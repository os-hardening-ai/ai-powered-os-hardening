# models/__init__.py
from __future__ import annotations

import inspect
import logging
import os
import threading
import time
from typing import Callable, Dict, List, Optional, Tuple


def _record_latency(stats: dict, label: str, elapsed_ms: float) -> None:
    """Lane/provider başına kümülatif gecikme (toplam_ms, adet) → ortalama hesaplanabilir.
    Yavaş lane tespiti için: hangi model sürekli uzun sürüyor görünür → havuzdan çıkarılır."""
    lat = stats.setdefault("latency_ms_by_provider", {})
    acc = lat.setdefault(label, [0.0, 0])
    acc[0] += elapsed_ms
    acc[1] += 1


def _record_failure(stats: dict, label: str) -> None:
    """Lane/provider başına başarısız (429/timeout/5xx) call sayısı → ÖLÜ/zayıf lane tespiti.
    (örn. codestral=0 başarı + N başarısızlık → model erişilemez/rate-limited.)"""
    f = stats.setdefault("failures_by_provider", {})
    f[label] = f.get(label, 0) + 1

# Import from core.config
from llm.core.config import LLM_PROVIDER

logger = logging.getLogger(__name__)

LLMCallable = Callable[..., str]


def _accepts_system(fn) -> bool:
    """fn (client.__call__ / .stream) opsiyonel 'system' parametresi kabul ediyor mu?
    Eski/deprecated client'lar system desteklemiyor → onlara prompt-only çağrı yapılır."""
    try:
        return "system" in inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False


def _metric_provider_call(role: str, provider: str, was_fallback: bool,
                          duration_s: Optional[float] = None) -> None:
    """Prometheus'a sağlayıcı çağrısını kaydet — best-effort (metrik yoksa sessiz geç).
    Gözlemlenebilirlik asla LLM akışını bozmamalı. duration_s → model-bazlı gecikme paneli."""
    try:
        from prometheus_metrics import record_llm_provider_call
        record_llm_provider_call(role, provider, was_fallback=was_fallback, duration_s=duration_s)
    except Exception:
        pass


def _metric_chain_failure(role: str) -> None:
    try:
        from prometheus_metrics import record_llm_chain_failure
        record_llm_chain_failure(role)
    except Exception:
        pass


def _get_openai_clients() -> Tuple[LLMCallable, LLMCallable]:
    """OpenAI client'larını local import ile al."""
    from .openai_client import get_small_openai_llm, get_large_openai_llm

    small = get_small_openai_llm()
    large = get_large_openai_llm()
    return small, large


def _get_groq_clients() -> Tuple[LLMCallable, LLMCallable]:
    """Groq client'larını local import ile al."""
    from .groq_client import get_small_groq_llm, get_large_groq_llm

    small = get_small_groq_llm()
    large = get_large_groq_llm()
    return small, large


def _get_novita_clients() -> Tuple[LLMCallable, LLMCallable]:
    """Novita client'larını local import ile al."""
    from .novita_llm_client import get_small_novita_llm, get_large_novita_llm

    small = get_small_novita_llm()
    large = get_large_novita_llm()
    return small, large


def _get_ollama_clients() -> Tuple[LLMCallable, LLMCallable]:
    """Ollama client'larını local import ile al."""
    from .ollama_client import get_small_ollama_llm, get_large_ollama_llm
    from llm.core.config import CONFIG

    small = get_small_ollama_llm(
        model_name=CONFIG.ollama_small_model,
        base_url=CONFIG.ollama_base_url,
        temperature=CONFIG.small_model_temperature,
        max_tokens=CONFIG.max_tokens,
    )
    large = get_large_ollama_llm(
        model_name=CONFIG.ollama_large_model,
        base_url=CONFIG.ollama_base_url,
        temperature=CONFIG.large_model_temperature,
        max_tokens=CONFIG.max_tokens,
    )
    return small, large


def _get_huggingface_clients() -> Tuple[LLMCallable, LLMCallable]:
    """HuggingFace client'larını local import ile al (ücretsiz tier — DEPRECATED, bkz. registry)."""
    from .huggingface_client import get_small_hf_llm, get_large_hf_llm

    return get_small_hf_llm(), get_large_hf_llm()


