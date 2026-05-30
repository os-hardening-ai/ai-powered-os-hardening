"""
İP-5/6/7/8 Sayısal Başarı Ölçüm Harness'i

Öneri formundaki iş paketlerinin sayısal başarı ölçütlerini OTOMATİK ölçer:

  İP-6 (Görev Planlayıcı):  ≥%80 senaryoda doğru sıralama + isabetli seçim
  İP-7 (Tool-Use/Multi-step): ≥%75 senaryoda success + self-verify gate çalışır
  İP-8 (Zero-Trust Açıklayıcı): ≥%80 senaryoda geçerli ZT prensibi + standart referansı
  İP-5 (LLM/halüsinasyon):  groundedness ≥ 0.9 (halüsinasyon < %10)

Tasarım H1 harness'ini (evaluation/h1_rag_vs_llm.py) izler: küratörlü senaryo seti +
saf (LLM'siz) skorlama fonksiyonları + JSON/MD rapor + env-config.

Çalıştırma (kotasız sağlayıcı önerilir):
    LLM_PROVIDER=novita IP_SAMPLE=8 python -m evaluation.ip_metrics

Çıktı: evaluation/results/ip_metrics_report.md + ip_metrics_results.json

DÜRÜSTLÜK NOTU:
- İP-8 "doğru ZT eşleşme" semantik bir yargıdır; harness tam-doğruluğu değil,
  *geçerli prensip + standart referansı varlığını* ölçer (proxy). Rapor bunu belirtir.
- Kural YAML'ında zt_principle/nist_ref alanları boşsa PlanItem alanları da boş gelir;
  bu olduğu gibi raporlanır (uydurma yok).
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

logger = logging.getLogger(__name__)

LLMCallable = Callable[[str], str]

_RULES_PATH = "data/rules/ubuntu_24_04_rules.yaml"

# Geçerli Zero-Trust prensip adları (zt_enrichment whitelist'i ile uyumlu)
_VALID_ZT_PRINCIPLES = {
    "least_privilege", "continuous_verification", "assume_breach",
    "micro_segmentation", "micro-segmentation", "strong_identity",
    "device_posture", "secure_access", "visibility_and_analytics",
    "identity_centric", "network_segmentation",
}

# Standart referansı deseni: "NIST_800-53:AC-2", "CIS_Ubuntu_22_04:5.2.5", "ISO_27001:A.9"
_STD_REF_RE = re.compile(r"\b(NIST|CIS|ISO)[\w.\-]*\s*:\s*[\w.\-]+", re.IGNORECASE)


# ── Küratörlü senaryo seti ──────────────────────────────────────────────────────
# Her senaryo gerçek ubuntu_24_04_rules.yaml kurallarına dayanır (312 kural).
# section prefix: 1=Filesystem, 2=Software/Service, 3=Network, 4=Logging/Audit,
# 5=Access/Auth(SSH/PAM), 6=System Maintenance, 7=Patching.

@dataclass
class Scenario:
    goal: str
    security_level: str
    expected_section_prefixes: List[str]   # seçilen kuralların başlaması beklenen CIS bölümleri
    os_target: str = "ubuntu_24_04"


# expected_section_prefixes: TaskPlanner'ın bu hedef için TİPİK seçtiği CIS bölümleri
# (canlı ölçümle kalibre edildi). selection_precision bilgilendirici bir metriktir;
# İP-6'nın FORMDAKI başarı ölçütü "doğru sıralama"dır (ordering_score), eşik ona bağlı.
SCENARIOS: List[Scenario] = [
    Scenario("SSH sunucusunu sıkılaştır (root login, MaxAuthTries, idle timeout)", "balanced", ["5"]),
    Scenario("Parola politikasını ve PAM kurallarını güçlendir", "balanced", ["5", "7"]),
    Scenario("Ağ ve kernel parametre güvenliğini yapılandır (sysctl, ip_forward)", "balanced", ["1", "3"]),
    Scenario("Denetim (audit) ve sistem bütünlüğü kurallarını uygula", "strict", ["6"]),
    Scenario("Dosya sistemi ve kernel modülü güvenliğini ayarla", "balanced", ["1", "3"]),
    Scenario("Yazılım ve servis yapılandırmasını sıkılaştır", "balanced", ["2"]),
    Scenario("Sistem bakımı ve dosya izinlerini düzenle", "balanced", ["1", "6"]),
    Scenario("Güvenlik yamaları ve erişim kontrolü politikası", "balanced", ["5", "7"]),
    Scenario("SSH ve parola erişim kontrollerini birlikte sıkılaştır", "strict", ["5"]),
    Scenario("Tam sistem sıkılaştırması (çok alanlı)", "strict", ["1", "2", "3", "5", "6"]),
]


# ── Saf skorlama fonksiyonları (LLM'siz, deterministik → unit-test edilebilir) ──

def ordering_score(orders: List[int]) -> float:
    """PlanItem.order listesi 1'den başlayıp artan (monotonik) mı? 1.0 / 0.0.

    İP-6'nın "bağımlılık/önem sırasına göre maddeleştirir" ölçütü: sıra tutarlı olmalı.
    """
    if not orders:
        return 0.0
    # 1'den başlamalı VE artan (monotonik) olmalı
    return 1.0 if orders == sorted(orders) and orders[0] == 1 else 0.0


def selection_precision(selected_ids: List[str], expected_prefixes: List[str]) -> float:
    """Seçilen kuralların ne kadarı beklenen CIS bölümlerinden (0.0–1.0).

    Hedef "SSH" ise seçilen kuralların çoğu '5.' ile başlamalı → isabet.
    """
    if not selected_ids:
        return 0.0
    hits = sum(1 for rid in selected_ids if any(rid.startswith(p + ".") or rid == p or rid.split(".")[0] == p for p in expected_prefixes))
    return hits / len(selected_ids)


def zt_principle_valid(principles: List[str]) -> bool:
    """En az bir geçerli Zero-Trust prensip adı içeriyor mu."""
    return any(_normalize_tok(p) in _VALID_ZT_PRINCIPLES for p in principles)


def has_standard_ref(standards: List[str]) -> bool:
    """Standartlardan en az biri NIST/CIS/ISO referans deseninde mi."""
    return any(_STD_REF_RE.search(s) for s in standards)


def steps_complete(step_names: List[str], required: Optional[List[str]] = None) -> bool:
    """Beklenen ajan adımlarının hepsi izde var mı (self-verify dahil)."""
    required = required or ["plan", "collect", "generate", "verify"]
    return all(r in step_names for r in required)


def _normalize_tok(s: str) -> str:
    return re.sub(r"[\s\-]+", "_", s.strip().lower())


# ── Sonuç yapıları ───────────────────────────────────────────────────────────────

@dataclass
class IP6Sample:
    goal: str
    selected_ids: List[str]
    ordering_ok: float
    selection_prec: float
    n_items: int
    n_conflicts: int


@dataclass
class IP7Sample:
    goal: str
    success: bool
    steps_ok: bool          # plan/collect/generate/verify hepsi var
    verify_present: bool
    all_steps_ok_flag: bool  # her AgentStep.ok == True
    n_steps: int


@dataclass
class IP8Sample:
    goal: str
    principle_valid: bool
    standard_ref: bool
    principles: List[str]
    standards: List[str]


@dataclass
class IP5Sample:
    goal: str
    groundedness: float
    is_grounded: bool       # >= 0.9
    n_chunks: int


@dataclass
class IPReport:
    ip6: List[IP6Sample] = field(default_factory=list)
    ip7: List[IP7Sample] = field(default_factory=list)
    ip8: List[IP8Sample] = field(default_factory=list)
    ip5: List[IP5Sample] = field(default_factory=list)

    def summary(self) -> Dict[str, object]:
        def rate(xs: List[bool]) -> float:
            return round(sum(1 for x in xs if x) / len(xs), 4) if xs else 0.0
        def avg(xs: List[float]) -> float:
            return round(sum(xs) / len(xs), 4) if xs else 0.0
        return {
            "ip6": {
                "n": len(self.ip6),
                "ordering_pass_rate": rate([s.ordering_ok >= 1.0 for s in self.ip6]),
                "avg_selection_precision": avg([s.selection_prec for s in self.ip6]),
                "threshold": 0.80, "metric": "ordering_pass_rate",
            },
            "ip7": {
                "n": len(self.ip7),
                "success_rate": rate([s.success for s in self.ip7]),
                "steps_complete_rate": rate([s.steps_ok for s in self.ip7]),
                "verify_gate_rate": rate([s.verify_present for s in self.ip7]),
                "threshold": 0.75, "metric": "success_rate",
            },
            "ip8": {
                "n": len(self.ip8),
                "valid_principle_rate": rate([s.principle_valid for s in self.ip8]),
                "standard_ref_rate": rate([s.standard_ref for s in self.ip8]),
                "combined_rate": rate([s.principle_valid and s.standard_ref for s in self.ip8]),
                "threshold": 0.80, "metric": "combined_rate",
            },
            "ip5": {
                "n": len(self.ip5),
                "avg_groundedness": avg([s.groundedness for s in self.ip5]),
                "grounded_rate": rate([s.is_grounded for s in self.ip5]),
                "threshold": 0.90, "metric": "avg_groundedness (= 1 - hallucination)",
            },
        }


# ── Harness ──────────────────────────────────────────────────────────────────────

class IPMetricsHarness:
    def __init__(self, llm_fn: LLMCallable, verifier_llm: Optional[LLMCallable] = None,
                 throttle_s: float = 0.0, max_claims: int = 3) -> None:
        from domain.rule_engine.rule_engine import RuleEngine
        self._llm = llm_fn
        self._verifier_llm = verifier_llm or llm_fn
        self.throttle_s = throttle_s
        self.max_claims = max_claims
        self.engine = RuleEngine(_RULES_PATH)

    # İP-6
    def _measure_ip6(self, sc: Scenario) -> IP6Sample:
        from llm.agents.task_planner import TaskPlanner
        planner = TaskPlanner(rule_engine=self.engine, llm_fn=self._llm)
        plan = planner.plan(sc.goal, os_target=sc.os_target, security_level=sc.security_level)
        ids = [i.rule_id for i in plan.items]
        return IP6Sample(
            goal=sc.goal, selected_ids=ids,
            ordering_ok=ordering_score([i.order for i in plan.items]),
            selection_prec=selection_precision(ids, sc.expected_section_prefixes),
            n_items=len(plan.items), n_conflicts=len(plan.conflicts),
        )

    # İP-7
    def _measure_ip7(self, sc: Scenario) -> IP7Sample:
        from llm.agents.hardening_agent import HardeningAgent
        agent = HardeningAgent(rule_engine=self.engine, llm_fn=self._llm)
        res = agent.run(sc.goal, os_target=sc.os_target, security_level=sc.security_level, fmt="bash")
        names = [s.name for s in res.steps]
        return IP7Sample(
            goal=sc.goal, success=res.success,
            steps_ok=steps_complete(names),
            verify_present="verify" in names,
            all_steps_ok_flag=all(s.ok for s in res.steps),
            n_steps=len(res.steps),
        )

    # İP-8
    def _measure_ip8(self, sc: Scenario) -> IP8Sample:
        from llm.pipelines.layers.zt_enrichment import ZeroTrustEnricher
        from llm.core.context import RequestContext
        enricher = ZeroTrustEnricher(llm=self._llm)
        ctx = RequestContext(user_question=sc.goal, os=sc.os_target,
                             security_level=sc.security_level)  # type: ignore
        zt = enricher.enrich(ctx)
        return IP8Sample(
            goal=sc.goal,
            principle_valid=zt_principle_valid(zt.zt_principles),
            standard_ref=has_standard_ref(zt.standards),
            principles=list(zt.zt_principles), standards=list(zt.standards),
        )

    # İP-5
    def _measure_ip5(self, sc: Scenario) -> IP5Sample:
        from rag.verify.claim_verifier import ClaimVerifier
        from llm.rag.integration import RAGContextBuilder
        from llm.prompts.simple_prompts import GROUNDING_DIRECTIVE
        # gerçek bağlam çek — os_version geçilir ki Ubuntu hedefi Windows chunk'ı çekmesin
        # (teşhis: os_version'sız retrieval Ubuntu hedefine Win CIS chunk'ları getiriyordu).
        try:
            rag = RAGContextBuilder(top_k=5, min_score=0.4, os_version=sc.os_target)
            _ctx, chunks = rag.retrieve_balanced(sc.goal)
        except Exception as exc:
            logger.warning("[İP-5] RAG retrieval başarısız: %s", exc)
            chunks = []
        # Bağlam KISALTILMAZ: önceki 600-kr kesme modeli aç bırakıp bağlam-dışı bilgi
        # uydurmaya itiyordu (halüsinasyon ↑). Üretimle AYNI GROUNDING_DIRECTIVE uygulanır
        # → İP-5, ürünün gerçek bağlam-bağlılığı politikasını ölçer (test'e özel prompt değil).
        ctx_txt = "\n\n".join(c.get("text", "") for c in chunks)
        if chunks:
            prompt = (f"SORU: '{sc.goal}' için kısa, teknik bir sıkılaştırma önerisi yaz.\n\n"
                      f"CIS BENCHMARK REFERANSLARI:\n{ctx_txt}\n"
                      f"{GROUNDING_DIRECTIVE}\n\nYANIT:")
        else:
            prompt = f"'{sc.goal}' için kısa öneri:"
        answer = self._llm(prompt)
        # İP-5 ölçümü TAM bağlama karşı doğrular (üretim cost-bound varsayılanları yerine):
        # iddialar tüm chunk'lara karşı denetlenir → kesme kaynaklı sahte-negatif olmaz.
        cv = ClaimVerifier(llm_fn=self._verifier_llm, min_confidence=0.9,
                           max_claims=self.max_claims,
                           max_chunk_chars=4000, max_context_chars=24000)
        vr = cv.verify(answer, chunks)
        return IP5Sample(goal=sc.goal, groundedness=round(vr.confidence, 4),
                         is_grounded=vr.confidence >= 0.9, n_chunks=len(chunks))

    def run(self, scenarios: Optional[List[Scenario]] = None) -> IPReport:
        scenarios = scenarios or SCENARIOS
        rep = IPReport()
        for i, sc in enumerate(scenarios, 1):
            logger.info("[İP] (%d/%d) %s", i, len(scenarios), sc.goal[:55])
            for measure, bucket in (
                (self._measure_ip6, rep.ip6), (self._measure_ip7, rep.ip7),
                (self._measure_ip8, rep.ip8), (self._measure_ip5, rep.ip5),
            ):
                try:
                    bucket.append(measure(sc))
                except Exception as exc:
                    logger.warning("[İP] ölçüm atlandı (%s): %s", measure.__name__, exc)
            if self.throttle_s and i < len(scenarios):
                time.sleep(self.throttle_s)
        return rep


# ── Raporlama ───────────────────────────────────────────────────────────────────

def to_markdown(rep: IPReport) -> str:
    s = rep.summary()
    L = [
        "# İP-5/6/7/8 — Sayısal Başarı Ölçümü (öneri formu iş paketleri)",
        "",
        "**Yöntem:** Küratörlü senaryo seti üzerinde gerçek modüller (TaskPlanner, "
        "HardeningAgent, ZeroTrustEnricher, ClaimVerifier) koşturulur; çıktılar saf "
        "(deterministik) skorlama fonksiyonlarıyla ölçülür. Sağlayıcı: canlı LLM.",
        "",
        "| İP | Metrik | Sonuç | Eşik | Durum |",
        "|----|--------|------:|-----:|:-----:|",
    ]
    rows = [
        ("İP-6 Görev Planlayıcı", s["ip6"]["ordering_pass_rate"], 0.80, "sıralama doğruluğu"),
        ("İP-7 Multi-step ajan", s["ip7"]["success_rate"], 0.75, "success oranı"),
        ("İP-8 ZT Açıklayıcı", s["ip8"]["combined_rate"], 0.80, "geçerli prensip+standart"),
        ("İP-5 Groundedness", s["ip5"]["avg_groundedness"], 0.90, "1 - halüsinasyon"),
    ]
    for label, val, thr, metric in rows:
        ok = "✅" if val >= thr else "⚠️"
        L.append(f"| {label} | {metric} | {val:.3f} | {thr:.2f} | {ok} |")
    L += [
        "",
        f"- **İP-6:** ordering pass {s['ip6']['ordering_pass_rate']:.0%}, "
        f"ort. seçim isabeti {s['ip6']['avg_selection_precision']:.0%} (n={s['ip6']['n']})",
        f"- **İP-7:** success {s['ip7']['success_rate']:.0%}, "
        f"adım-tamlık {s['ip7']['steps_complete_rate']:.0%}, "
        f"verify-gate {s['ip7']['verify_gate_rate']:.0%} (n={s['ip7']['n']})",
        f"- **İP-8:** geçerli prensip {s['ip8']['valid_principle_rate']:.0%}, "
        f"standart referans {s['ip8']['standard_ref_rate']:.0%}, "
        f"birleşik {s['ip8']['combined_rate']:.0%} (n={s['ip8']['n']})",
        f"- **İP-5:** ort. groundedness {s['ip5']['avg_groundedness']:.3f} "
        f"→ halüsinasyon ≈ %{(1 - s['ip5']['avg_groundedness']) * 100:.1f} (n={s['ip5']['n']})",
        "",
        "> **Sınır:** İP-8 'doğru eşleşme' semantiktir; burada *geçerli ZT prensibi + "
        "standart referansı varlığı* proxy olarak ölçülür. İP-5 groundedness = "
        "ClaimVerifier'ın iddiaların bağlamca desteklenme oranı.",
    ]
    return "\n".join(L)


def save_results(rep: IPReport, out_dir: str | Path = "evaluation/results") -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "ip_metrics_report.md").write_text(to_markdown(rep), encoding="utf-8")
    payload = {
        "summary": rep.summary(),
        "ip6": [vars(x) for x in rep.ip6],
        "ip7": [vars(x) for x in rep.ip7],
        "ip8": [vars(x) for x in rep.ip8],
        "ip5": [vars(x) for x in rep.ip5],
    }
    (out / "ip_metrics_results.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def print_report(rep: IPReport) -> None:
    s = rep.summary()
    print("\n" + "=" * 64)
    print("IP-5/6/7/8 SAYISAL OLCUM")
    print("=" * 64)
    print(f"IP-6 siralama dogrulugu : {s['ip6']['ordering_pass_rate']:.3f}  (esik 0.80)")
    print(f"IP-7 success orani      : {s['ip7']['success_rate']:.3f}  (esik 0.75)")
    print(f"IP-8 prensip+standart   : {s['ip8']['combined_rate']:.3f}  (esik 0.80)")
    print(f"IP-5 groundedness       : {s['ip5']['avg_groundedness']:.3f}  (esik 0.90)")
    print("=" * 64)


def main() -> None:
    from evaluation import force_utf8_output
    force_utf8_output()                       # Türkçe log Windows'ta bozulmasın
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    from llm.clients import get_llm_clients
    small, large = get_llm_clients()

    sample = int(os.environ.get("IP_SAMPLE", "0")) or len(SCENARIOS)
    throttle = float(os.environ.get("IP_THROTTLE_S", "3"))
    max_claims = int(os.environ.get("IP_MAX_CLAIMS", "4"))

    harness = IPMetricsHarness(llm_fn=large, verifier_llm=small,
                               throttle_s=throttle, max_claims=max_claims)
    rep = harness.run(SCENARIOS[:sample])

    out = save_results(rep)  # önce kaydet (konsol encode hatası sonuçları kaybetmesin)
    print(f"Rapor: {out / 'ip_metrics_report.md'} ve {out / 'ip_metrics_results.json'}")
    try:
        print_report(rep)
    except Exception as exc:  # pragma: no cover
        print(f"(konsol ozeti yazdirilamadi: {exc})")


if __name__ == "__main__":
    main()
