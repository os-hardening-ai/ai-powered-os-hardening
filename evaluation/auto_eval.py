"""
Otomatik LLM-as-Judge Değerlendirmesi — H2 / H4 / İP-12 (insan pilotu YERİNE)

Öneri formundaki üç kullanıcı-çalışması maddesini İNSAN GEREKMEDEN, endüstri-standardı
LLM-as-a-judge yöntemiyle (MT-Bench / AlpacaEval / RAGAS hattı) otomatik ölçer:

  İP-12  Memnuniyet (Likert ≥4 oranı) > %70
  H2     Karar süresi: araçla (RAG) vs araçsız (RAG'siz) — azalma
  H4     Öneri kabul oranı: RAG'li öneriler ne oranda kabul edilebilir

YÖNTEM:
  Küratörlü senaryo seti → her senaryo için
    (a) RAG'li cevap  : gerçek pipeline (RAGContextBuilder + GROUNDING_DIRECTIVE)
    (b) RAG'siz cevap : AYNI LLM, bağlamsız (kontrol)
  → LLM-judge (kıdemli sysadmin persona) her cevabı puanlar:
      verdict (accept/modify/reject)         → H4
      actionability (0-1, ek-araştırmasız uygulanabilirlik) → H2 proxy
      Likert 1-5 (usefulness/trust/clarity/would_use_again/overall) → İP-12
  → survey_eval.summarize() (DEĞİŞMEDEN yeniden kullanılır) ile AYNI metrikler.

KARAR SÜRESİ (H2) PROXY: insan "saniye" ölçülemez. actionability → türetilmiş süre:
  yüksek actionability = daha az ek-araştırma = daha kısa karar süresi
  decision_time_s = _DT_BASE_S * (1 - actionability). RAG actionability > no-RAG ise H2 ✓.
  Rapor bunun TÜRETİLMİŞ PROXY olduğunu açıkça belirtir (uydurma yok).

DÜRÜSTLÜK: Bu otomatik proxy'dir, gerçek kullanıcı değil. Ama tekrarlanabilir, objektif ve
ölçeklenebilir; kıyas (RAG vs no-RAG) aynı judge ile yapıldığı için göreli sonuç anlamlıdır.

Çalıştırma (kotasız sağlayıcı önerilir):
    LLM_PROVIDER=novita python -m evaluation.auto_eval
Çıktı: evaluation/results/auto_eval_report.md + auto_eval_results.json
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

from evaluation.survey_eval import summarize as survey_summarize

logger = logging.getLogger(__name__)

LLMCallable = Callable[[str], str]

# actionability → karar süresi türetme tabanı (saniye). Yalnız RAG vs no-RAG GÖRELİ
# kıyas için; mutlak değer önemli değil, fark önemli.
_DT_BASE_S = 240.0

# Geçerli verdict'ler ve survey_eval kredi anahtarları ile uyumlu
_VALID_VERDICTS = ("accept", "modify", "reject")
_LIKERT_KEYS = ("usefulness", "trust", "clarity", "would_use_again", "overall_satisfaction")


# ── Küratörlü senaryo seti (ip_metrics ile aynı domain, gerçek CIS hedefleri) ──
@dataclass
class EvalScenario:
    goal: str
    os_target: str = "ubuntu_24_04"
    security_level: str = "balanced"


SCENARIOS: List[EvalScenario] = [
    EvalScenario("Ubuntu 24.04'te SSH sunucusunu CIS'e göre sıkılaştır (root login, MaxAuthTries)"),
    EvalScenario("Parola politikası ve PAM kurallarını güçlendir"),
    EvalScenario("UFW güvenlik duvarını varsayılan-reddet politikasıyla yapılandır"),
    EvalScenario("Denetim (auditd) kurallarını ve log saklamayı yapılandır", security_level="strict"),
    EvalScenario("Kernel ve ağ parametrelerini (sysctl) sıkılaştır"),
    EvalScenario("Dosya izinlerini ve kullanılmayan kernel modüllerini sıkılaştır"),
    EvalScenario("SSH için yalnız anahtar-tabanlı kimlik doğrulamayı zorunlu kıl"),
    EvalScenario("Sistem güncellemeleri ve otomatik güvenlik yamalarını yapılandır"),
]


# ── Saf yardımcılar (LLM'siz, deterministik → unit-test edilebilir) ──

def actionability_to_decision_time(actionability: float) -> float:
    """actionability(0-1) → türetilmiş karar süresi (s). Yüksek action = kısa süre (monotonik)."""
    a = min(1.0, max(0.0, float(actionability)))
    return round(_DT_BASE_S * (1.0 - a), 2)


def normalize_verdict(raw: str) -> str:
    """LLM verdict metnini accept|modify|reject'e indir (bilinmeyende conservative=modify)."""
    s = str(raw).strip().lower()
    for v in _VALID_VERDICTS:
        if v in s:
            return v
    # TR eşleşmeleri
    if any(w in s for w in ("kabul", "uygula")):
        return "accept"
    if any(w in s for w in ("ret", "redd", "yanlış", "hatalı")):
        return "reject"
    return "modify"  # belirsiz → yarım kredi (ne tam kabul ne tam ret)