def _get_cerebras_clients() -> Tuple[LLMCallable, LLMCallable]:
    """Cerebras (gpt-oss-120b) — generic OpenAI-uyumlu client (en hızlı + ücretsiz 1M/gün)."""
    from .openai_compatible_client import get_small_cerebras_llm, get_large_cerebras_llm

    return get_small_cerebras_llm(), get_large_cerebras_llm()


def _get_sambanova_clients() -> Tuple[LLMCallable, LLMCallable]:
    """SambaNova (gpt-oss-120b) — generic OpenAI-uyumlu client (hızlı fallback)."""
    from .openai_compatible_client import get_small_sambanova_llm, get_large_sambanova_llm

    return get_small_sambanova_llm(), get_large_sambanova_llm()


def _get_gemini_clients() -> Tuple[LLMCallable, LLMCallable]:
    """Gemini 3.1 Flash Lite (OpenRouter üzerinden) — hızlı + 1M context fallback."""
    from .openai_compatible_client import get_small_gemini_llm, get_large_gemini_llm

    return get_small_gemini_llm(), get_large_gemini_llm()


# Sağlayıcı adı → (small, large) çifti kuran fonksiyon.
# Not: builder'lar burada tutulur (ollama özel kwargs gerektirir); registry yalnızca
# SIRA + maliyet metaverisi için kullanılır (ücretsiz-first politikası tek yerde).
_PROVIDER_BUILDERS: Dict[str, Callable[[], Tuple[LLMCallable, LLMCallable]]] = {
    "cerebras": _get_cerebras_clients,
    "sambanova": _get_sambanova_clients,
    "gemini": _get_gemini_clients,
    "novita": _get_novita_clients,
    # Aşağıdakiler registry'de deprecated (varsayılan zincirde DEĞİL); yalnızca açıkça
    # LLM_PROVIDER=<x> seçilirse kullanılır. Kullanıcı kararı: groq (riskli/flaky),
    # ollama (GPU yok), huggingface (bozuk) → otomatik akıştan çıkarıldı.
    "groq": _get_groq_clients,
    "ollama": _get_ollama_clients,
    "huggingface": _get_huggingface_clients,
    "openai": _get_openai_clients,
}


