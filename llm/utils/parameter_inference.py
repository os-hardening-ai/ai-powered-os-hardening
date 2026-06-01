# utils/parameter_inference.py
"""
Parametre Çıkarım Motoru

Kullanıcı sorusundan otomatik olarak parametreleri çıkarır:
- OS (işletim sistemi)
- Role (kullanıcı rolü)
- Security Level (güvenlik seviyesi)

Bu sayede kullanıcı her sorguda parametreleri girmek zorunda kalmaz.
"""

from __future__ import annotations
import re
from typing import Optional, Dict, Any
from datetime import datetime


class ParameterInferenceEngine:
    """
    Kullanıcı sorusundan parametreleri otomatik çıkarır.

    Inference stratejisi:
    1. Pattern matching (regex)
    2. Keyword detection
    3. Intent-based inference
    4. Session context fallback
    5. Safe defaults
    """

    # OS Detection Patterns
    OS_PATTERNS = {
        # Ubuntu
        r'\b(ubuntu\s*24\.04|ubuntu\s*24|noble|jammy)\b': 'ubuntu_24_04',
        r'\b(ubuntu\s*22\.04|ubuntu\s*22)\b': 'ubuntu_22_04',
        r'\b(ubuntu\s*20\.04|ubuntu\s*20|focal)\b': 'ubuntu_20_04',
        r'\bubuntu\b': 'ubuntu_22_04',  # Generic ubuntu → latest LTS

        # Debian
        r'\b(debian\s*12|debian\s*bookworm)\b': 'debian_12',
        r'\b(debian\s*11|debian\s*bullseye)\b': 'debian_11',
        r'\bdebian\b': 'debian_12',  # Generic debian → latest

        # CentOS/RHEL
        r'\b(centos\s*9|rhel\s*9|red\s*hat\s*9)\b': 'centos_9',
        r'\b(centos\s*8|rhel\s*8|red\s*hat\s*8)\b': 'centos_8',
        r'\b(centos|rhel|red\s*hat)\b': 'centos_9',  # Generic → latest

        # Windows
        r'\b(windows\s*11|win\s*11)\b': 'windows_11',
        r'\b(windows\s*server\s*2022)\b': 'windows_server_2022',
        r'\b(windows\s*server\s*2019)\b': 'windows_server_2019',
        r'\bwindows\b': 'windows_11',  # Generic → latest

        # macOS
        r'\b(macos|mac\s*os|osx)\b': 'macos',
    }

    # Role Detection Patterns
    ROLE_PATTERNS = {
        r'\b(sysadmin|system\s*admin|admin|sistem\s*yönetici)\b': 'sysadmin',
        r'\b(developer|dev|geliştirici|yazılımcı|coder|programmer)\b': 'developer',
        r'\b(devops|sre|site\s*reliability)\b': 'devops',
        r'\b(security|güvenlik|soc|security\s*analyst|pentester)\b': 'security',
    }

    # Security Level Keywords
    SECURITY_LEVEL_KEYWORDS = {
        'strict': ['strict', 'maximum', 'paranoid', 'high', 'katı', 'maksimum', 'yüksek'],
        'minimal': ['minimal', 'basic', 'low', 'düşük', 'temel', 'basit'],
        'balanced': ['balanced', 'normal', 'dengeli', 'orta', 'medium'],
    }

    def __init__(self, debug: bool = False):
        """
        Args:
            debug: Debug mod (inference detaylarını logla)
        """
        self.debug = debug
        self.inference_log = []  # Inference history (debugging için)

    def infer_os(self, question: str, default: str = "ubuntu_22_04") -> str:
        """
        Sorudan OS tespit et.

        Args:
            question: Kullanıcı sorusu
            default: Default OS (tespit edilemezse)

        Returns:
            OS identifier (e.g., "ubuntu_22_04")

        Examples:
            >>> engine = ParameterInferenceEngine()
            >>> engine.infer_os("Ubuntu 22.04'te SSH nasıl yapılandırılır?")
            'ubuntu_22_04'
            >>> engine.infer_os("Windows Server 2022 firewall ayarları")
            'windows_server_2022'
        """
        matched = self._match_os(question)
        if matched is None and self.debug:
            self.inference_log.append(f"OS: {default} (default)")
        return matched or default

    def _match_os(self, question: str) -> Optional[str]:
        """OS pattern'i eşleşirse değeri, yoksa None (gerçek-tespit sinyali)."""
        question_lower = question.lower()
        for pattern, os_value in self.OS_PATTERNS.items():
            if re.search(pattern, question_lower, re.IGNORECASE):
                if self.debug:
                    self.inference_log.append(f"OS: {os_value} (pattern: {pattern})")
                return os_value
        return None

    def infer_role(self, question: str, default: str = "sysadmin") -> str:
        """
        Sorudan kullanıcı rolü tespit et.

        Strateji:
        1. Explicit mention (soru içinde rol belirtilmiş)
        2. Intent-based (soru tipinden çıkar)
        3. Keyword-based (specific keywords)

        Args:
            question: Kullanıcı sorusu
            default: Default role

        Returns:
            Role identifier

        Examples:
            >>> engine = ParameterInferenceEngine()
            >>> engine.infer_role("Developer olarak SSH key nasıl yönetilir?")
            'developer'
            >>> engine.infer_role("Monitoring ve alerting kurulumu")
            'devops'
        """
        matched = self._match_role(question)
        if matched is None and self.debug:
            self.inference_log.append(f"Role: {default} (default)")
        return matched or default

    def _match_role(self, question: str) -> Optional[str]:
        """Rol açıkça veya intent'ten eşleşirse değeri, yoksa None (gerçek-tespit sinyali)."""
        question_lower = question.lower()

        # 1. Explicit role mention
        for pattern, role_value in self.ROLE_PATTERNS.items():
            if re.search(pattern, question_lower, re.IGNORECASE):
                if self.debug:
                    self.inference_log.append(f"Role: {role_value} (explicit)")
                return role_value

        # 2. Intent-based inference
        if any(kw in question_lower for kw in [
            'script', 'automation', 'code', 'api', 'sdk', 'library',
            'git', 'docker', 'container', 'build', 'deploy'
        ]):
            if self.debug:
                self.inference_log.append("Role: developer (intent: code/automation)")
            return 'developer'
        if any(kw in question_lower for kw in [
            'ci/cd', 'pipeline', 'ansible', 'terraform', 'kubernetes',
            'monitoring', 'prometheus', 'grafana', 'elk', 'logging'
        ]):
            if self.debug:
                self.inference_log.append("Role: devops (intent: infrastructure)")
            return 'devops'
        if any(kw in question_lower for kw in [
            'incident', 'threat', 'vulnerability', 'exploit', 'audit',
            'compliance', 'forensic', 'penetration', 'siem'
        ]):
            if self.debug:
                self.inference_log.append("Role: security (intent: security ops)")
            return 'security'
        return None

    def infer_security_level(
        self,
        question: str,
        role: str,
        default: str = "balanced"
    ) -> str:
        """
        Güvenlik seviyesi öner.

        Strateji:
        1. Explicit mention (soru içinde belirtilmiş)
        2. Role-based defaults
        3. Keyword-based inference

        Args:
            question: Kullanıcı sorusu
            role: Tespit edilen rol (role-based default için)
            default: Default security level

        Returns:
            Security level (minimal/balanced/strict)

        Examples:
            >>> engine = ParameterInferenceEngine()
            >>> engine.infer_security_level("Maximum güvenlik için SSH hardening", "sysadmin")
            'strict'
            >>> engine.infer_security_level("Basit firewall kuralları", "developer")
            'minimal'
        """
        # 1. Explicit keywords (sorudan gerçek tespit)
        explicit = self._match_security_level(question)
        if explicit:
            return explicit

        # 2. Role-based defaults (rolden türetilmiş, güvenli)
        role_defaults = {
            'security': 'strict',  # Security team → strict
            'sysadmin': 'balanced',  # SysAdmin → balanced
            'devops': 'balanced',  # DevOps → balanced
            'developer': 'minimal',  # Developer → minimal (dev env)
        }
        if role in role_defaults:
            level = role_defaults[role]
            if self.debug:
                self.inference_log.append(f"SecurityLevel: {level} (role-based)")
            return level

        # 3. Default
        if self.debug:
            self.inference_log.append(f"SecurityLevel: {default} (default)")
        return default

    def _match_security_level(self, question: str) -> Optional[str]:
        """Açık güvenlik-seviyesi anahtar kelimesi eşleşirse değeri, yoksa None."""
        question_lower = question.lower()
        for level, keywords in self.SECURITY_LEVEL_KEYWORDS.items():
            if any(kw in question_lower for kw in keywords):
                if self.debug:
                    self.inference_log.append(f"SecurityLevel: {level} (explicit)")
                return level
        return None

    def infer_all(
        self,
        question: str,
        session_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Tüm parametreleri bir seferde çıkar.

        Öncelik sırası:
        1. Session context (varsa, override)
        2. Question inference
        3. Defaults

        Args:
            question: Kullanıcı sorusu
            session_context: Session'dan gelen context (optional)

        Returns:
            Dict with inferred parameters

        Example:
            >>> engine = ParameterInferenceEngine()
            >>> engine.infer_all("Ubuntu 22.04'te developer olarak SSH kurulumu")
            {
                'os': 'ubuntu_22_04',
                'role': 'developer',
                'security_level': 'minimal',
                'zt_maturity': 'medium',
                'inferred': True,
                'inference_source': {
                    'os': 'question',
                    'role': 'question',
                    'security_level': 'role_default'
                }
            }
        """
        # Clear inference log
        self.inference_log = []

        # 1. Infer from question — gerçekten EŞLEŞTİ mi yoksa default'a mı düştü, izle
        os_match = self._match_os(question)
        role_match = self._match_role(question)
        sec_match = self._match_security_level(question)
        os_inferred = os_match or "ubuntu_22_04"
        role_inferred = role_match or "sysadmin"
        security_level_inferred = self.infer_security_level(question, role_inferred)

        # Track sources: yalnız sorudan EŞLEŞTİYSE 'question' (gerçek tespit), aksi 'default'
        inference_source = {
            'os': 'question' if os_match else 'default',
            'role': 'question' if role_match else 'default',
            'security_level': 'question' if sec_match else 'default',
            'zt_maturity': 'default',
        }

        # 2. Override with session context (if provided)
        if session_context:
            if session_context.get('os'):
                os_inferred = session_context['os']
                inference_source['os'] = 'session'

            if session_context.get('role'):
                role_inferred = session_context['role']
                inference_source['role'] = 'session'

            if session_context.get('security_level'):
                security_level_inferred = session_context['security_level']
                inference_source['security_level'] = 'session'

        # 3. Build result
        result = {
            'os': os_inferred,
            'role': role_inferred,
            'security_level': security_level_inferred,
            'zt_maturity': 'medium',  # Always default for now
            'inferred': True,  # Flag: These params were inferred
            'inference_source': inference_source,
            'timestamp': datetime.now().isoformat(),
        }

        if self.debug:
            result['inference_log'] = self.inference_log

        return result

    def get_inference_message(self, inferred_params: Dict[str, Any]) -> Optional[str]:
        """
        Kullanıcıya inference hakkında bilgi mesajı oluştur.

        Args:
            inferred_params: infer_all() output

        Returns:
            User-friendly message (optional)

        Example:
            "✓ OS tespit edildi: Ubuntu 22.04 (sorudan)
             ✓ Rol tespit edildi: Developer (sorudan)
             → Sonraki sorular bu bağlamda yanıtlanacak."
        """
        sources = inferred_params.get('inference_source', {})

        # Sadece question'dan infer edildiyse mesaj göster
        if sources.get('os') == 'question' or sources.get('role') == 'question':
            os_name = inferred_params['os']
            role_name = inferred_params['role']

            return (
                f"✓ Bağlam tespit edildi: {os_name.replace('_', ' ').title()}, "
                f"Rol: {role_name.title()}\n"
                f"→ Sonraki sorular bu bağlamda yanıtlanacak."
            )

        return None


# Convenience function
def infer_parameters(
    question: str,
    session_context: Optional[Dict[str, Any]] = None,
    debug: bool = False
) -> Dict[str, Any]:
    """
    Global helper: Parametreleri çıkar.

    Usage:
        params = infer_parameters("Ubuntu'da SSH nasıl yapılır?")
        # → {'os': 'ubuntu_22_04', 'role': 'sysadmin', ...}
    """
    engine = ParameterInferenceEngine(debug=debug)
    return engine.infer_all(question, session_context)
