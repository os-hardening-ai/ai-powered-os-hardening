"""
İP-7 — Multi-step Reasoning / Tool-Use Ajanı (HardeningAgent)

Öneri formu: "Ajanın çok-adımlı akıl yürütme (multi-step reasoning) ... self-verify
modülü devreye alınır."

Ajan, bir sıkılaştırma hedefini birden çok ARACI sırayla kullanarak çözer:

    1. PLAN      → TaskPlanner (İP-6): hedefe uygun kuralları seç + sırala
    2. COLLECT   → RuleEngine: seçilen kuralların tam tanımlarını topla
    3. GENERATE  → ArtifactGenerator: uygulanabilir script üret (bash/ps/ansible)
    4. VERIFY    → OutputValidator: tehlikeli komut / kalite self-verify
    5. REFINE    → güvensizse tehlikeli kuralı çıkar ve YENİDEN üret (gözlem→
                   akıl yürütme→yeniden eylem), en fazla `max_refine` kez
    6. SYNTAX    → üretilen script'i FİİLEN doğrula (`bash -n` / `yaml.load`);
                   bozuksa (a) bozuk kuralı izole edip çıkar→yeniden üret
                   (deterministik), (b) hâlâ bozuksa LLM'e geri besleyip onar
                   (son çare, tam yeniden-doğrulamalı), en fazla `max_syntax_fix` kez

Her adım bir AgentStep olarak kaydedilir → açıklanabilir, denetlenebilir iz.
Araçların çoğu (rule_engine, artifact_generator, validator, bash -n) deterministik
çalışır; LLM yalnızca planlama (İP-6), opsiyonel özet ve son-çare sözdizimi onarımı
için kullanılır.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

from domain.rule_engine.rule_engine import RuleEngine
from domain.artifact_generator.generator import ArtifactGenerator, Artifact
from llm.pipelines.layers.output_validator import OutputValidator
from llm.agents.task_planner import TaskPlanner, HardeningPlan
from llm.agents.freeform_generator import FreeformScriptGenerator

logger = logging.getLogger(__name__)

LLMCallable = Callable[[str], str]


# Katalogda karşılığı olmayan, kullanıcıya-özel EYLEM sinyalleri (TR + EN). Bunlar CIS
# benchmark kuralı değil, operasyonel görevdir (grup/kullanıcı oluştur, belirli isimli
# kaynak ekle). Varlıkları + katalog kurallarının bunu KARŞILAMAMASI → serbest-form.
# Türkçe ekleri (grubu/grubuna) yakalamak için kök-bazlı: "grup"+"oluştur" AYNI cümlede
# yeterli (alt-dizge "grup oluştur" eklerde kaçar). Bu yüzden çok-token kontrolü _has_pair ile.
_FREEFORM_ACTION_MARKERS = (
    "groupadd", "useradd", "usermod", "adduser", "addgroup",
    "create group", "add group", "create user", "add user", "create account",
    "mkdir", "symlink", "crontab",
)
# (kök, eylem) çiftleri — ikisi de hedefte geçerse katalog-dışı operasyonel iş.
_FREEFORM_PAIRS = (
    ("grup", "oluştur"), ("grub", "oluştur"), ("grup", "ekle"), ("grub", "ekle"),
    ("kullanıcı", "oluştur"), ("kullanıcı", "ekle"), ("hesap", "oluştur"),
    ("kullanıc", "ekle"), ("dizin", "oluştur"), ("klasör", "oluştur"),
)


def _is_catalog_miss(goal: str, plan: "HardeningPlan") -> bool:
    """Hedef CIS kataloğuyla karşılanamayan ÖZEL bir operasyonel iş mi? (deterministik)

    True → serbest-form script üret. Konservatif: yalnız NET katalog-miss'te True
    (şüphede katalog kalır → mevcut davranış bozulmaz). Sinyal:
      katalogda-olmayan-eylem sözcüğü (groupadd/useradd/grup oluştur...) VAR ve
      seçilen kuralların başlık/açıklamaları bu eylemi KARŞILAMIYOR.
    """
    g = (goal or "").lower()
    has_action = (
        any(m in g for m in _FREEFORM_ACTION_MARKERS)
        or any(root in g and verb in g for root, verb in _FREEFORM_PAIRS)
    )
    if not has_action:
        return False
    # Plan kuralları bu eylemi karşılıyor mu? (kural başlık/kategorilerinde grup/kullanıcı
    # oluşturma geçiyorsa katalog yeterli sayılır → freeform'a gerek yok).
    catalog_text = " ".join(
        f"{i.title} {getattr(i, 'rationale', '')}" for i in (plan.items or [])
    ).lower()
    catalog_covers = any(
        kw in catalog_text for kw in ("groupadd", "useradd", "grup oluştur", "kullanıcı oluştur",
                                      "create group", "create user", "add group", "add user")
    )
    return has_action and not catalog_covers


@dataclass
class AgentStep:
    """Tek bir akıl yürütme/araç adımı (denetim izi)."""
    name: str            # plan | collect | generate | verify | refine | summarize
    tool: str            # kullanılan aracın adı
    detail: str          # insan-okunur özet
    ok: bool = True


@dataclass
class AgentResult:
    success: bool
    goal: str
    os_target: str
    fmt: str
    plan: Optional[HardeningPlan] = None
    artifact: Optional[Artifact] = None
    issues: List[str] = field(default_factory=list)
    steps: List[AgentStep] = field(default_factory=list)
    summary: str = ""
    mode: str = "catalog"   # "catalog" (CIS kural seçimi) | "freeform" (özel script)


class HardeningAgent:
    """
    İP-7 çok-adımlı tool-use ajanı.

    Kullanım:
        agent = HardeningAgent(rule_engine=engine, llm_fn=groq_small)
        result = agent.run("SSH'i sıkılaştır", os_target="ubuntu_24_04",
                           security_level="strict", fmt="bash")
        print(result.artifact.content)
        for s in result.steps: print(s.name, s.detail)
    """

    def __init__(
        self,
        rule_engine: RuleEngine,
        llm_fn: Optional[LLMCallable] = None,
        artifact_generator: Optional[ArtifactGenerator] = None,
        task_planner: Optional[TaskPlanner] = None,
        max_refine: int = 1,
        max_syntax_fix: int = 1,
        debug: bool = False,
    ) -> None:
        self.rule_engine = rule_engine
        self.llm = llm_fn
        self.artifact_generator = artifact_generator or ArtifactGenerator()
        self.planner = task_planner or TaskPlanner(rule_engine=rule_engine, llm_fn=llm_fn, debug=debug)
        # Regex-only validator (no LLM needed for the safety self-verify gate)
        self.validator = OutputValidator(use_llm_validation=False, debug=debug)
        self.max_refine = max_refine
        # Sözdizimi self-verify döngüsünde en fazla kaç onarım denemesi (izolasyon+LLM)
        self.max_syntax_fix = max_syntax_fix
        self.debug = debug
        self._danger_re = [re.compile(p, re.IGNORECASE) for p in OutputValidator.DANGEROUS_COMMANDS]

    def run(
        self,
        goal: str,
        os_target: str = "ubuntu_24_04",
        security_level: str = "balanced",
        fmt: str = "bash",
    ) -> AgentResult:
        steps: List[AgentStep] = []

        # ── Step 1: PLAN (tool: TaskPlanner / İP-6) ──
        plan = self.planner.plan(goal, os_target=os_target, security_level=security_level)
        steps.append(AgentStep(
            "plan", "TaskPlanner",
            f"{len(plan.items)} kural seçildi, {len(plan.conflicts)} olası çakışma",
            ok=bool(plan.items),
        ))

        # ── KATALOG-MISS DALLANMASI ──
        # Kullanıcı katalogda karşılığı OLMAYAN özel bir iş istediyse (ör. "dev grubu
        # oluştur") katalog kuralları dökmek yerine SERBEST-FORM script üret. Heuristik
        # deterministik (LLM'siz); şüphede KATALOG kalır (mevcut davranış bozulmaz).
        # Katalog-miss → serbest-form (LLM) üretim. İki sinyal:
        #  (a) operasyonel iş heuristiği (grup/kullanıcı oluştur vb.), VEYA
        #  (b) TaskPlanner alaka tabanı: hedefe uygun CIS kuralı yok ('no_relevant_rules').
        #      (apache/nginx/docker gibi katalog-dışı talepler → alakasız kural dökmek yerine
        #       hedefe-özel script LLM'den üretilir; güvenlik kapısı + bash -n yine uygulanır.)
        if _is_catalog_miss(goal, plan) or "no_relevant_rules" in (plan.warnings or []):
            return self._run_freeform(goal, os_target, security_level, fmt, plan, steps)

        if not plan.items:
            return AgentResult(
                success=False, goal=goal, os_target=os_target, fmt=fmt,
                plan=plan, steps=steps,
                summary="Hedef için uygulanabilir kural bulunamadı.",
            )

        selected_ids = [item.rule_id for item in plan.items]

        # ── Steps 2-5: COLLECT → GENERATE → VERIFY → (REFINE) döngüsü ──
        artifact: Optional[Artifact] = None
        validation = None
        for attempt in range(self.max_refine + 1):
            # Step 2: COLLECT (tool: RuleEngine)
            rules = [r for r in (self.rule_engine.get_rule(rid) for rid in selected_ids) if r]
            if attempt == 0:
                steps.append(AgentStep("collect", "RuleEngine", f"{len(rules)} kural tanımı toplandı"))

            # Step 3: GENERATE (tool: ArtifactGenerator)
            artifact = self.artifact_generator.generate(rules, fmt, os_target, security_level)
            steps.append(AgentStep(
                "generate", "ArtifactGenerator",
                f"{artifact.rule_count} kural → {fmt} script ({len(artifact.content)} karakter)",
                ok=artifact.rule_count > 0,
            ))

            # Step 4: VERIFY (tool: OutputValidator — tehlikeli komut self-verify)
            # intent=info_request: kod-bloğu zorunluluğunu atlar, tehlikeli komut +
            # uzunluk kontrollerini uygular (artifact ham script, markdown değil).
            validation = self.validator.validate(artifact.content, intent="info_request")
            steps.append(AgentStep(
                "verify", "OutputValidator",
                "güvenli" if validation.is_valid else f"{len(validation.issues)} sorun: {validation.issues[:2]}",
                ok=validation.is_valid,
            ))

            if validation.is_valid:
                break

            # Step 5: REFINE — gözlem→akıl yürütme→yeniden eylem
            if attempt < self.max_refine:
                dangerous_ids = self._find_dangerous_rules(selected_ids)
                if not dangerous_ids:
                    break  # sorun tehlikeli komuttan değil → refine fayda etmez
                selected_ids = [rid for rid in selected_ids if rid not in dangerous_ids]
                steps.append(AgentStep(
                    "refine", "HardeningAgent",
                    f"Tehlikeli komut içeren {len(dangerous_ids)} kural çıkarıldı, yeniden üretiliyor: {sorted(dangerous_ids)}",
                ))
                if not selected_ids:
                    # Tüm kurallar tehlikeli çıktı → uygulanabilir güvenli kural kalmadı.
                    # Önceki iterasyonun TEHLİKELİ artifact'ını DÖNDÜRME (güvenlik): temizle.
                    artifact = self.artifact_generator.generate([], fmt, os_target, security_level)
                    steps.append(AgentStep(
                        "verify", "OutputValidator",
                        "tüm kurallar tehlikeli komut içeriyordu → güvenli script üretilemedi",
                        ok=False,
                    ))
                    validation = None
                    break

        # ── Step 6: SYNTAX self-verify + onarım (agentic üret→doğrula→düzelt döngüsü) ──
        # GENERATE deterministik GEÇERLİ iskelet üretir; fakat bir kuralın HAM remediation
        # içeriği bozuk olabilir (dengesiz tırnak/parantez) → tüm script `bash -n`'de patlar.
        # Burada script'i FİİLEN doğrularız; hata varsa önce bozuk kuralı izole edip çıkarır
        # (deterministik, güvenli), son çare olarak LLM'e geri besleyip onarmayı deneriz.
        syntax_issues: List[str] = []
        syntax_ok = True
        if artifact and artifact.content and artifact.rule_count > 0:
            ok, err = self._syntax_check(artifact.content, fmt)
            steps.append(AgentStep(
                "syntax", "bash -n / yaml.load",
                "sözdizimi geçerli" if ok else f"sözdizimi hatası: {err[:100]}", ok=ok,
            ))
            if not ok:
                # (a) DETERMİNİSTİK onarım: hangi kural tek başına `bash -n`'de patlıyor →
                #     onu çıkar, yeniden üret. LLM yok, semantik bozulmaz, kesinti riski yok.
                bad_ids = self._isolate_broken_rule_ids(selected_ids, fmt, os_target, security_level)
                if bad_ids:
                    selected_ids = [rid for rid in selected_ids if rid not in bad_ids]
                    steps.append(AgentStep(
                        "refine", "syntax-isolate",
                        f"sözdizimi bozuk {len(bad_ids)} kural çıkarıldı → yeniden üretiliyor: {sorted(bad_ids)}",
                    ))
                    rules = [r for r in (self.rule_engine.get_rule(rid) for rid in selected_ids) if r]
                    artifact = self.artifact_generator.generate(rules, fmt, os_target, security_level)
                    ok, err = self._syntax_check(artifact.content, fmt)
                    steps.append(AgentStep(
                        "syntax", "bash -n / yaml.load",
                        "sözdizimi geçerli" if ok else f"sözdizimi hatası: {err[:100]}", ok=ok,
                    ))
                # (b) hâlâ bozuk + LLM var + script makul boyutta → LLM-repair (son çare)
                if not ok and self.llm and len(artifact.content) <= 6000:
                    repaired = self._llm_repair(artifact.content, err, fmt)
                    if repaired and repaired.strip() and repaired != artifact.content:
                        # GÜVENLİK: LLM onarımı yeni tehlikeli komut sokmuş VEYA hâlâ bozuk olabilir
                        # → tehlikeli-komut + sözdizimini YENİDEN doğrula, ikisi de geçerse kabul et.
                        rep_val = self.validator.validate(repaired, intent="info_request")
                        rep_ok, _ = self._syntax_check(repaired, fmt)
                        if rep_val.is_valid and rep_ok:
                            artifact = Artifact(
                                format=artifact.format, content=repaired,
                                rule_count=artifact.rule_count, os_target=artifact.os_target,
                                warnings=artifact.warnings,
                            )
                            ok = True
                            steps.append(AgentStep(
                                "refine", "LLM-repair",
                                "sözdizimi LLM ile onarıldı ve yeniden doğrulandı", ok=True,
                            ))
                        else:
                            steps.append(AgentStep(
                                "refine", "LLM-repair",
                                "onarım reddedildi (tehlikeli komut eklendi / hâlâ geçersiz) → orijinal korunuyor",
                                ok=False,
                            ))
                if not ok:
                    # Onaramadık → bozuk script'i SESSİZCE sunma: şeffafça işaretle, success=False.
                    syntax_ok = False
                    syntax_issues.append(f"Sözdizimi doğrulaması başarısız: {err[:200]}")

        success = bool(
            artifact and artifact.rule_count > 0
            and validation and validation.is_valid
            and syntax_ok
        )
        all_issues = (list(validation.issues) if validation else []) + syntax_issues
        summary = self._summarize(goal, plan, artifact, success)
        steps.append(AgentStep("summarize", "LLM" if self.llm else "template", summary[:80], ok=True))

        return AgentResult(
            success=success,
            goal=goal,
            os_target=os_target,
            fmt=fmt,
            plan=plan,
            artifact=artifact,
            issues=all_issues,
            steps=steps,
            summary=summary,
        )

    # ── serbest-form dal (katalog-miss) ──────────────────────────────────────────

    def _run_freeform(self, goal, os_target, security_level, fmt, plan, steps) -> AgentResult:
        """Katalog-dışı özel istek → LLM ile hedefe-özel script üret + güvenlik kapısı.

        Tehlikeli komut bulunursa REDDEDİLİR (success=False) — güvenli alternatif üretme yok.
        Üretilen script ayrıca FİİLEN syntax doğrulamasından (bash -n) geçer.
        """
        if self.llm is None:
            steps.append(AgentStep("freeform_generate", "FreeformScriptGenerator",
                                   "LLM yok — serbest-form üretilemez", ok=False))
            return AgentResult(success=False, goal=goal, os_target=os_target, fmt=fmt,
                               plan=plan, steps=steps, mode="freeform",
                               summary="Özel istek için LLM gerekli (yapılandırılmamış).")

        gen = FreeformScriptGenerator(llm_fn=self.llm, validator=self.validator, debug=self.debug)
        res = gen.generate(goal, os_target=os_target, security_level=security_level, fmt=fmt)
        steps.append(AgentStep(
            "freeform_generate", "FreeformScriptGenerator",
            f"{res.language} script ({len(res.content)} karakter)" if res.ok
            else f"reddedildi: {res.issues[:2]}",
            ok=res.ok,
        ))
        if not res.ok:
            return AgentResult(
                success=False, goal=goal, os_target=os_target, fmt=fmt, plan=plan,
                issues=res.issues, steps=steps, mode="freeform",
                summary="Özel istek için güvenli script üretilemedi "
                        f"({'; '.join(res.issues[:2]) or 'doğrulama başarısız'}).",
            )

        # Güvenlik geçti → fiilî sözdizimi doğrulaması (deterministik araç)
        ok, err = self._syntax_check(res.content, fmt)
        steps.append(AgentStep("syntax", "bash -n / yaml.load",
                               "sözdizimi geçerli" if ok else f"sözdizimi hatası: {err[:80]}",
                               ok=ok))

        artifact = Artifact(format=res.language, content=res.content, rule_count=0,
                            os_target=os_target, warnings=[])
        steps.append(AgentStep("summarize", "template",
                               f"Özel istek için {res.language} script üretildi.", ok=True))
        return AgentResult(
            success=ok, goal=goal, os_target=os_target, fmt=fmt, plan=plan,
            artifact=artifact, issues=([] if ok else [f"sözdizimi: {err}"]),
            steps=steps, mode="freeform",
            summary=f"'{goal}' için özel bir {res.language} script üretildi "
                    f"(katalog-dışı istek; CIS kural dökümü değil).",
        )

    # ── internal tools ──────────────────────────────────────────────────────────

    def _find_dangerous_rules(self, rule_ids: List[str]) -> set[str]:
        """Remediation içeriği tehlikeli komut barındıran kuralları bul."""
        bad: set[str] = set()
        for rid in rule_ids:
            rule = self.rule_engine.get_rule(rid) or {}
            script = (
                rule.get("remediation_script_content")
                or rule.get("remediation_command")
                or ""
            )
            if any(rx.search(script) for rx in self._danger_re):
                bad.add(rid)
        return bad

    # ── Sözdizimi self-verify araçları (Step 6) ──────────────────────────────────

    def _syntax_check(self, content: str, fmt: str) -> Tuple[bool, str]:
        """Üretilen artifact'ı FİİLEN doğrula (deterministik araç):
          • bash    → `bash -n` (söz dizimi). bash yoksa (ör. Windows) ATLA →
                      "doğrulanamadı" ≠ "geçersiz", false-fail verme.
          • ansible → `yaml.safe_load` (geçerli YAML mı).
          • diğer   → atla (güvenilir yerel doğrulayıcı yok: pwsh/reg/gpo).
        Döner: (ok, hata_mesajı).
        """
        if not content.strip():
            return True, ""
        if fmt == "bash":
            if not shutil.which("bash"):
                return True, ""  # doğrulayamıyoruz → engelleyici olma
            try:
                r = subprocess.run(
                    ["bash", "-n"], input=content,
                    capture_output=True, text=True, encoding="utf-8", timeout=10,
                )
                return (r.returncode == 0), (r.stderr or "").strip()
            except Exception:  # pragma: no cover - defensive (araç çalışmadı)
                return True, ""
        if fmt == "ansible":
            try:
                import yaml
                yaml.safe_load(content)
                return True, ""
            except Exception as exc:
                return False, str(exc)
        return True, ""

    def _isolate_broken_rule_ids(
        self, rule_ids: List[str], fmt: str, os_target: str, security_level: str
    ) -> set[str]:
        """Her kuralı TEK BAŞINA üretip sözdizimini dene → tek başına patlayanları işaretle.
        Generator her kuralı kendi `apply_<id>()` fonksiyonuna sardığı için bir kuralın
        bozuk içeriği o fonksiyonda izole kalır → tek-kural testi suçluyu kesin bulur."""
        bad: set[str] = set()
        for rid in rule_ids:
            rule = self.rule_engine.get_rule(rid)
            if not rule:
                continue
            art = self.artifact_generator.generate([rule], fmt, os_target, security_level)
            if art.rule_count == 0:
                continue  # remediation yok → generate zaten atladı, sözdizimi sorunu değil
            ok, _ = self._syntax_check(art.content, fmt)
            if not ok:
                bad.add(rid)
        return bad

    def _llm_repair(self, content: str, error: str, fmt: str) -> Optional[str]:
        """Sözdizimi hatasını LLM'e geri besleyip SADECE düzeltme iste (semantiği koru).
        Son çare: deterministik izolasyon çözemediğinde (ör. iskelet düzeyi hata)."""
        if not self.llm:
            return None
        prompt = (
            f"Aşağıdaki {fmt} script'inde bir SÖZDİZİMİ hatası var.\n\n"
            f"HATA:\n{error[:500]}\n\n"
            f"SCRIPT:\n{content[:6000]}\n\n"
            "Görev: SADECE sözdizimi hatasını düzelt. Komutları, kuralları ve güvenlik "
            "anlamını DEĞİŞTİRME; komut EKLEME/ÇIKARMA. Yalnızca düzeltilmiş script'in "
            "TAMAMINI döndür — açıklama veya markdown kod bloğu (```) EKLEME."
        )
        try:
            out = self.llm(prompt)
            return self._strip_code_fence(out).strip() if out else None
        except Exception:  # pragma: no cover - defensive
            return None

    @staticmethod
    def _strip_code_fence(text: str) -> str:
        """LLM çıktısındaki ```bash ... ``` / ```yaml ... ``` çitlerini ayıkla (varsa)."""
        t = text.strip()
        if not t.startswith("```"):
            return t
        lines = t.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines)

    def _summarize(self, goal: str, plan: HardeningPlan, artifact: Optional[Artifact], success: bool) -> str:
        # GERÇEK final kural sayısı = üretilen artifact'ınki (refine'da tehlikeli kural
        # çıkarılmış olabilir → plan.items'tan farklı). Özet plan'ı değil ÜRETİLENİ yansıtır.
        final_count = artifact.rule_count if artifact else len(plan.items)
        removed = len(plan.items) - final_count
        removed_note = f" ({removed} kural güvenlik nedeniyle çıkarıldı)" if removed > 0 else ""
        base = (
            f"'{goal}' hedefi için {final_count} kurallı bir {artifact.format if artifact else '?'} "
            f"sıkılaştırma planı üretildi{removed_note} ve "
            f"{'doğrulandı' if success else 'doğrulama uyarıları içeriyor'}."
        )
        if not self.llm:
            return base
        try:
            prompt = (
                "Aşağıdaki sıkılaştırma planını 1-2 cümleyle, yöneticiye uygun dilde özetle. "
                "Sadece özet metni döndür.\n\n"
                f"Hedef: {goal}\nOS: {plan.os_target}\nSeviye: {plan.security_level}\n"
                f"Üretilen kural sayısı: {final_count}{removed_note}\n"
                f"Çakışma: {len(plan.conflicts)}\n"
                f"Doğrulama: {'başarılı' if success else 'uyarılı'}"
            )
            out = self.llm(prompt).strip()
            return out or base
        except Exception:  # pragma: no cover - defensive
            return base