class FallbackLLM:
    """
    Birden çok sağlayıcıyı sırayla deneyen Callable[[str], str].

    Sağlayıcılar TEMBEL (lazy) kurulur: eksik API anahtarı olan bir sağlayıcı
    yalnızca o sağlayıcıya sıra geldiğinde atlanır, başlangıçta çökme olmaz.
    Bir çağrı hata verirse (429/timeout/5xx) sıradaki sağlayıcıya geçilir;
    hepsi başarısız olursa anlamlı bir hata yükseltilir (sessiz "" DÖNMEZ).

    small/large iki sarmalayıcı aynı `cache`'i paylaşır → her sağlayıcı en fazla
    bir kez kurulur.
    """

    def __init__(
        self,
        role: str,                      # "small" | "large"
        providers: List[str],
        cache: Dict[str, Optional[Tuple[LLMCallable, LLMCallable]]],
        stats: Optional[dict] = None,
    ) -> None:
        self.role = role
        self.providers = providers
        self._cache = cache
        # Gözlemlenebilirlik: hangi sağlayıcı kaç kez servis etti, kaç fallback oldu.
        # small/large paylaşımlı stats dict alabilir (get_llm_clients öyle verir).
        self.stats = stats if stats is not None else {
            "total_calls": 0, "fallback_count": 0, "failures": 0, "by_provider": {},
        }
        # ── YÜK DENGELEME (round-robin) ──────────────────────────────────────
        # Saf fallback HER ZAMAN birincil(cerebras)'ı önce dener → tüm yük tek
        # sağlayıcıya biner, onun 5/dk limiti darboğaz olur. Bunun yerine ilk
        # `balance_n` sağlayıcıyı (hızlı free tier: cerebras/sambanova/openrouter)
        # HER ÇAĞRIDA round-robin döndürürüz → yük ~eşit bölünür, agregat istek/dk
        # ~N katına çıkar. Kuyruğun geri kalanı (novita/ollama...) yine FALLBACK olarak
        # kalır. LLM_BALANCE_TOP_N=1 → rotasyon kapalı (eski saf-fallback davranışı).
        self._rr = 0
        self._rr_lock = threading.Lock()
        try:
            _bn = int(os.environ.get("LLM_BALANCE_TOP_N", "3"))
        except ValueError:
            _bn = 3
        self._balance_n = max(1, min(_bn, len(providers)))

    def _attempt_order(self) -> List[str]:
        """Bu çağrı için denenecek sağlayıcı sırası. İlk `balance_n` round-robin
        döndürülür (yük dengeleme), kalan kısım sabit kuyruk (fallback) olarak eklenir."""
        n = len(self.providers)
        bn = self._balance_n
        if bn <= 1 or n <= 1:
            return list(self.providers)
        with self._rr_lock:
            start = self._rr % bn
            self._rr += 1
        head = self.providers[:bn]
        return head[start:] + head[:start] + self.providers[bn:]

    def _client(self, provider: str) -> Optional[LLMCallable]:
        if provider not in self._cache:
            try:
                self._cache[provider] = _PROVIDER_BUILDERS[provider]()
                logger.info("[FallbackLLM] provider '%s' hazır", provider)
            except Exception as exc:
                logger.warning("[FallbackLLM] provider '%s' kullanılamıyor (atlanıyor): %s", provider, exc)
                self._cache[provider] = None
        built = self._cache[provider]
        if built is None:
            return None
        return built[0] if self.role == "small" else built[1]

    def __call__(self, prompt: str, system: Optional[str] = None) -> str:
        from llm.clients.base import classify_error

        self.stats["total_calls"] += 1
        last_exc: Optional[Exception] = None
        attempted: List[str] = []
        for idx, provider in enumerate(self._attempt_order()):
            client = self._client(provider)
            if client is None:
                continue
            attempted.append(provider)
            try:
                _t0 = time.perf_counter()
                result = client(prompt, system=system) if (system and _accepts_system(client)) else client(prompt)
                _elapsed = time.perf_counter() - _t0
                _record_latency(self.stats, provider, _elapsed * 1000.0)
                self.stats["by_provider"][provider] = self.stats["by_provider"].get(provider, 0) + 1
                if idx > 0:  # birincil değil → fallback gerçekleşti
                    self.stats["fallback_count"] += 1
                    logger.info("[FallbackLLM] '%s' ile kurtarıldı (fallback)", provider)
                _metric_provider_call(self.role, provider, idx > 0, duration_s=_elapsed)
                return result
            except Exception as exc:
                last_exc = classify_error(exc, provider)
                _record_failure(self.stats, provider)
                logger.warning(
                    "[FallbackLLM] '%s' başarısız (%s), sıradakine geçiliyor: %s",
                    provider, type(last_exc).__name__, last_exc,
                )
        self.stats["failures"] += 1
        _metric_chain_failure(self.role)
        raise RuntimeError(
            f"Tüm LLM sağlayıcıları başarısız oldu (denenen: {attempted or self.providers}). "
            f"Son hata: {last_exc}"
        )

    def stream(self, prompt: str, system: Optional[str] = None):
        """GERÇEK token streaming + fallback. İlk token'ı veren sağlayıcıdan akıtır;
        bir sağlayıcı ilk token'dan ÖNCE hata verirse sonrakine geçer (commit-on-first-token).
        `stream()` desteklemeyen sağlayıcı (örn. Novita-net) → tam cevabı tek parça yield eder.
        """
        from llm.clients.base import classify_error, ModelUnavailableError

        self.stats["total_calls"] += 1
        last_exc: Optional[Exception] = None
        attempted: List[str] = []
        for idx, provider in enumerate(self._attempt_order()):
            client = self._client(provider)
            if client is None:
                continue
            attempted.append(provider)
            try:
                if hasattr(client, "stream"):
                    gen = (client.stream(prompt, system=system)
                           if (system and _accepts_system(client.stream))
                           else client.stream(prompt))
                    first = next(gen)                 # ilk token → hata burada sağlayıcıyı atlatır
                    self.stats["by_provider"][provider] = self.stats["by_provider"].get(provider, 0) + 1
                    if idx > 0:
                        self.stats["fallback_count"] += 1
                        logger.info("[FallbackLLM.stream] '%s' ile kurtarıldı", provider)
                    _metric_provider_call(self.role, provider, idx > 0)
                    yield first
                    yield from gen
                    return
                else:  # stream'siz sağlayıcı → tam cevabı tek parça akıt (graceful degrade)
                    result = (client(prompt, system=system)
                              if (system and _accepts_system(client))
                              else client(prompt))
                    self.stats["by_provider"][provider] = self.stats["by_provider"].get(provider, 0) + 1
                    if idx > 0:
                        self.stats["fallback_count"] += 1
                    _metric_provider_call(self.role, provider, idx > 0)
                    yield result
                    return
            except StopIteration:
                last_exc = ModelUnavailableError(f"{provider}: boş stream", provider)
                continue
            except Exception as exc:
                last_exc = classify_error(exc, provider)
                logger.warning("[FallbackLLM.stream] '%s' başarısız (%s), sıradakine: %s",
                               provider, type(last_exc).__name__, last_exc)
                continue
        self.stats["failures"] += 1
        _metric_chain_failure(self.role)
        raise RuntimeError(
            f"Tüm LLM sağlayıcıları (stream) başarısız (denenen: {attempted or self.providers}). "
            f"Son hata: {last_exc}"
        )

    def get_stats(self) -> dict:
        total = self.stats["total_calls"]
        rate = (self.stats["fallback_count"] / total) if total else 0.0
        _lat = self.stats.get("latency_ms_by_provider", {})
        avg_lat = {k: round(v[0] / v[1]) for k, v in _lat.items() if v[1] > 0}
        return {**self.stats, "fallback_rate": round(rate, 4), "avg_latency_ms_by_provider": avg_lat}