def parse_score(raw: str, default: float = 0.5) -> float:
    """LLM'den 0-1 skor çıkar (ragas_evaluator._ask_score mantığıyla uyumlu)."""
    try:
        m = re.search(r"\b(1\.0|0\.\d{1,3}|[01])\b", str(raw))
        if m:
            return min(1.0, max(0.0, float(m.group())))
        low = str(raw).lower()
        if any(w in low for w in ("yes", "fully", "evet", "tam")):
            return 1.0
        if any(w in low for w in ("no", "none", "hayır", "hiç")):
            return 0.0
    except Exception:
        pass
    return default


def parse_likert(val, default: int = 3) -> int:
    """1-5 Likert değerini güvenle çöz (aralık dışı → kırp, parse hatası → nötr 3)."""
    try:
        n = int(round(float(val)))
        return min(5, max(1, n))
    except Exception:
        return default


# ── Sonuç yapıları ──

@dataclass
class ModeJudgement:
    mode: str                      # "rag" | "no_rag"
    verdict: str                   # accept | modify | reject
    actionability: float           # 0-1
    likert: Dict[str, int]         # usefulness/trust/clarity/would_use_again/overall_satisfaction
    reason: str = ""


@dataclass
class ScenarioResult:
    goal: str
    rag: ModeJudgement
    no_rag: ModeJudgement
    n_chunks: int


@dataclass
class AutoEvalReport:
    results: List[ScenarioResult] = field(default_factory=list)

    def to_survey_data(self) -> dict:
        """survey_eval.summarize()'in beklediği participants şemasına dönüştür.

        Her senaryo = bir 'participant' (tek task). RAG cevabı 'with_tool', RAG'siz
        cevabı 'baseline'. Memnuniyet (Likert) = RAG cevabının puanları (araç bu).
        Kabul oranı (H4) = RAG önerilerinin verdict'i.
        """
        participants = []
        for r in self.results:
            participants.append({
                "id": r.goal[:40],
                "role": "auto_judge",
                "tasks": [{
                    "task_id": r.goal[:40],
                    "decision_time_with_tool_s": actionability_to_decision_time(r.rag.actionability),
                    "decision_time_baseline_s": actionability_to_decision_time(r.no_rag.actionability),
                    "recommendations": [{"id": "rag", "verdict": r.rag.verdict}],
                }],
                "survey": dict(r.rag.likert),
            })
        return {"study": "auto_llm_judge", "participants": participants}

    def rag_vs_norag(self) -> Dict[str, float]:
        """H1-stili göreli kıyas: RAG vs no-RAG (accept kredisi + actionability)."""
        def credit(v: str) -> float:
            return {"accept": 1.0, "modify": 0.5, "reject": 0.0}.get(v, 0.0)
        n = len(self.results) or 1
        return {
            "n": len(self.results),
            "rag_accept_credit": round(sum(credit(r.rag.verdict) for r in self.results) / n, 4),
            "norag_accept_credit": round(sum(credit(r.no_rag.verdict) for r in self.results) / n, 4),
            "rag_actionability": round(sum(r.rag.actionability for r in self.results) / n, 4),
            "norag_actionability": round(sum(r.no_rag.actionability for r in self.results) / n, 4),
        }


# ── Harness ──

