"""
H1 Hipotez Kanıtı — RAG-temelli yanıtlar, saf-LLM yanıtlarına göre OS sıkılaştırma
sorularında daha doğru ve daha gerekçelidir (grounded).

Tasarım — KONTROLLÜ A/B (tek değişken = bağlam):
  Aynı üretim modeli (llm_large) ve AYNI prompt şablonu iki kez çalıştırılır:
    A) PURE  : CIS bağlamı YOK            → modelin parametrik bilgisi
    B) RAG   : retrieve edilen CIS chunk'ları prompt'a enjekte edilir
  Tek fark bağlam olduğu için ölçülen fark doğrudan RAG'in katkısıdır
  (güvenlik/intent yönlendirmesi gibi confound'lar elenir).

Metrikler (her soru, her mod için):
  • fact_recall   : küratörlü CIS ground-truth gerçeklerinin yanıtta bulunma oranı.
  • groundedness  : ClaimVerifier'ın yanıttaki iddiaların AYNI CIS chunk'larınca
                    desteklenme oranı (her iki mod da aynı chunk'lara karşı ölçülür
                    → simetrik, adil karşılaştırma).
  • latency_s     : üretim gecikmesi.

Çıktı: konsol tablosu + evaluation/results/h1_report.md + h1_results.json.

Çalıştırma (canlı LLM + Qdrant gerektirir):
    python -m evaluation.h1_rag_vs_llm
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

_logger = logging.getLogger(__name__)

LLMCallable = Callable[[str], str]


# ── Ground-truth değerlendirme seti ────────────────────────────────────────────
# Her gerçek (fact), CIS Ubuntu Benchmark'ın önerdiği KANONİK değerdir. Yanıtta
# (boşluk-normalize, küçük harf) alt-dize olarak aranır. Eşanlamlılar "|" ile
# verilir — herhangi biri eşleşirse gerçek "bulundu" sayılır.

@dataclass
class H1Question:
    question: str
    expected_facts: List[str]          # her öğe "a|b|c" → herhangi biri eşleşmeli
    cis_section: str = ""              # doğru atıf (citation) kontrolü için


H1_DATASET: List[H1Question] = [
    H1Question(
        "Ubuntu 24.04'te SSH üzerinden root oturum açmayı CIS'e göre nasıl engellerim?",
        ["permitrootlogin no"], "5.1",
    ),
    H1Question(
        "CIS, SSH için MaxAuthTries değerini kaç önerir ve nasıl ayarlanır?",
        ["maxauthtries 4|maxauthtries=4|maxauthtries 3"], "5.1",
    ),
    H1Question(
        "SSH'te boş parolalı girişleri engellemek için hangi direktif kullanılır?",
        ["permitemptypasswords no"], "5.1",
    ),
    H1Question(
        "CIS Benchmark parolalar için minimum uzunluğu kaç olarak önerir?",
        ["14"], "5.4",
    ),
    H1Question(
        "Parola maksimum geçerlilik süresi (PASS_MAX_DAYS) CIS'e göre ne olmalıdır?",
        ["365"], "5.4",
    ),
    H1Question(
        "Çekirdek seviyesinde adres uzayı rastgeleleştirmesi (ASLR) nasıl etkinleştirilir?",
        ["kernel.randomize_va_space = 2|randomize_va_space=2|randomize_va_space = 2"], "1.5",
    ),
    H1Question(
        "Bir host'ta IPv4 paket yönlendirmeyi (IP forwarding) CIS'e göre nasıl devre dışı bırakırım?",
        ["net.ipv4.ip_forward = 0|ip_forward = 0|ip_forward=0"], "3.1",
    ),
    H1Question(
        "UFW güvenlik duvarında varsayılan gelen trafik politikası ne olmalıdır?",
        ["default deny"], "3.5",
    ),
    H1Question(
        "cramfs çekirdek modülünün yüklenmesini kalıcı olarak nasıl engellerim?",
        ["install cramfs /bin/false|install cramfs /bin/true|blacklist cramfs|modprobe.d"], "1.1",
    ),
    H1Question(
        "auditd servisinin açılışta etkin olmasını nasıl sağlarım?",
        ["systemctl enable auditd|systemctl --now enable auditd|enable auditd"], "6.2",
    ),
    H1Question(
        "SSH boşta oturum zaman aşımı için hangi direktifler ayarlanır?",
        ["clientaliveinterval", "clientalivecountmax"], "5.1",
    ),
    H1Question(
        "Çekirdek üzerinde core dump'ları (fs.suid_dumpable) nasıl devre dışı bırakırım?",
        ["fs.suid_dumpable = 0|suid_dumpable = 0|suid_dumpable=0"], "1.5",
    ),
]


# ── Saf skorlama fonksiyonları (LLM'siz, deterministik → unit-test edilebilir) ──

def _normalize(text: str) -> str:
    """Küçük harf + tüm boşlukları tek boşluğa indir (alt-dize eşleşmesi için)."""
    return re.sub(r"\s+", " ", text.lower()).strip()


def fact_recall(answer: str, expected_facts: List[str]) -> float:
    """Beklenen gerçeklerin yanıtta bulunma oranı (0.0–1.0).

    Her beklenen gerçek "a|b|c" alternatiflerinden herhangi biriyle eşleşebilir.
    """
    if not expected_facts:
        return 1.0
    norm = _normalize(answer)
    hits = 0
    for fact in expected_facts:
        alternatives = [_normalize(a) for a in fact.split("|")]
        if any(alt in norm for alt in alternatives):
            hits += 1
    return hits / len(expected_facts)


def cites_section(answer: str, cis_section: str) -> bool:
    """Yanıt doğru CIS bölüm numarasına atıf veriyor mu (örn. '5.1')."""
    if not cis_section:
        return False
    return bool(re.search(rf"\b{re.escape(cis_section)}(\.\d+)*\b", answer))


# ── Çalıştırma yapıları ─────────────────────────────────────────────────────────

@dataclass
class ModeSample:
    mode: str                  # "pure" | "rag"
    answer: str
    fact_recall: float
    groundedness: float        # ClaimVerifier confidence (aynı chunk'lara karşı)
    cites: bool
    latency_s: float


@dataclass
class H1Pair:
    question: str
    pure: ModeSample
    rag: ModeSample
    num_chunks: int


@dataclass
class H1Report:
    pairs: List[H1Pair] = field(default_factory=list)

    def _avg(self, mode: str, attr: str) -> float:
        vals = [getattr(getattr(p, mode), attr) for p in self.pairs]
        return sum(vals) / len(vals) if vals else 0.0

    def summary(self) -> Dict[str, float]:
        n = len(self.pairs) or 1
        rag_wins = sum(1 for p in self.pairs if p.rag.fact_recall > p.pure.fact_recall)
        ties = sum(1 for p in self.pairs if p.rag.fact_recall == p.pure.fact_recall)
        losses = sum(1 for p in self.pairs if p.rag.fact_recall < p.pure.fact_recall)
        return {
            "n": len(self.pairs),
            "pure_fact_recall": self._avg("pure", "fact_recall"),
            "rag_fact_recall": self._avg("rag", "fact_recall"),
            "pure_groundedness": self._avg("pure", "groundedness"),
            "rag_groundedness": self._avg("rag", "groundedness"),
            "pure_citation_rate": sum(p.pure.cites for p in self.pairs) / n,
            "rag_citation_rate": sum(p.rag.cites for p in self.pairs) / n,
            "pure_latency_s": self._avg("pure", "latency_s"),
            "rag_latency_s": self._avg("rag", "latency_s"),
            "rag_wins": rag_wins,
            "ties": ties,
            "rag_losses": losses,
        }


_SYS_PROMPT = (
    "Sen bir OS sıkılaştırma (hardening) uzmanısın. Soruyu kısa ve teknik yanıtla; "
    "ilgili yapılandırma direktifini/değerini ve varsa CIS bölüm numarasını belirt."
)


def _build_prompt(question: str, context: Optional[str]) -> str:
    if context:
        return (
            f"{_SYS_PROMPT}\n\n"
            f"Aşağıdaki CIS Benchmark bağlamını kullan:\n{context}\n\n"
            f"SORU: {question}\nYANIT:"
        )
    return f"{_SYS_PROMPT}\n\nSORU: {question}\nYANIT:"


class H1Harness:
    """RAG vs saf-LLM kontrollü karşılaştırma koşucusu."""

    def __init__(
        self,
        llm_fn: LLMCallable,
        verifier_llm: Optional[LLMCallable] = None,
        top_k: int = 5,
        min_score: float = 0.4,
        throttle_s: float = 0.0,
        max_claims: int = 4,
    ) -> None:
        self._llm = llm_fn
        self._verifier_llm = verifier_llm or llm_fn
        self.top_k = top_k
        self.min_score = min_score
        # Sağlayıcı hız limitlerine (örn. Groq ücretsiz tier) saygı için sorular
        # arası bekleme; groundedness iddia sayısı da limiti azaltmak için ayarlı.
        self.throttle_s = throttle_s
        self.max_claims = max_claims

    def _verify(self, answer: str, chunks: List[dict]) -> float:
        if not chunks:
            return 0.0
        try:
            from rag.verify.claim_verifier import ClaimVerifier
            cv = ClaimVerifier(llm_fn=self._verifier_llm, max_claims=self.max_claims)
            return cv.verify(answer, chunks).confidence
        except Exception as exc:  # pragma: no cover - defensive
            _logger.warning("[H1] groundedness verify failed: %s", exc)
            return 0.0

    def _run_pair(self, q: H1Question) -> H1Pair:
        from llm.rag.integration import RAGContextBuilder

        # Tek retrieval — her iki mod aynı chunk'lara karşı ölçülür (simetri).
        rag = RAGContextBuilder(top_k=self.top_k, min_score=self.min_score)
        context, chunks = rag.retrieve_balanced(q.question)
        if not chunks:
            context = ""

        # A) PURE — bağlam yok
        t0 = time.monotonic()
        pure_ans = self._llm(_build_prompt(q.question, None))
        pure_lat = time.monotonic() - t0

        # B) RAG — CIS bağlamı enjekte
        t1 = time.monotonic()
        rag_ans = self._llm(_build_prompt(q.question, context)) if context else pure_ans
        rag_lat = time.monotonic() - t1

        pure = ModeSample(
            "pure", pure_ans, fact_recall(pure_ans, q.expected_facts),
            self._verify(pure_ans, chunks), cites_section(pure_ans, q.cis_section), pure_lat,
        )
        rag_s = ModeSample(
            "rag", rag_ans, fact_recall(rag_ans, q.expected_facts),
            self._verify(rag_ans, chunks), cites_section(rag_ans, q.cis_section), rag_lat,
        )
        return H1Pair(question=q.question, pure=pure, rag=rag_s, num_chunks=len(chunks))

    def run(self, questions: Optional[List[H1Question]] = None) -> H1Report:
        import time as _time
        questions = questions or H1_DATASET
        report = H1Report()
        for i, q in enumerate(questions, 1):
            _logger.info("[H1] (%d/%d) %s", i, len(questions), q.question[:55])
            try:
                report.pairs.append(self._run_pair(q))
            except Exception as exc:
                _logger.warning("[H1] question failed, skipping: %s", exc)
            if self.throttle_s and i < len(questions):
                _time.sleep(self.throttle_s)
        return report


# ── Raporlama ───────────────────────────────────────────────────────────────────

def print_report(report: H1Report) -> None:
    s = report.summary()
    # ASCII-only console output — Windows konsolu (cp1254) Δ/— gibi karakterleri
    # encode edemiyor; rapor dosyası (UTF-8) tam karakter setini korur.
    print(f"\n{'='*68}")
    print("H1 - RAG vs SAF-LLM (kontrollu A/B)")
    print(f"{'='*68}")
    print(f"{'Metrik':<26}{'PURE (LLM)':>14}{'RAG':>14}{'Delta':>12}")
    print("-" * 68)
    rows = [
        ("Fact-recall (doğruluk)", "pure_fact_recall", "rag_fact_recall"),
        ("Groundedness", "pure_groundedness", "rag_groundedness"),
        ("CIS atıf oranı", "pure_citation_rate", "rag_citation_rate"),
        ("Latency (s)", "pure_latency_s", "rag_latency_s"),
    ]
    for label, pk, rk in rows:
        delta = s[rk] - s[pk]
        print(f"{label:<26}{s[pk]:>14.3f}{s[rk]:>14.3f}{delta:>+12.3f}")
    print("-" * 68)
    print(f"Soru sayisi: {s['n']}  |  RAG kazandi: {s['rag_wins']}  "
          f"berabere: {s['ties']}  kaybetti: {s['rag_losses']}")
    print(f"{'='*68}\n")


def to_markdown(report: H1Report) -> str:
    s = report.summary()
    lines = [
        "# H1 Kanıtı — RAG vs Saf-LLM (Kontrollü A/B)",
        "",
        "**Hipotez (H1):** RAG ile CIS bağlamı enjekte edilen yanıtlar, saf-LLM "
        "yanıtlarına göre daha doğru (fact-recall) ve daha gerekçelidir (groundedness).",
        "",
        "**Yöntem:** Aynı üretim modeli + aynı prompt şablonu; tek değişken CIS bağlamı. "
        "Groundedness her iki mod için *aynı* retrieve edilen chunk'lara karşı ölçülür.",
        "",
        f"**Örneklem:** {s['n']} OS sıkılaştırma sorusu (CIS Ubuntu Benchmark ground-truth).",
        "",
        "## Toplu Sonuçlar",
        "",
        "| Metrik | PURE (LLM) | RAG | Δ |",
        "|---|---:|---:|---:|",
        f"| Fact-recall (doğruluk) | {s['pure_fact_recall']:.3f} | {s['rag_fact_recall']:.3f} | {s['rag_fact_recall']-s['pure_fact_recall']:+.3f} |",
        f"| Groundedness | {s['pure_groundedness']:.3f} | {s['rag_groundedness']:.3f} | {s['rag_groundedness']-s['pure_groundedness']:+.3f} |",
        f"| CIS atıf oranı | {s['pure_citation_rate']:.3f} | {s['rag_citation_rate']:.3f} | {s['rag_citation_rate']-s['pure_citation_rate']:+.3f} |",
        f"| Latency (s) | {s['pure_latency_s']:.2f} | {s['rag_latency_s']:.2f} | {s['rag_latency_s']-s['pure_latency_s']:+.2f} |",
        "",
        f"**Karşılaştırma (fact-recall):** RAG kazandı **{s['rag_wins']}**, "
        f"berabere {s['ties']}, kaybetti {s['rag_losses']} (n={s['n']}).",
        "",
        "## Soru Bazında",
        "",
        "| # | Soru | PURE recall | RAG recall | PURE ground | RAG ground |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for i, p in enumerate(report.pairs, 1):
        q = p.question if len(p.question) <= 60 else p.question[:57] + "..."
        lines.append(
            f"| {i} | {q} | {p.pure.fact_recall:.2f} | {p.rag.fact_recall:.2f} | "
            f"{p.pure.groundedness:.2f} | {p.rag.groundedness:.2f} |"
        )
    lines.append("")
    return "\n".join(lines)


def save_results(report: H1Report, out_dir: str | Path = "evaluation/results") -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "h1_report.md").write_text(to_markdown(report), encoding="utf-8")
    payload = {
        "summary": report.summary(),
        "pairs": [
            {
                "question": p.question,
                "num_chunks": p.num_chunks,
                "pure": vars(p.pure),
                "rag": vars(p.rag),
            }
            for p in report.pairs
        ],
    }
    (out / "h1_results.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return out


def main() -> None:
    import os
    from evaluation import force_utf8_output
    force_utf8_output()                       # Türkçe log Windows'ta bozulmasın
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    from llm.clients import get_llm_clients
    small, large = get_llm_clients()

    # Ölçek/throttle env ile ayarlanabilir (Groq ücretsiz tier dostu varsayılanlar).
    sample = int(os.environ.get("H1_SAMPLE", "0")) or len(H1_DATASET)
    throttle = float(os.environ.get("H1_THROTTLE_S", "4"))
    max_claims = int(os.environ.get("H1_MAX_CLAIMS", "3"))

    # Üretim modeli = large; groundedness yargısı için hızlı small model.
    harness = H1Harness(
        llm_fn=large, verifier_llm=small,
        throttle_s=throttle, max_claims=max_claims,
    )
    report = harness.run(H1_DATASET[:sample])

    # Önce kaydet (konsol encode hatası sonuçları kaybetmesin), sonra yazdır.
    out = save_results(report)
    print(f"Rapor kaydedildi: {out / 'h1_report.md'}  ve  {out / 'h1_results.json'}")
    try:
        print_report(report)
    except Exception as exc:  # pragma: no cover - konsol encoding vb.
        print(f"(Konsol ozeti yazdirilamadi, rapor dosyada: {exc})")


if __name__ == "__main__":
    main()