class LaneLoadBalancer:
    """Açık (label, client) LANE'leri üzerinde round-robin + fallback Callable.

    Her lane = bir (provider, model) `OpenAICompatibleClient`. FallbackLLM hep aynı
    birincili dener (tek sağlayıcının rate-limit'i darboğaz); LaneLoadBalancer ise her
    çağrıda farklı lane ile BAŞLAR → yük lane'lere (her birinin AYRI istek/dk limiti)
    bölünür, agregat throughput ~N katına çıkar. Seçilen lane 429/timeout verirse
    sıradaki lane'e düşer (fallback korunur). small/large havuzları AYRIDIR: küçük
    helper çağrıları (safety/queryplanner/verify burst) ucuz-hızlı modellere, üretim
    güçlü modellere gider.
    """

    def __init__(self, role: str, lanes: List[Tuple[str, LLMCallable]], stats: Optional[dict] = None) -> None:
        self.role = role
        self.lanes = lanes  # [(label="provider:model", client), ...]
        self._rr = 0
        self._rr_lock = threading.Lock()
        self.stats = stats if stats is not None else {
            "total_calls": 0, "fallback_count": 0, "failures": 0, "by_provider": {},
        }

    def _order(self) -> List[Tuple[str, LLMCallable]]:
        n = len(self.lanes)
        if n <= 1:
            return list(self.lanes)
        with self._rr_lock:
            start = self._rr % n
            self._rr += 1
        return self.lanes[start:] + self.lanes[:start]

    def __call__(self, prompt: str, system: Optional[str] = None) -> str:
        from llm.clients.base import classify_error
        self.stats["total_calls"] += 1
        last_exc: Optional[Exception] = None
        attempted: List[str] = []
        for idx, (label, client) in enumerate(self._order()):
            attempted.append(label)
            try:
                _t0 = time.perf_counter()
                result = client(prompt, system=system) if (system and _accepts_system(client)) else client(prompt)
                _elapsed = time.perf_counter() - _t0
                _record_latency(self.stats, label, _elapsed * 1000.0)
                self.stats["by_provider"][label] = self.stats["by_provider"].get(label, 0) + 1
                if idx > 0:
                    self.stats["fallback_count"] += 1
                _metric_provider_call(self.role, label.split(":")[0], idx > 0, duration_s=_elapsed)
                return result
            except Exception as exc:
                last_exc = classify_error(exc, label)
                _record_failure(self.stats, label)
                logger.warning("[LaneLB:%s] '%s' başarısız (%s), sıradakine: %s",
                               self.role, label, type(last_exc).__name__, last_exc)
        self.stats["failures"] += 1
        _metric_chain_failure(self.role)
        raise RuntimeError(f"Tüm LLM lane'leri başarısız (denenen: {attempted}). Son hata: {last_exc}")

    def stream(self, prompt: str, system: Optional[str] = None):
        from llm.clients.base import classify_error, ModelUnavailableError
        self.stats["total_calls"] += 1
        last_exc: Optional[Exception] = None
        attempted: List[str] = []
        for idx, (label, client) in enumerate(self._order()):
            attempted.append(label)
            try:
                if hasattr(client, "stream"):
                    gen = (client.stream(prompt, system=system)
                           if (system and _accepts_system(client.stream)) else client.stream(prompt))
                    first = next(gen)
                    self.stats["by_provider"][label] = self.stats["by_provider"].get(label, 0) + 1
                    if idx > 0:
                        self.stats["fallback_count"] += 1
                    _metric_provider_call(self.role, label.split(":")[0], idx > 0)
                    yield first
                    yield from gen
                    return
                else:
                    result = (client(prompt, system=system)
                              if (system and _accepts_system(client)) else client(prompt))
                    self.stats["by_provider"][label] = self.stats["by_provider"].get(label, 0) + 1
                    if idx > 0:
                        self.stats["fallback_count"] += 1
                    _metric_provider_call(self.role, label.split(":")[0], idx > 0)
                    yield result
                    return
            except StopIteration:
                last_exc = ModelUnavailableError(f"{label}: boş stream", label)
                continue
            except Exception as exc:
                last_exc = classify_error(exc, label)
                logger.warning("[LaneLB.stream:%s] '%s' başarısız (%s), sıradakine: %s",
                               self.role, label, type(last_exc).__name__, last_exc)
                continue
        self.stats["failures"] += 1
        _metric_chain_failure(self.role)
        raise RuntimeError(f"Tüm LLM lane'leri (stream) başarısız (denenen: {attempted}). Son hata: {last_exc}")

    def get_stats(self) -> dict:
        total = self.stats["total_calls"]
        rate = (self.stats["fallback_count"] / total) if total else 0.0
        _lat = self.stats.get("latency_ms_by_provider", {})
        avg_lat = {k: round(v[0] / v[1]) for k, v in _lat.items() if v[1] > 0}
        return {**self.stats, "fallback_rate": round(rate, 4), "avg_latency_ms_by_provider": avg_lat}