class AutoEvalHarness:
    """LLM-judge otomatik değerlendirme. answer_fn/judge_fn enjekte edilebilir (ağsız test)."""

    def __init__(
        self,
        answer_fn: Optional[Callable[[str, bool], tuple]] = None,
        judge_fn: Optional[LLMCallable] = None,
        llm_fn: Optional[LLMCallable] = None,
        throttle_s: float = 0.0,
        top_k: int = 5,
        min_score: float = 0.4,
    ) -> None:
        """
        Args:
            answer_fn: (goal, use_rag) -> (answer_text, n_chunks). None → gerçek pipeline.
            judge_fn:  LLM-judge callable (prompt -> JSON str). None → llm_fn kullanılır.
            llm_fn:    Cevap üreten LLM (answer_fn None ise). None → get_llm_clients().large.
            throttle_s: senaryolar arası bekleme (rate-limit).
        """
        self.throttle_s = throttle_s
        self.top_k = top_k
        self.min_score = min_score
        self._answer_fn = answer_fn
        self._judge_fn = judge_fn
        self._llm_fn = llm_fn
        self._rag_builder = None  # lazy

    # ── cevap üretimi ──
    def _answer(self, goal: str, sc: EvalScenario, use_rag: bool) -> tuple:
        if self._answer_fn is not None:
            return self._answer_fn(goal, use_rag)
        # gerçek pipeline (ip_metrics._measure_ip5 deseni)
        llm = self._llm_fn
        if llm is None:
            from llm.clients import get_llm_clients
            _small, large = get_llm_clients()
            llm = large
            self._llm_fn = large
        if not use_rag:
            return llm(f"'{goal}' için kısa, teknik bir OS sıkılaştırma önerisi yaz:"), 0
        from llm.rag.integration import RAGContextBuilder
        from llm.prompts.simple_prompts import GROUNDING_DIRECTIVE
        try:
            rag = RAGContextBuilder(top_k=self.top_k, min_score=self.min_score, os_version=sc.os_target)
            _ctx, chunks = rag.retrieve_balanced(goal)
        except Exception as exc:
            logger.warning("[auto_eval] RAG retrieval başarısız: %s", exc)
            chunks = []
        ctx_txt = "\n\n".join(c.get("text", "") for c in chunks)
        if chunks:
            prompt = (f"SORU: '{goal}' için kısa, teknik bir sıkılaştırma önerisi yaz.\n\n"
                      f"CIS BENCHMARK REFERANSLARI:\n{ctx_txt}\n{GROUNDING_DIRECTIVE}\n\nYANIT:")
        else:
            prompt = f"'{goal}' için kısa öneri:"
        return llm(prompt), len(chunks)

    # ── LLM-judge ──
    def _judge_prompt(self, goal: str, answer: str) -> str:
        return (
            "Sen kıdemli bir Linux/Windows sistem yöneticisisin. Aşağıdaki SORU için üretilen "
            "ÖNERİYİ değerlendir. SADECE JSON döndür, başka metin yazma:\n"
            '{"verdict":"accept|modify|reject",'
            '"actionability":0.0-1.0,'
            '"usefulness":1-5,"trust":1-5,"clarity":1-5,"would_use_again":1-5,'
            '"overall_satisfaction":1-5,"reason":"tek cümle"}\n\n'
            "verdict: öneriyi olduğu gibi uygular mıydın (accept), düzelterek mi (modify), "
            "reddeder mi (reject)?\n"
            "actionability: ek araştırma YAPMADAN doğrudan uygulanabilirlik (1.0=komutlar hazır, "
            "0.0=belirsiz/eksik).\n"
            "Likert 1-5: faydalılık, güven, açıklık, tekrar kullanım, genel memnuniyet.\n\n"
            f"SORU: {goal[:300]}\n\nÖNERİ:\n{answer[:1800]}\n"
        )

    def _judge(self, goal: str, answer: str, mode: str) -> ModeJudgement:
        judge = self._judge_fn
        if judge is None:
            judge = self._llm_fn
            if judge is None:
                from llm.clients import get_llm_clients
                small, _large = get_llm_clients()
                judge = small
                self._judge_fn = small
        raw = ""
        try:
            raw = judge(self._judge_prompt(goal, answer))
            obj = _extract_json_obj(raw)
        except Exception as exc:
            logger.warning("[auto_eval] judge çağrısı başarısız (%s): conservative", exc)
            obj = {}
        verdict = normalize_verdict(obj.get("verdict", "modify"))
        action = parse_score(str(obj.get("actionability", 0.5)))
        likert = {k: parse_likert(obj.get(k, 3)) for k in _LIKERT_KEYS}
        reason = str(obj.get("reason", ""))[:200]
        return ModeJudgement(mode=mode, verdict=verdict, actionability=action,
                             likert=likert, reason=reason)

    def run(self, scenarios: Optional[List[EvalScenario]] = None) -> AutoEvalReport:
        scenarios = scenarios or SCENARIOS
        rep = AutoEvalReport()
        for i, sc in enumerate(scenarios, 1):
            logger.info("[auto_eval] (%d/%d) %s", i, len(scenarios), sc.goal[:55])
            try:
                rag_ans, n_chunks = self._answer(sc.goal, sc, use_rag=True)
                norag_ans, _ = self._answer(sc.goal, sc, use_rag=False)
                rag_j = self._judge(sc.goal, rag_ans, "rag")
                norag_j = self._judge(sc.goal, norag_ans, "no_rag")
                rep.results.append(ScenarioResult(goal=sc.goal, rag=rag_j,
                                                  no_rag=norag_j, n_chunks=n_chunks))
            except Exception as exc:
                logger.warning("[auto_eval] senaryo atlandı: %s", exc)
            if self.throttle_s and i < len(scenarios):
                time.sleep(self.throttle_s)
        return rep


