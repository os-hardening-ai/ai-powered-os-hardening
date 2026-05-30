"""
LLM sağlayıcı ortak arayüzü + hata taksonomisi.

Tüm sağlayıcı client'ları aynı çağrılabilir sözleşmeyi sağlar: ``client(prompt) -> str``.
Bu modül o sözleşmeyi tipler (Protocol) ve fallback/retry mantığının sağlayıcıdan
bağımsız karar verebilmesi için hataları SINIFLANDIRIR.

Neden ayrı hata sınıfları? Fallback handler'ın "429 mı, auth mı, geçici mi?" ayrımını
her sağlayıcının farklı exception metnine bakarak değil, tek bir taksonomiyle yapması
için. Her client kendi SDK hatasını bu sınıflardan birine çevirir.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    """Çağrılabilir LLM sağlayıcı sözleşmesi: prompt al, metin döndür."""

    def __call__(self, prompt: str) -> str: ...


# ── Hata taksonomisi ─────────────────────────────────────────────────────────

class LLMProviderError(RuntimeError):
    """Tüm sağlayıcı hatalarının tabanı. `provider` alanı hangi sağlayıcı olduğunu taşır."""

    #: Bu hata türünde sıradaki sağlayıcıya geçmek mantıklı mı?
    #: (Auth/Config hatasında geçmek mantıklı; ama örn. quota-bitti'de de geçilir.)
    should_fallback: bool = True

    def __init__(self, message: str, provider: str = "", *, cause: Exception | None = None) -> None:
        super().__init__(message)
        self.provider = provider
        #: Sarmalanan ham SDK hatası (tanı/loglama için). __cause__ getset-descriptor
        #: olduğundan normal attribute olarak da saklarız.
        self.original_error = cause
        if cause is not None:
            self.__cause__ = cause


class RateLimitError(LLMProviderError):
    """429 / rate-limit / kota aşımı. Sıradaki sağlayıcıya geçilmeli."""
    should_fallback = True


class AuthError(LLMProviderError):
    """401 / geçersiz anahtar. Bu sağlayıcı bu süreçte hep başarısız → atla."""
    should_fallback = True


class TimeoutError_(LLMProviderError):
    """Zaman aşımı / ağ. Sıradaki sağlayıcıya geçilmeli."""
    should_fallback = True


class ModelUnavailableError(LLMProviderError):
    """Model bulunamadı / sağlayıcı erişilemez / boş yanıt. Sıradaki sağlayıcıya geçilmeli."""
    should_fallback = True


def classify_error(exc: Exception, provider: str = "") -> LLMProviderError:
    """Ham bir SDK exception'ını taksonomiye çevirir (metin sezgisiyle).

    Zaten bir LLMProviderError ise olduğu gibi döndürür (çift sarmalama yok).
    """
    if isinstance(exc, LLMProviderError):
        return exc

    # Alt çizgileri boşluğa çevir ki "model_not_supported" ~ "model not supported".
    msg = str(exc).lower().replace("_", " ")
    if "rate" in msg and "limit" in msg or "429" in msg or "quota" in msg or "too many requests" in msg:
        return RateLimitError(f"{provider}: rate limit / kota aşıldı", provider, cause=exc)
    if "401" in msg or "unauthorized" in msg or "invalid api key" in msg or "api key" in msg and "invalid" in msg:
        return AuthError(f"{provider}: kimlik doğrulama hatası", provider, cause=exc)
    if "timeout" in msg or "timed out" in msg or "connection" in msg:
        return TimeoutError_(f"{provider}: zaman aşımı / bağlantı hatası", provider, cause=exc)
    if "not found" in msg or "not supported" in msg or "unavailable" in msg or "empty" in msg:
        return ModelUnavailableError(f"{provider}: model/servis erişilemez", provider, cause=exc)
    # Bilinmeyen → genel sağlayıcı hatası (yine de fallback denenir)
    return LLMProviderError(f"{provider}: {exc}", provider, cause=exc)