def _build_lane_balancer(
    role: str, lanes_env: str, stats: dict, temperature_override: Optional[float] = None
) -> Optional["LaneLoadBalancer"]:
    """ "openrouter:model-a,sambanova:model-b" → LaneLoadBalancer. Key'i olmayan veya
    kurulamayan lane atlanır. Hiç lane kalmazsa None (çağıran varsayılana düşer).
    temperature_override verilirse role-default yerine o kullanılır (ör. script üretimi
    için düşük-temp deterministik client)."""
    from llm.clients.openai_compatible_client import (
        build_from_preset, preset_api_key, PROVIDER_PRESETS, _CHAIN_TIMEOUT, _CHAIN_RETRIES,
    )
    from llm.core.config import SMALL_MODEL_TEMPERATURE, LARGE_MODEL_TEMPERATURE
    temperature = (
        temperature_override if temperature_override is not None
        else (SMALL_MODEL_TEMPERATURE if role == "small" else LARGE_MODEL_TEMPERATURE)
    )
    lanes: List[Tuple[str, LLMCallable]] = []
    for part in lanes_env.split(","):
        part = part.strip()
        if not part:
            continue
        provider, _, model = part.partition(":")
        provider, model = provider.strip(), model.strip()
        if provider not in PROVIDER_PRESETS:
            logger.warning("[LaneLB:%s] bilinmeyen provider '%s' (lane atlandı)", role, provider)
            continue
        if not preset_api_key(provider):
            logger.warning("[LaneLB:%s] %s key yok (.env) → lane atlandı: %s", role, provider, model or "(default)")
            continue
        try:
            client = build_from_preset(
                provider, model=model or None, temperature=temperature,
                timeout=_CHAIN_TIMEOUT, max_retries=_CHAIN_RETRIES,
            )
            lanes.append((f"{provider}:{model or PROVIDER_PRESETS[provider]['model']}", client))
        except Exception as exc:
            logger.warning("[LaneLB:%s] lane kurulamadı %s:%s → %s", role, provider, model, exc)
    if not lanes:
        return None
    logger.info("[LaneLB:%s] %d lane aktif: %s", role, len(lanes), [l for l, _ in lanes])
    return LaneLoadBalancer(role, lanes, stats)


