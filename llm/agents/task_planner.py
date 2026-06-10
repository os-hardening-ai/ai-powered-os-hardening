"""
İP-6 — Görev Planlayıcı (Task Planner)

Öneri formu: "LLM tabanlı görev planlayıcı ... önerileri önem/bağımlılık
sırasına göre maddeleştirir."

Tasarım — LLM + RuleEngine hibrit:
  1. security_level → ilgili CIS Level kuralları (aday havuzu) RuleEngine'den.
  2. LLM, kullanıcı hedefine uygun kuralları SEÇER ve önceliklendirir
     (priority + rationale + risk).  → açıklanabilirlik
  3. RuleEngine seçilen kuralları DETERMINISTIK sıraya dizer (CIS bölüm no)
     ve çakışmaları (aynı config dosyası / kernel modülü) tespit eder.
  4. Sonuç: sıralı, gerekçeli, çakışma-uyarılı bir HardeningPlan.

LLM verilmezse (llm_fn=None) ya da LLM hata verirse, plan tamamen
RuleEngine'den deterministik olarak üretilir (graceful degradation).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from domain.rule_engine.rule_engine import RuleEngine, RuleConflict

logger = logging.getLogger(__name__)

LLMCallable = Callable[[str], str]

# security_level → değerlendirilecek CIS Level'ları
_LEVEL_MAP: Dict[str, List[int]] = {
    "minimal": [1],
    "balanced": [1],
    "strict": [1, 2],
}

# LLM'e gönderilecek (ve deterministik fallback'te kullanılacak) aday sayısı.
# Tüm level kuralları hedefe göre alaka sırasına dizilir; en alakalı ilk N tanesi
# LLM prompt'una girer → küçük prompt = düşük latency + odaklı seçim.
_LLM_CANDIDATES = 24

# Türkçe diakritik → ASCII (lexical eşleştirmeyi dil-bağımsız yapar)
_TR_FOLD = str.maketrans("çğıöşüâîû", "cgiosuaiu")

# Eşleştirmede gürültü yapan dolgu kelimeleri
_STOPWORDS = {
    "ve", "ile", "icin", "için", "bir", "bu", "su", "su", "the", "and", "for",
    "ayarla", "yap", "yapilandir", "yapılandır", "sikilastir", "sıkılaştır",
    "politika", "politikasi", "politikası", "ayarlar", "ayarlari",
}

# TR hedef kelimesi → ilgili (genelde İngilizce) CIS terimleri.
# Anahtarlar ASCII-fold edilmiş halde tutulur (tokenizer da fold uygular).
_SYNONYMS: Dict[str, set] = {
    "ssh": {"ssh", "sshd"},
    "parola": {"password", "passwd", "pam", "pwquality", "shadow"},
    "sifre": {"password", "passwd", "pwquality"},
    "guvenlik": {"security"},
    "duvari": {"firewall", "ufw", "iptables", "nftables"},
    "atesduvari": {"firewall", "ufw", "iptables", "nftables"},
    "firewall": {"firewall", "ufw", "iptables", "nftables"},
    "cekirdek": {"kernel", "module", "modprobe", "sysctl"},
    "kernel": {"kernel", "module", "modprobe", "sysctl"},
    "network": {"network", "ipv4", "ipv6", "tcp"},
    "denetim": {"audit", "auditd"},
    "audit": {"audit", "auditd"},
    "gunluk": {"log", "logging", "syslog", "journald", "rsyslog"},
    "log": {"log", "logging", "syslog", "journald", "rsyslog"},
    "dosya": {"file", "filesystem", "mount", "partition"},
    "kullanici": {"user", "account", "sudo"},
    "zaman": {"time", "ntp", "chrony", "timesync"},
    "servis": {"service", "daemon", "systemd"},
    "hizmet": {"service", "daemon", "systemd"},
    "izin": {"permission", "chmod", "umask"},
}


def _fold(text: str) -> str:
    return text.lower().translate(_TR_FOLD)


def _tokenize(text: str) -> set:
    """ASCII-fold + sözcüklere ayır; kısa token ve dolgu kelimelerini at."""
    folded = _fold(text)
    return {
        t for t in re.split(r"[^a-z0-9]+", folded)
        if len(t) >= 3 and t not in _STOPWORDS
    }


def _expand(tokens: set) -> set:
    """Hedef token'larını eşanlamlı CIS terimleriyle genişlet (TR↔EN köprüsü)."""
    expanded = set(tokens)
    for tok in tokens:
        if tok in _SYNONYMS:
            expanded |= _SYNONYMS[tok]
    return expanded


def _rule_relevance(goal_tokens: set, rule: dict) -> int:
    """Kuralın hedefle leksik örtüşme skoru (ortak token sayısı). 0 = alakasız."""
    hay = _tokenize(" ".join([
        str(rule.get("title", "")),
        str(rule.get("category", "")),
        " ".join(rule.get("tags", []) or []),
        str(rule.get("description", "")),
    ]))
    return len(goal_tokens & hay)