def _extract_json_obj(text: str) -> dict:
    """LLM çıktısından ilk JSON nesnesini çıkar (markdown sarmalı toleranslı)."""
    try:
        m = re.search(r"\{.*\}", str(text), re.DOTALL)
        if m:
            return json.loads(m.group())
    except Exception:
        pass
    return {}


# ── Raporlama ──

def to_markdown(rep: AutoEvalReport) -> str:
    data = rep.to_survey_data()
    s = survey_summarize(data)          # MEVCUT skorlama yeniden kullanılır
    cmp = rep.rag_vs_norag()
    sat = s["ip12_satisfaction"]; acc = s["h4_acceptance"]; dt = s["h2_decision_time"]  # type: ignore[index]
    sat_mark = "✅" if sat["passed"] else "⚠️"
    h2_mark = "✅" if s["h2_supported"] else "⚠️"
    h4_mark = "✅" if cmp["rag_accept_credit"] >= cmp["norag_accept_credit"] else "⚠️"
    L = [
        "# Otomatik LLM-Judge Değerlendirmesi — H2 / H4 / İP-12",
        "",
        "**Yöntem:** Küratörlü senaryolarda RAG'li vs RAG'siz cevaplar üretilir; kıdemli-sysadmin "
        "persona'lı LLM-judge (MT-Bench/AlpacaEval/RAGAS hattı) puanlar. İnsan pilotu YERİNE "
        "otomatik proxy — tekrarlanabilir + objektif.",
        "",
        f"**Senaryo sayısı (n):** {cmp['n']}",
        "",
        "| Madde | Metrik | Sonuç | Eşik/Yön | Durum |",
        "|-------|--------|------:|:--------:|:-----:|",
        f"| İP-12 | Memnuniyet (Likert ≥4 oranı) | {sat['rate']:.0%} | >%70 | {sat_mark} |",
        f"| H4 | RAG kabul kredisi vs RAG'siz | {cmp['rag_accept_credit']:.0%} vs {cmp['norag_accept_credit']:.0%} | RAG ≥ | {h4_mark} |",
        f"| H2 | Karar süresi azalması (proxy) | {dt['reduction_pct']:.0%} | >0 | {h2_mark} |",
        "",
        f"- **H2 proxy:** araçla {dt['mean_with_tool_s']}s vs araçsız {dt['mean_baseline_s']}s "
        f"(actionability'den türetildi: RAG {cmp['rag_actionability']:.2f} vs RAG'siz {cmp['norag_actionability']:.2f})",
        f"- **H4:** {acc['n_recommendations']} RAG önerisi değerlendirildi "
        f"(accept=1.0, modify=0.5, reject=0.0)",
        "",
        "> **Dürüstlük notu:** Bu otomatik LLM-judge proxy'sidir, gerçek kullanıcı çalışması "
        "değildir. Karar süresi actionability'den TÜRETİLMİŞTİR (mutlak saniye değil, RAG vs "
        "RAG'siz GÖRELİ kıyas anlamlıdır). Yöntem endüstri-standardı LLM-as-a-judge hattındadır.",
    ]
    return "\n".join(L)


def save_results(rep: AutoEvalReport, out_dir: str | Path = "evaluation/results") -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "auto_eval_report.md").write_text(to_markdown(rep), encoding="utf-8")
    payload = {
        "summary": survey_summarize(rep.to_survey_data()),
        "rag_vs_norag": rep.rag_vs_norag(),
        "scenarios": [
            {"goal": r.goal, "n_chunks": r.n_chunks,
             "rag": vars(r.rag), "no_rag": vars(r.no_rag)}
            for r in rep.results
        ],
    }
    (out / "auto_eval_results.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def main() -> None:
    from evaluation import force_utf8_output
    force_utf8_output()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    from llm.clients import get_llm_clients
    small, large = get_llm_clients()

    sample = int(os.environ.get("AUTO_EVAL_SAMPLE", "0")) or len(SCENARIOS)
    throttle = float(os.environ.get("AUTO_EVAL_THROTTLE_S", "3"))

    harness = AutoEvalHarness(llm_fn=large, judge_fn=small, throttle_s=throttle)
    rep = harness.run(SCENARIOS[:sample])

    out = save_results(rep)            # önce kaydet (konsol encode hatası sonuç kaybetmesin)
    print(to_markdown(rep))
    print(f"\nRapor: {out / 'auto_eval_report.md'} ve {out / 'auto_eval_results.json'}")


if __name__ == "__main__":
    main()