_script_llm_cache: Dict[str, Optional["LLMCallable"]] = {}


def get_script_llm() -> Optional[LLMCallable]:
    """Script üretimi için DÜŞÜK-TEMP (deterministik) large client.

    `SCRIPT_MODEL_TEMPERATURE` (default 0.1) ile `LLM_LARGE_LANES`'ten kurulur — script'ler
    daha tutarlı/öngörülebilir olsun. Lane env YOKSA None döner → çağıran (ActionPipeline)
    enjekte edilmiş llm_large'a düşer. Lane'siz/test ortamında GERÇEK provider init ETMEZ
    (yan etki yok). Tek sefer kurulup cache'lenir."""
    if "client" in _script_llm_cache:
        return _script_llm_cache["client"]
    lanes_env = os.environ.get("LLM_LARGE_LANES", "").strip()
    client: Optional[LLMCallable] = None
    if lanes_env:
        try:
            temp = float(os.environ.get("SCRIPT_MODEL_TEMPERATURE", "0.1"))
            stats = {"total_calls": 0, "fallback_count": 0, "failures": 0, "by_provider": {}}
            client = _build_lane_balancer("large", lanes_env, stats, temperature_override=temp)
            if client is not None:
                logger.info("[ScriptLLM] düşük-temp(%.2f) script client kuruldu", temp)
        except Exception as exc:
            logger.warning("[ScriptLLM] kurulamadı (injected large'a düşülecek): %s", exc)
            client = None
    _script_llm_cache["client"] = client
    return client


