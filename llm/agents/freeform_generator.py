"""
Serbest-Form Script Üretici — katalog-dışı özel istekler için.

HardeningAgent normalde CIS kural KATALOĞUNDAN seçim yapar. Ama kullanıcı katalogda
karşılığı OLMAYAN özel bir iş isteyebilir (ör. "SSH için dev grubu oluştur ve bu gruba
allow ver" → `groupadd dev` + `AllowGroups dev`). Katalog böyle bir kural içermediğinden
agent eskiden alakasız 20+ generic kural döküyordu. Bu üretici, LLM ile kullanıcının TAM
isteğini karşılayan hedefli bir script üretir.

GÜVENLİK: Üretilen serbest-form script, katalog script'iyle AYNI güvenlik kapısından geçer
(OutputValidator / DANGEROUS_COMMANDS). Tehlikeli komut bulunursa REDDEDİLİR (ok=False) —
LLM'e güvenli alternatif ürettirme YOK (en güvenli/sade politika; kullanıcı kararı).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from llm.pipelines.layers.output_validator import OutputValidator

logger = logging.getLogger(__name__)

LLMCallable = Callable[[str], str]


@dataclass
class FreeformResult:
    """Serbest-form üretim sonucu."""
    ok: bool                       # güvenli + içerik üretildi mi
    content: str                   # üretilen script (kod bloğu çıkarılmış)
    language: str                  # bash | powershell
    issues: List[str] = field(default_factory=list)   # güvenlik/üretim sorunları


class FreeformScriptGenerator:
    """LLM ile hedefe-özel script üretir + güvenlik doğrulamasından geçirir."""

    def __init__(
        self,
        llm_fn: LLMCallable,
        validator: Optional[OutputValidator] = None,
        debug: bool = False,
    ) -> None:
        self._llm = llm_fn
        # Katalog akışıyla AYNI güvenlik kapısı (regex-only, LLM gerekmez).
        self.validator = validator or OutputValidator(use_llm_validation=False, debug=debug)
        self.debug = debug

    def generate(
        self,
        goal: str,
        os_target: str = "ubuntu_24_04",
        security_level: str = "balanced",
        fmt: str = "bash",
    ) -> FreeformResult:
        language = "powershell" if "windows" in os_target.lower() else "bash"
        prompt = self._build_prompt(goal, os_target, security_level, language)
        try:
            raw = self._llm(prompt)
        except Exception as exc:
            logger.warning("[Freeform] LLM çağrısı başarısız: %s", exc)
            return FreeformResult(ok=False, content="", language=language,
                                  issues=[f"LLM hatası: {exc}"])

        content = _extract_code_block(raw, language)
        if not content.strip():
            return FreeformResult(ok=False, content="", language=language,
                                  issues=["Üretilen yanıttan script çıkarılamadı."])

        # GÜVENLİK KAPISI — katalog akışıyla aynı validator (intent=info_request:
        # ham script doğrular, markdown kod-bloğu zorunluluğunu atlar).
        validation = self.validator.validate(content, intent="info_request")
        if not validation.is_valid:
            # Tehlikeli/geçersiz → REDDET (güvenli alternatif üretme yok — kullanıcı kararı).
            return FreeformResult(ok=False, content=content, language=language,
                                  issues=list(validation.issues))

        return FreeformResult(ok=True, content=content, language=language)

    # ── prompt ──────────────────────────────────────────────────────────────
    def _build_prompt(self, goal: str, os_target: str, security_level: str, language: str) -> str:
        shebang = "" if language == "powershell" else "#!/usr/bin/env bash\nset -euo pipefail\n"
        return (
            f"Sen kıdemli bir sistem yöneticisisin. Kullanıcının TAM olarak istediği işi yapan, "
            f"ÜRETİME HAZIR bir {language} script'i yaz.\n\n"
            f"KULLANICI İSTEĞİ: {goal}\n"
            f"HEDEF OS: {os_target} | Güvenlik seviyesi: {security_level}\n\n"
            "KURALLAR:\n"
            "1. SADECE istenen işi yap — alakasız genel CIS sıkılaştırma kuralları EKLEME.\n"
            "2. Her adıma kısa yorum + (uygunsa) geri alma (rollback) notu ekle.\n"
            "3. İşlem öncesi ilgili dosyaları yedekle (varsa).\n"
            "4. Idempotent olsun (tekrar çalıştırılabilir; zaten varsa hata vermesin).\n"
            "5. Tehlikeli/yıkıcı komut KULLANMA (rm -rf /, mkfs, dd if=..of=/dev/sd, vb.).\n"
            "6. SADECE kod bloğu döndür, açıklama yazma.\n\n"
            f"```{language}\n{shebang}# Hedef: {goal}\n"
        )


def _extract_code_block(text: str, language: str) -> str:
    """LLM çıktısından ilk kod bloğunu çıkar. Fence yoksa metnin tamamını dener
    (bash shebang/komut sezgisi). Boşsa "" döner."""
    if not text:
        return ""
    # ```lang ... ```  veya  ``` ... ```
    m = re.search(r"```[a-zA-Z]*\n(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    # Fence yok ama script-benzeri içerik (shebang / yaygın komutlar) → ham metni kullan
    stripped = text.strip()
    if stripped.startswith("#!") or re.search(r"\b(groupadd|useradd|usermod|sed|echo|systemctl|chmod|chown)\b", stripped):
        return stripped
    return ""