@dataclass
class PlanItem:
    rule_id: str
    title: str
    order: int                       # uygulama sırası (1'den başlar)
    priority: int = 3                # 1=en yüksek .. 5=en düşük (LLM)
    rationale: str = ""              # neden bu kural? (LLM)
    risk: str = "medium"             # low/medium/high (LLM)
    zt_principle: str = ""           # kural metadata'sından
    nist_ref: str = ""               # kural metadata'sından


@dataclass
class HardeningPlan:
    goal: str
    os_target: str
    security_level: str
    items: List[PlanItem] = field(default_factory=list)
    conflicts: List[RuleConflict] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "goal": self.goal,
            "os_target": self.os_target,
            "security_level": self.security_level,
            "summary": self.summary,
            "items": [item.__dict__ for item in self.items],
            "conflicts": [c.__dict__ for c in self.conflicts],
            "warnings": self.warnings,
        }


class TaskPlanner:
    """
    İP-6 Görev Planlayıcı.

    Kullanım:
        engine = RuleEngine("data/rules/ubuntu_24_04_rules.yaml")
        planner = TaskPlanner(llm_fn=groq_small, rule_engine=engine)
        plan = planner.plan("SSH ve parola politikasını sıkılaştır",
                            os_target="ubuntu_24_04", security_level="strict")
    """

    def __init__(
        self,
        rule_engine: RuleEngine,
        llm_fn: Optional[LLMCallable] = None,
        debug: bool = False,
    ) -> None:
        self.rule_engine = rule_engine
        self.llm = llm_fn
        self.debug = debug

    # ── public API ────────────────────────────────────────────────────────────

    def plan(
        self,
        goal: str,
        os_target: str = "ubuntu_24_04",
        security_level: str = "balanced",
    ) -> HardeningPlan:
        candidates = self._candidate_rules(security_level)
        if not candidates:
            logger.warning("[TaskPlanner] Aday kural bulunamadı (level=%s)", security_level)
            return HardeningPlan(
                goal=goal, os_target=os_target, security_level=security_level,
                summary="Bu güvenlik seviyesi için uygun kural bulunamadı.",
            )

        # 0) Adayları hedefe göre alaka sırasına diz ve LLM prompt'u için kıs.
        #    (Tüm level kuralları sıralanır → bölüm-sırası kaynaklı "ilk 60" hatası
        #     ortadan kalkar; SSH gibi geç bölümdeki kurallar da aday olabilir.)
        goal_tokens = _expand(_tokenize(goal))
        llm_pool = self._rank_candidates(goal, candidates)[:_LLM_CANDIDATES]

        # 1) LLM ile seçim + önceliklendirme (varsa). parsed_ok = LLM geçerli JSON üretti mi.
        selections, llm_parsed_ok = (
            self._llm_select(goal, llm_pool) if self.llm else ({}, False)
        )

        # ── ALAKA TABANI (relevance floor) — katalog-miss tespiti ───────────────────
        # Katalog-miss = LLM VAR + "hiç ilgili kural yok" ([]) dedi + hedef katalogla
        # leksik olarak da örtüşmüyor (apache/nginx/docker gibi katalog-DIŞI iş). Bu durumda
        # ALAKASIZ kural dökmek yerine boş plan + 'no_relevant_rules' dön; HardeningAgent bunu
        # görüp serbest-form (LLM) üretime yönlendirir ("CIS kuralı yoksa LLM'den üret").
        # NOT: self.llm yoksa (offline/test) eski recall davranışı korunur → jenerik hedefler
        # ("tüm sıkılaştırma", "hepsi") yanlışlıkla katalog-dışı sayılmaz.
        catalog_relevant = (
            any(_rule_relevance(goal_tokens, r) > 0 for r in candidates) if goal_tokens else True
        )
        if self.llm and llm_parsed_ok and not selections and not catalog_relevant:
            return HardeningPlan(
                goal=goal, os_target=os_target, security_level=security_level,
                summary=f"'{goal}' için katalogda uygun CIS kuralı bulunamadı "
                        "(katalog OS-seviyesi sıkılaştırmayı kapsar; katalog-dışı istek "
                        "serbest-form üretilir).",
                warnings=["no_relevant_rules"],
            )

        # 2) Seçilen kural id'leri (LLM boşsa → alaka-sıralı havuz, recall korunur).
        if selections:
            selected_ids = [rid for rid in selections if self.rule_engine.get_rule(rid)]
        else:
            selected_ids = [r["id"] for r in llm_pool]

        if not selected_ids:
            selected_ids = [r["id"] for r in llm_pool]

        # 3) RuleEngine: deterministik sıra + çakışma tespiti
        exec_plan = self.rule_engine.get_execution_plan(selected_ids)

        # 4) PlanItem listesi (uygulama sırasına göre, metadata + LLM zenginleştirmesi)
        items: List[PlanItem] = []
        for order, rid in enumerate(exec_plan.ordered_rules, start=1):
            rule = self.rule_engine.get_rule(rid) or {}
            sel = selections.get(rid, {})
            items.append(PlanItem(
                rule_id=rid,
                title=rule.get("title", ""),
                order=order,
                priority=int(sel.get("priority", 3)),
                rationale=str(sel.get("rationale", "")).strip(),
                risk=str(sel.get("risk", rule.get("impact", "medium"))).lower(),
                zt_principle=str(rule.get("zt_principle", "")),
                nist_ref=str(rule.get("nist_ref", "")),
            ))

        summary = (
            f"{os_target} için '{goal}' hedefiyle {len(items)} kural seçildi "
            f"({security_level} seviye). {len(exec_plan.conflicts)} olası çakışma tespit edildi."
        )

        return HardeningPlan(
            goal=goal,
            os_target=os_target,
            security_level=security_level,
            items=items,
            conflicts=exec_plan.conflicts,
            warnings=exec_plan.warnings,
            summary=summary,
        )

    # ── internal helpers ────────────────────────────────────────────────────────

    def _candidate_rules(self, security_level: str) -> List[dict]:
        levels = _LEVEL_MAP.get(security_level, [1])
        seen: Dict[str, dict] = {}
        for lvl in levels:
            for rule in self.rule_engine.list_rules(level=lvl):
                seen[rule["id"]] = rule
        # Tam level havuzu döner; kısma (alaka-sıralaması sonrası) plan()'da yapılır.
        return list(seen.values())

    def _rank_candidates(self, goal: str, candidates: List[dict]) -> List[dict]:
        """Adayları hedefle leksik örtüşmeye göre sırala (alakalı önce, kalanı korunur).

        Eşleşme yoksa orijinal sıra korunur — böylece recall asla kaybolmaz,
        yalnızca alakalı kurallar öne çekilir.
        """
        goal_tokens = _expand(_tokenize(goal))
        if not goal_tokens:
            return list(candidates)

        # Stabil sıralama: yüksek skor önce, eşitlikte orijinal sıra (CIS bölüm no).
        indexed = list(enumerate(candidates))
        indexed.sort(key=lambda pair: (-_rule_relevance(goal_tokens, pair[1]), pair[0]))
        return [rule for _, rule in indexed]

    def _llm_select(self, goal: str, candidates: List[dict]) -> "tuple[Dict[str, dict], bool]":
        """LLM'e adayları verir; (seçim_dict, parsed_ok) döndürür. parsed_ok=True →
        LLM geçerli JSON dizisi üretti (boş [] = 'hiç ilgili kural yok')."""
        catalog = "\n".join(
            f"- {r['id']}: {r.get('title', '')}" for r in candidates
        )
        prompt = (
            "Sen bir güvenlik sıkılaştırma uzmanısın. Kullanıcının hedefi için "
            "aşağıdaki CIS kurallarından UYGUN olanları seç ve önceliklendir.\n\n"
            f"HEDEF: {goal}\n\n"
            f"ADAY KURALLAR:\n{catalog}\n\n"
            "Sadece geçerli JSON dizisi döndür (markdown yok). Her öğe:\n"
            '{"rule_id": "<id>", "priority": 1-5, "risk": "low|medium|high", '
            '"rationale": "tek cümle gerekçe"}\n'
            "priority 1 = en kritik/önce uygulanmalı. Yalnızca hedefle ilgili kuralları dahil et.\n"
            "Hedefle ilgili HİÇBİR kural yoksa (ör. katalog-dışı bir konu) BOŞ dizi [] döndür; "
            "ASLA alakasız kural ekleme."
        )
        try:
            raw = self.llm(prompt)  # type: ignore[misc]
            items, parsed_ok = _parse_json_array(raw)
            result: Dict[str, dict] = {}
            for it in items:
                rid = str(it.get("rule_id", "")).strip()
                if rid:
                    result[rid] = it
            if self.debug:
                logger.info("[TaskPlanner] LLM %d kural seçti", len(result))
            return result, parsed_ok
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("[TaskPlanner] LLM seçimi başarısız, deterministik fallback: %s", exc)
            return {}, False


def _parse_json_array(text: str) -> "tuple[List[dict], bool]":
    """(öğeler, parsed_ok) döndürür. parsed_ok=True → metin GEÇERLİ bir JSON dizisi
    içeriyordu (boş [] olsa bile = LLM bilerek 'hiç kural yok' dedi). False → dizi
    bulunamadı / JSON bozuk (LLM seçim formatı üretmedi → katalog-miss SAYILMAZ)."""
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return [], False
    try:
        data = json.loads(match.group())
        return [d for d in data if isinstance(d, dict)], True
    except (json.JSONDecodeError, TypeError):
        return [], False