def get_llm_clients(enable_fallback: bool = True) -> Tuple[LLMCallable, LLMCallable]:
    """
    LLM_PROVIDER birincil; başarısız olursa diğer sağlayıcılara düşen (small, large) döndürür.

    Args:
        enable_fallback: False ise yalnızca birincil sağlayıcı (eski davranış,
                         örn. değerlendirme/ablation'da tek modeli sabitlemek için).

    Dönüş:
        (llm_small, llm_large)  # her ikisi de Callable[[str], str]
    """
    import os
    from llm.clients.registry import build_order, get_spec, Cost

    provider = (LLM_PROVIDER or "groq").lower()
    if provider not in _PROVIDER_BUILDERS:
        raise ValueError(
            f"Desteklenmeyen LLM_PROVIDER: '{provider}'\n"
            f"Geçerli değerler: {', '.join(_PROVIDER_BUILDERS)}"
        )

    if not enable_fallback:
        return _PROVIDER_BUILDERS[provider]()

    # ── LANE-TABANLI YÜK DENGELEME (opsiyonel) ───────────────────────────────
    # LLM_SMALL_LANES / LLM_LARGE_LANES verilirse, sağlayıcı-zinciri yerine açık
    # (provider:model) lane'leri üzerinde round-robin + fallback kullanılır. small/large
    # havuzları AYRI → helper burst'ü ucuz/hızlı modellere, üretim güçlü modellere dağılır.
    # Örn: LLM_SMALL_LANES="openrouter:meta-llama/llama-3.2-1b-instruct,sambanova:gemma-3-12b-it"
    _small_lanes = os.environ.get("LLM_SMALL_LANES", "").strip()
    _large_lanes = os.environ.get("LLM_LARGE_LANES", "").strip()
    if _small_lanes or _large_lanes:
        shared_stats = {"total_calls": 0, "fallback_count": 0, "failures": 0, "by_provider": {}}
        small_lb = _build_lane_balancer("small", _small_lanes, shared_stats) if _small_lanes else None
        large_lb = _build_lane_balancer("large", _large_lanes, shared_stats) if _large_lanes else None
        if small_lb and large_lb:
            logger.info("[get_llm_clients] LANE load-balancing aktif (small=%d lane, large=%d lane)",
                        len(small_lb.lanes), len(large_lb.lanes))
            return small_lb, large_lb
        logger.warning("[get_llm_clients] Lane env verildi ama lane kurulamadı (key/format?) → varsayılan zincire düşülüyor")

    # Fallback sırası (free_priority'ye göre): groq(10) → huggingface(20) → novita(25) → ollama(30)
    # Novita varsayılan olarak dahil (include_cheap=True): Groq 429'u için güvenilir ağ köprüsü.
    # LLM_INCLUDE_CHEAP=0 ile devre dışı bırakılabilir. LLM_INCLUDE_PAID=1 → OpenAI de eklenir.
    _truthy = ("1", "true", "yes", "on")
    _falsy  = ("0", "false", "no", "off")
    _cheap_env = os.environ.get("LLM_INCLUDE_CHEAP", "").lower()
    include_cheap = (_cheap_env not in _falsy)   # varsayılan True; yalnızca "0/false" ile kapatılır
    include_paid = os.environ.get("LLM_INCLUDE_PAID", "").lower() in _truthy
    primary_cost = get_spec(provider).cost
    if primary_cost is Cost.CHEAP_PAID:
        include_cheap = True
    if primary_cost is Cost.PAID:
        include_paid = True
    order = build_order(primary=provider, include_cheap=include_cheap, include_paid=include_paid)
    shared_cache: Dict[str, Optional[Tuple[LLMCallable, LLMCallable]]] = {}
    shared_stats = {"total_calls": 0, "fallback_count": 0, "failures": 0, "by_provider": {}}
    small = FallbackLLM("small", order, shared_cache, shared_stats)
    large = FallbackLLM("large", order, shared_cache, shared_stats)
    return small, large


# WARNING: Module-level initialization sorunları yaşanmaması için
# llm_small ve llm_large'ı doğrudan kullanmak yerine get_llm_clients()
# fonksiyonunu kullanın. Ancak backward compatibility için hala export ediyoruz.

# Module seviyesinde export et - ancak dikkatli kullanılmalı
try:
    llm_small, llm_large = get_llm_clients()
except Exception as e:
    # Import-time hata olursa warning ver ama crash etme.
    import warnings
    warnings.warn(
        f"LLM clients initialization failed: {e}\n"
        f"Use get_llm_clients() directly in your code instead of importing llm_small/llm_large.",
        RuntimeWarning,
    )

    # Dummy: SESSİZCE "" DÖNME — bu, hatayı yutup aşağı akışta boş/yanlış
    # cevaplara yol açıyordu. Bunun yerine çağrıldığında anlamlı hata yükselt.
    def _unavailable_llm(_prompt: str) -> str:  # type: ignore[misc]
        raise RuntimeError(
            "LLM clients kullanılamıyor (başlatma başarısız). "
            "get_llm_clients() ile doğrudan başlatmayı deneyin ve .env/anahtarları kontrol edin."
        )

    llm_small = _unavailable_llm  # type: ignore[assignment]
    llm_large = _unavailable_llm  # type: ignore[assignment]


__all__ = ["get_llm_clients", "llm_small", "llm_large"]