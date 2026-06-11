# layers/info_pipeline.py
"""
Layer 3B: Info Pipeline (Smart RAG + Complexity Routing)

Purpose:
- Handle information queries with adaptive complexity routing
- Smart RAG triggering based on query type
- Complexity-based model selection (simple/medium/complex)

Based on:
- REVISED_ROUTE_ARCHITECTURE.md - Layer 3B specification
- Existing pipeline_optimized.py complexity routing
"""

from __future__ import annotations
import logging
from typing import Callable, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from llm.core.context import RequestContext
from llm.utils.question_classifier import classify_question
from llm.prompts.simple_prompts import get_prompt_for_complexity, GROUNDING_DIRECTIVE
from llm.prompts.cot_prompts import CoTSecurityAnalyzer

# Type alias
LLMCallable = Callable[[str], str]

_logger = logging.getLogger(__name__)

# ── ANSWER CACHE (exact-match, normalize) ────────────────────────────────────
# Best-practice: aynı soruyu YENİDEN ÜRETME → 0 LLM call. Anahtar = normalize(soru) +
# os + role + security_level. Yalnız BAŞARILI cevaplar cache'lenir (hata/boş değil).
# In-memory LRU + TTL (tek container; çok-worker için ileride Redis'e taşınabilir).
# ANSWER_CACHE_TTL_S=0 → cache kapalı. (Semantik benzerlik eşleştirme ileride embedding
# cache üstüne eklenebilir; bu sürüm güvenli exact-match — yanlış-hit riski yok.)
import os as _os
import re as _re
from collections import OrderedDict as _OrderedDict

_ANSWER_CACHE: "dict" = _OrderedDict()
_ANSWER_CACHE_MAX = 500
try:
    _ANSWER_CACHE_TTL_S = float(_os.environ.get("ANSWER_CACHE_TTL_S", "1800"))
except ValueError:
    _ANSWER_CACHE_TTL_S = 1800.0


def _answer_cache_key(ctx: "RequestContext") -> str:
    q = _re.sub(r"\s+", " ", (ctx.user_question or "").strip().lower())
    return f"{q}|{ctx.os or ''}|{ctx.role or ''}|{ctx.security_level or ''}"


def _answer_cache_get(key: str):
    if _ANSWER_CACHE_TTL_S <= 0:
        return None
    item = _ANSWER_CACHE.get(key)
    if item is None:
        return None
    ts, result = item
    if (datetime.now() - ts).total_seconds() > _ANSWER_CACHE_TTL_S:
        _ANSWER_CACHE.pop(key, None)
        return None
    _ANSWER_CACHE.move_to_end(key)  # LRU dokunuşu
    return result


def _answer_cache_put(key: str, result) -> None:
    if _ANSWER_CACHE_TTL_S <= 0:
        return
    _ANSWER_CACHE[key] = (datetime.now(), result)
    _ANSWER_CACHE.move_to_end(key)
    while len(_ANSWER_CACHE) > _ANSWER_CACHE_MAX:
        _ANSWER_CACHE.popitem(last=False)



@dataclass
class InfoQueryResult:
    """Info pipeline result"""
    answer: str
    complexity: str  # simple/medium/complex
    used_rag: bool
    rag_chunks: int = 0
    model_used: str = "unknown"
    response_time_s: float = 0.0
    estimated_cost: float = 0.0
    rag_sources: list = field(default_factory=list)
    verification_confidence: float | None = None  # None = not checked
    unsupported_claims: list = field(default_factory=list)  # bağlamca DESTEKLENMEYEN iddialar
    timing: Dict[str, float] = field(default_factory=dict)  # per-step breakdown (seconds)


class InfoPipeline:
    """
    Layer 3B: Info Pipeline Handler

    Design:
    - Adaptive complexity routing (simple → medium → complex)
    - Smart RAG triggering:
      - SKIP RAG: Generic definitions LLM already knows
      - USE RAG: Specific OS/security config questions
    - Model selection:
      - Simple: Small model (Groq Llama 8B - FREE)
      - Medium: Medium model (GPT-4o-mini)
      - Complex: Large model + CoT (GPT-4o)

    Integration:
    - Called after Layer 2 identifies "info_request" intent
    - Uses parameter inference for metadata
    - Returns structured answer
    """

    def __init__(
        self,
        llm_small: LLMCallable,
        llm_large: LLMCallable,
        rag_builder: Optional[Callable] = None,
        query_planner=None,
        claim_verifier=None,
        debug: bool = False,
        enable_refinement: bool = True,
        refine_threshold: float = 0.40,
    ):
        """
        Args:
            llm_small:      Small/fast model callable
            llm_large:      Large/powerful model callable
            rag_builder:    RAG context builder (optional)
            query_planner:  QueryPlanner instance (optional — expands queries)
            claim_verifier: ClaimVerifier instance (optional — halüsinasyon kontrolü)
            debug:          Enable debug logging
            enable_refinement: Cevap-groundedness refinement loop'unu aç (düşük confidence
                            → sorguyu genişlet + yeniden üret, 1 deneme).
            refine_threshold: Bu eşiğin ALTINDAKİ verification confidence refinement tetikler.
        """
        self.llm_small = llm_small
        self.llm_large = llm_large
        self.rag_builder = rag_builder
        self.query_planner = query_planner
        self.claim_verifier = claim_verifier
        self.debug = debug
        self.enable_refinement = enable_refinement
        self.refine_threshold = refine_threshold

        # CoT analyzer for complex queries
        self.cot_analyzer = CoTSecurityAnalyzer(use_few_shot=True)

        self.stats = {
            "total_queries": 0,
            "simple_count": 0,
            "medium_count": 0,
            "complex_count": 0,
            "rag_used_count": 0,
            "rag_skipped_count": 0,
            "refine_count": 0,
            "total_cost": 0.0,
        }

    def _retrieve_rag(
        self, ctx: RequestContext, complexity: str
    ) -> tuple[int, list, list, dict]:
        """RAG retrieval — handle() ve handle_stream() tarafından ortaklaşa kullanılır.

        Returns: (rag_chunks, rag_sources, raw_results_for_verify, timing_updates)
        """
        _t: dict = {}
        rag_chunks, rag_sources, raw_results_for_verify = 0, [], []
        try:
            if self.query_planner is not None and complexity == "complex":
                try:
                    _t0 = datetime.now()
                    plan = self.query_planner.plan(ctx.user_question)
                    _t["query_planner_s"] = (datetime.now() - _t0).total_seconds()
                    all_queries = plan.all_queries()
                    _t0 = datetime.now()
                    if hasattr(self.rag_builder, "retrieve_multi"):
                        rag_context, raw_results = self.rag_builder.retrieve_multi(
                            queries=all_queries, original_query=ctx.user_question,
                        )
                    else:
                        rag_context, raw_results = self.rag_builder.retrieve_balanced(ctx.user_question)
                    _t["rag_retrieve_s"] = (datetime.now() - _t0).total_seconds()
                except Exception as qp_exc:
                    _logger.warning("[InfoPipeline] QueryPlanner failed, using balanced: %s", qp_exc)
                    _t0 = datetime.now()
                    rag_context, raw_results = self.rag_builder.retrieve_balanced(ctx.user_question)
                    _t["rag_retrieve_s"] = (datetime.now() - _t0).total_seconds()
            else:
                _t0 = datetime.now()
                rag_context, raw_results = self.rag_builder.retrieve_balanced(ctx.user_question)
                _t["rag_retrieve_s"] = (datetime.now() - _t0).total_seconds()

            if rag_context and raw_results:
                ctx.retrieved_context = rag_context
                rag_chunks = len(raw_results)
                raw_results_for_verify = raw_results
                self.stats["rag_used_count"] += 1
                for result in raw_results:
                    metadata = result.get("metadata", {})
                    section_id = metadata.get("section_id") or metadata.get("section") or ""
                    section_title = metadata.get("section_title") or metadata.get("title") or ""
                    if section_id and section_title and section_id != section_title:
                        section = f"{section_id} - {section_title}"
                    elif section_id:
                        section = section_id
                    elif section_title:
                        section = section_title
                    else:
                        section = "N/A"
                    chunk_text = result.get("text", "")
                    rag_sources.append({
                        "score": result.get("score", 0.0),
                        "source": metadata.get("benchmark_product") or metadata.get("source_id") or "CIS Benchmark",
                        "section": section,
                        "text": chunk_text[:500] if chunk_text else None,
                    })
                _logger.info("[InfoPipeline] RAG OK — %d chunks, %d sources", rag_chunks, len(rag_sources))
            else:
                _logger.info(
                    "[InfoPipeline] RAG returned empty — context=%s, results=%d",
                    bool(rag_context), len(raw_results),
                )
        except Exception as e:
            _logger.error("[InfoPipeline] RAG ERROR: %s", e)
        return rag_chunks, rag_sources, raw_results_for_verify, _t

    def handle(self, ctx: RequestContext) -> InfoQueryResult:
        """
        Handle information query

        Args:
            ctx: Request context

        Returns:
            InfoQueryResult with answer

        Decision Logic:
        1. Classify complexity (simple/medium/complex)
        2. Decide RAG usage (skip generic, use specific)
        3. Route to appropriate path
        4. Return structured result
        """
        start_time = datetime.now()
        _t: dict[str, float] = {}  # per-step timing accumulator

        # ANSWER CACHE: aynı soru (+os/role/level) tekrar gelirse 0 LLM call ile dön.
        _ck = _answer_cache_key(ctx)
        _cached = _answer_cache_get(_ck)
        if _cached is not None:
            _logger.info("[InfoPipeline] answer-cache HIT → 0 LLM call (%.40s)", ctx.user_question)
            return _cached

        # Classify complexity
        complexity = classify_question(ctx.user_question)

        if self.debug:
            print(f"[InfoPipeline] Complexity: {complexity}")

        use_rag = self.rag_builder is not None and self._should_use_rag(
            ctx.user_question, complexity
        )

        if self.debug:
            print(f"[InfoPipeline] RAG usage: {use_rag} (builder={self.rag_builder is not None})")

        rag_chunks = 0
        rag_sources = []
        raw_results_for_verify: List[dict] = []
        _logger.debug("[InfoPipeline] use_rag=%s, rag_builder=%s", use_rag, "SET" if self.rag_builder else "NONE")
        if use_rag and self.rag_builder:
            rag_chunks, rag_sources, raw_results_for_verify, _rag_t = self._retrieve_rag(ctx, complexity)
            _t.update(_rag_t)
        else:
            self.stats["rag_skipped_count"] += 1
            _logger.debug("[InfoPipeline] RAG skipped")

        # RAG kaliteli context getirdiyse simple→medium yükselt
        if complexity == "simple" and rag_chunks >= 2:
            complexity = "medium"
            _logger.debug("[InfoPipeline] Upgraded simple→medium (rag_chunks=%d)", rag_chunks)

        # Route based on complexity — time the LLM generation separately
        _t0 = datetime.now()
        try:
            result, model_used, estimated_cost = self._generate(ctx, complexity)
        except Exception as gen_exc:
            _logger.error("[InfoPipeline] LLM generation failed: %s", gen_exc)
            result = (
                "Şu anda yanıt üretilemedi — LLM sağlayıcısı geçici olarak kullanılamıyor. "
                "Lütfen birkaç saniye bekleyip tekrar deneyin."
            )
            model_used = "error"
            estimated_cost = 0.0
        _t["llm_gen_s"] = (datetime.now() - _t0).total_seconds()

        # Claim verification + REFINEMENT LOOP (only when RAG was used AND opt-in açıksa).
        # verify_claims default KAPALI — açıldığında ~15s ekler (hız↔groundedness tradeoff).
        verification_confidence: float | None = None
        unsupported_claims: list = []
        if self.claim_verifier is not None and raw_results_for_verify and getattr(ctx, "verify_claims", False):
            try:
                _t0 = datetime.now()
                vr = self.claim_verifier.verify(result, raw_results_for_verify)
                _t["claim_verify_s"] = (datetime.now() - _t0).total_seconds()

                # Cevap-groundedness refinement loop (HAFİF): üretilen cevap kaynaklarla
                # yeterince örtüşmüyorsa (confidence < eşik) → yeniden-retrieval/planlama YOK,
                # zaten elde olan kaynaklara karşı TEK küçük-model düzeltme çağrısı. Yalnız
                # DAHA İYİ cevabı tut. Tek deneme. simple yol RAG'siz olduğu için hariç.
                if (
                    self.enable_refinement
                    and complexity != "simple"
                    and self.rag_builder is not None
                    and vr.confidence < self.refine_threshold
                ):
                    result, raw_results_for_verify, vr = self._refine_answer(
                        ctx, complexity, result, raw_results_for_verify, vr, _t
                    )

                verification_confidence = vr.confidence
                unsupported_claims = list(vr.unsupported)
                # Disclaimer'ı yalnızca BİRDEN FAZLA desteksiz iddia varken göster. Tek bir
                # iddianın "desteksiz" çıkması (özellikle az örneklemde) çoğu kez kalibrasyon/
                # retrieval artefaktıdır → kullanıcıyı korkutucu "%0 güven" ile yanıltmayalım.
                # Ayrıca yüzde basmıyoruz (az iddiada precision yanıltıcı); niteliksel + eylem odaklı.
                if not vr.is_valid and len(vr.unsupported) >= 2:
                    _logger.warning(
                        "[InfoPipeline] Low verification confidence %.2f — unsupported: %s",
                        vr.confidence,
                        vr.unsupported[:2],
                    )
                    result += (
                        "\n\n> ℹ️ **Not:** Bu yanıttaki bazı ifadeler getirilen kaynak "
                        "dokümanlarla doğrudan eşleşmedi. Kritik komutları uygulamadan önce "
                        "resmi CIS Benchmark / dağıtım dokümantasyonundan teyit edin."
                    )
                    # KATMANLI ÇEKİNME (abstention): hiç desteklenen iddia yoksa (confidence 0 +
                    # ≥3 desteksiz) bu artık gürültü değil, gerçek dayanaksızlıktır → kullanıcıyı
                    # BAŞTA belirgin uyar (sessizce güvenli-görünen cevap sunma; zero-trust ruhu).
                    if vr.confidence <= 0.0 and len(vr.unsupported) >= 3:
                        result = (
                            "> ⚠️ **DİKKAT — DÜŞÜK DAYANAK:** Aşağıdaki yanıttaki iddialar getirilen "
                            "CIS kaynaklarıyla doğrulanamadı. Komutları RESMİ dokümantasyondan teyit "
                            "etmeden UYGULAMAYIN.\n\n"
                        ) + result
            except Exception as cv_exc:
                _logger.warning("[InfoPipeline] ClaimVerifier failed: %s", cv_exc)

        # Update stats
        self.stats["total_queries"] += 1
        self.stats["total_cost"] += estimated_cost

        # Calculate response time
        response_time = (datetime.now() - start_time).total_seconds()

        result_obj = InfoQueryResult(
            answer=result,
            complexity=complexity,
            used_rag=use_rag and rag_chunks > 0,
            rag_chunks=rag_chunks,
            model_used=model_used,
            response_time_s=response_time,
            estimated_cost=estimated_cost,
            rag_sources=rag_sources,
            verification_confidence=verification_confidence,
            unsupported_claims=unsupported_claims,
            timing=_t,
        )
        # Yalnız BAŞARILI cevabı cache'le (LLM hatası/boş cevabı tekrar sunma).
        if model_used != "error" and result and result.strip():
            _answer_cache_put(_ck, result_obj)
        return result_obj

    def _should_use_rag(self, question: str, complexity: str) -> bool:
        """RAG retrieval kararı — NİYETE BAĞLI (ayrı keyword otoritesi DEĞİL).

        Bu metoda yalnız info_request niyetiyle gelinir (3B). info_request için RAG
        VARSAYILAN AÇIKtır: bilgi cevabının amacı CIS/OS dayanağına oturmaktır. TEK
        optimizasyon: somut bir OS/config/CIS göstergesi YOKKEN saf jenerik tanım sorusu
        ("firewall nedir") gelirse LLM bunu zaten bilir → retrieval'ı atla (gecikme/maliyet).
        Karar 3 net dalda; rakip keyword labirenti yok.
        """
        q_lower = question.lower()

        # Somut dayanak gerektiren göstergeler (OS/sürüm/config/CIS) → mutlaka retrieval.
        specific_indicators = [
            "ubuntu", "centos", "debian", "windows", "rhel",            # OS
            "22.04", "24.04", "20.04", "server 2022",                   # sürüm
            "sshd_config", "firewalld", "ufw", "selinux", "apparmor",   # config
            "cis benchmark", "cis control", "benchmark",                # CIS
        ]
        # Saf tanım kalıpları (somut gösterge yoksa retrieval'ı atlamak güvenli).
        generic_patterns = [
            "nedir", "ne demek", "nasıl çalışır", "ne işe yarar",
            "what is", "what does", "explain",
        ]

        if any(ind in q_lower for ind in specific_indicators):
            return True                                  # somut OS/config/CIS → dayanak çek
        if any(p in q_lower for p in generic_patterns):
            return False                                 # saf tanım (somut yok) → atla
        return complexity in ("medium", "complex")       # belirsiz: karmaşıksa çek, basitse atla

    def _generate(self, ctx: RequestContext, complexity: str) -> tuple[str, str, float]:
        """Karmaşıklığa göre cevap üret. Döndürür: (cevap, model_used, estimated_cost).

        Refinement loop tarafından da yeniden çağrılır (aynı yolla yeniden üretim).
        """
        if complexity == "simple":
            self.stats["simple_count"] += 1
            return self._simple_path(ctx), "small", 0.0002
        elif complexity == "medium":
            self.stats["medium_count"] += 1
            return self._medium_path(ctx), "large", 0.0005
        else:  # complex
            self.stats["complex_count"] += 1
            return self._complex_path(ctx), "large+CoT", 0.0015

    def _refine_answer(self, ctx, complexity, result, raw_results, vr, _t):
        """HAFİF refinement: yeniden-retrieval/yeniden-planlama YOK.

        Zaten elde olan kaynaklara (raw_results / ctx.retrieved_context) karşı TEK
        küçük-model düzeltme çağrısı ile desteklenmeyen iddiaları çıkarır/uyumlar.
        Eski sürüm sorguyu genişletip tüm RAG yolunu baştan koşuyordu
        (reformulate + queryplan×3 + retrieve_multi + büyük-model üretim + verify
        ≈ 9 call, ~36s). Bu sürüm ~1 küçük-model call + 1 verify ≈ birkaç saniye.
        Yalnız confidence ARTARSA yeni cevabı tutar; aksi halde orijinali korur.
        """
        try:
            self.stats["refine_count"] += 1
            unsupported = list(vr.unsupported)
            if not unsupported or not ctx.retrieved_context:
                return result, raw_results, vr
            _logger.info(
                "[RefinementLoop:light] confidence %.2f < %.2f — %d iddia için tek düzeltme çağrısı",
                vr.confidence, self.refine_threshold, len(unsupported),
            )
            unsupported_txt = "\n".join(f"- {c}" for c in unsupported[:5])
            correction_prompt = (
                "Aşağıdaki KAYNAKLAR'a dayanarak CEVAP'ı düzelt. Kaynaklarca "
                "DESTEKLENMEYEN şu ifadeleri kaynaklarla uyumlu hale getir ya da çıkar; "
                "yeni iddia EKLEME, cevabın dilini ve formatını koru.\n\n"
                f"DESTEKLENMEYEN İFADELER:\n{unsupported_txt}\n\n"
                f"KAYNAKLAR:\n{ctx.retrieved_context}\n\n"
                f"CEVAP:\n{result}\n\n"
                "DÜZELTİLMİŞ CEVAP:"
            )
            _t1 = datetime.now()
            new_answer = self._call_llm(self.llm_small, correction_prompt, ctx)
            _t["refine_correct_s"] = (datetime.now() - _t1).total_seconds()

            if not new_answer or not new_answer.strip():
                return result, raw_results, vr

            # Aynı kaynaklara karşı yeniden doğrula (claims=1 → tek call); sadece iyileşirse tut
            new_vr = self.claim_verifier.verify(new_answer, raw_results)
            if new_vr.confidence > vr.confidence:
                _logger.info(
                    "[RefinementLoop:light] iyileşti %.2f → %.2f", vr.confidence, new_vr.confidence
                )
                return new_answer, raw_results, new_vr
            return result, raw_results, vr
        except Exception as exc:
            _logger.warning("[RefinementLoop:light] failed: %s", exc)
            return result, raw_results, vr

    def _call_llm(self, fn, prompt: str, ctx: RequestContext) -> str:
        """LLM'i çağır; RAG bağlamı varsa grounding direktifini SYSTEM mesajı olarak geçir.
        Callable 'system' parametresini desteklemiyorsa (örn. test mock'u) prompt-only çağırır."""
        from llm.clients import _accepts_system
        system = GROUNDING_DIRECTIVE if ctx.retrieved_context else None
        if system and _accepts_system(fn):
            return fn(prompt, system=system)
        return fn(prompt)

    def _simple_path(self, ctx: RequestContext) -> str:
        """
        Simple path: Small model + minimal prompt

        Args:
            ctx: Request context

        Returns:
            Answer string
        """
        if self.debug:
            print("[InfoPipeline] Simple path: small model")

        # Minimal prompt
        prompt = get_prompt_for_complexity(ctx, "simple")

        # LLM call — grounding direktifi SYSTEM mesajı olarak (RAG bağlamı varsa) → echo edilmez
        response = self._call_llm(self.llm_small, prompt, ctx)

        return response.strip()

    def _medium_path(self, ctx: RequestContext) -> str:
        """
        Medium path: Large model + medium prompt

        Args:
            ctx: Request context

        Returns:
            Answer string
        """
        if self.debug:
            print("[InfoPipeline] Medium path: large model")

        # Medium prompt
        prompt = get_prompt_for_complexity(ctx, "medium")

        # LLM call — grounding direktifi SYSTEM mesajı olarak (RAG bağlamı varsa)
        response = self._call_llm(self.llm_large, prompt, ctx)

        return response.strip()

    def _complex_path(self, ctx: RequestContext) -> str:
        """
        Complex path: Large model + full CoT reasoning

        Args:
            ctx: Request context

        Returns:
            Answer string
        """
        if self.debug:
            print("[InfoPipeline] Complex path: CoT reasoning")

        # CoT prompt
        cot_prompt = self.cot_analyzer.build_cot_prompt(ctx)

        # LLM call — grounding direktifi SYSTEM mesajı olarak (RAG bağlamı varsa)
        raw_response = self._call_llm(self.llm_large, cot_prompt, ctx)

        # Parse CoT response
        ctx = self.cot_analyzer.parse_cot_response(raw_response, ctx)

        # Return final answer
        return ctx.final_answer if ctx.final_answer else raw_response

    def handle_stream(self, ctx: RequestContext):
        """Gerçek token streaming varinatı. Yields:
            ("pre_gen", InfoQueryResult)  — RAG bitti, LLM başlamadan önce (answer="")
            ("token",   str)              — LLM token'ı
            ("done",    InfoQueryResult)  — tamamlanmış sonuç
        """
        from llm.clients import _accepts_system

        start_time = datetime.now()
        _t: dict = {}

        # Cache hit → token olarak tek parça gönder
        _ck = _answer_cache_key(ctx)
        _cached = _answer_cache_get(_ck)
        if _cached is not None:
            _logger.info("[InfoPipeline.stream] cache HIT → 0 LLM call")
            yield ("pre_gen", _cached)
            yield ("token", _cached.answer)
            yield ("done", _cached)
            return

        complexity = classify_question(ctx.user_question)
        use_rag = self.rag_builder is not None and self._should_use_rag(ctx.user_question, complexity)

        rag_chunks, rag_sources, raw_results_for_verify = 0, [], []
        if use_rag and self.rag_builder:
            rag_chunks, rag_sources, raw_results_for_verify, _rag_t = self._retrieve_rag(ctx, complexity)
            _t.update(_rag_t)
        else:
            self.stats["rag_skipped_count"] += 1

        if complexity == "simple" and rag_chunks >= 2:
            complexity = "medium"

        _model_label = {"simple": "small", "medium": "large"}.get(complexity, "large+CoT")
        _estimated_cost = {"simple": 0.0002, "medium": 0.0005}.get(complexity, 0.0015)

        partial = InfoQueryResult(
            answer="",
            complexity=complexity,
            used_rag=use_rag and rag_chunks > 0,
            rag_chunks=rag_chunks,
            model_used=_model_label,
            estimated_cost=_estimated_cost,
            rag_sources=rag_sources,
            timing=_t,
        )
        yield ("pre_gen", partial)

        # LLM ve prompt seç
        if complexity == "simple":
            self.stats["simple_count"] += 1
            fn = self.llm_small
            prompt = get_prompt_for_complexity(ctx, "simple")
        elif complexity == "medium":
            self.stats["medium_count"] += 1
            fn = self.llm_large
            prompt = get_prompt_for_complexity(ctx, "medium")
        else:
            self.stats["complex_count"] += 1
            fn = self.llm_large
            prompt = self.cot_analyzer.build_cot_prompt(ctx)

        system = GROUNDING_DIRECTIVE if ctx.retrieved_context else None

        # Token streaming
        collected: list[str] = []
        model_used_actual = _model_label
        _t0 = datetime.now()
        try:
            if hasattr(fn, "stream"):
                stream_fn = fn.stream
                gen = (
                    stream_fn(prompt, system=system)
                    if (system and _accepts_system(stream_fn))
                    else stream_fn(prompt)
                )
                for tok in gen:
                    collected.append(tok)
                    yield ("token", tok)
            else:
                # stream() yok — tam cevabı tek parça akıt (graceful degrade)
                full = self._call_llm(fn, prompt, ctx)
                collected.append(full)
                yield ("token", full)
        except Exception as gen_exc:
            _logger.error("[InfoPipeline.stream] LLM failed: %s", gen_exc)
            err = (
                "Şu anda yanıt üretilemedi — LLM sağlayıcısı geçici olarak kullanılamıyor. "
                "Lütfen birkaç saniye bekleyip tekrar deneyin."
            )
            collected = [err]
            yield ("token", err)
            model_used_actual = "error"
        _t["llm_gen_s"] = (datetime.now() - _t0).total_seconds()

        answer = "".join(collected).strip()

        # Complex: CoT parse
        if complexity == "complex" and model_used_actual != "error":
            try:
                ctx_parsed = self.cot_analyzer.parse_cot_response(answer, ctx)
                if ctx_parsed.final_answer:
                    answer = ctx_parsed.final_answer
            except Exception:
                pass

        self.stats["total_queries"] += 1
        self.stats["total_cost"] += _estimated_cost

        result_obj = InfoQueryResult(
            answer=answer,
            complexity=complexity,
            used_rag=use_rag and rag_chunks > 0,
            rag_chunks=rag_chunks,
            model_used=model_used_actual,
            response_time_s=(datetime.now() - start_time).total_seconds(),
            estimated_cost=_estimated_cost,
            rag_sources=rag_sources,
            timing=_t,
        )
        if model_used_actual != "error" and answer.strip():
            _answer_cache_put(_ck, result_obj)
        yield ("done", result_obj)

    def get_stats(self) -> dict:
        """Get usage statistics"""
        total = self.stats["total_queries"]
        if total == 0:
            return self.stats

        return {
            **self.stats,
            "simple_rate": self.stats["simple_count"] / total,
            "medium_rate": self.stats["medium_count"] / total,
            "complex_rate": self.stats["complex_count"] / total,
            "rag_usage_rate": self.stats["rag_used_count"] / total,
            "avg_cost_per_query": self.stats["total_cost"] / total,
        }


# Convenience function
def handle_info_query(
    question: str,
    llm_small: LLMCallable,
    llm_large: LLMCallable,
    rag_builder: Optional[Callable] = None,
    context: Optional[RequestContext] = None,
    debug: bool = False,
) -> InfoQueryResult:
    """
    Quick info query handler

    Usage:
        result = handle_info_query(
            "Ubuntu 22.04 SSH hardening nasıl yapılır?",
            llm_small=groq_llm,
            llm_large=openai_llm,
            rag_builder=rag_builder
        )
        print(result.answer)
    """
    from llm.core.context import RequestContext

    if context is None:
        context = RequestContext(user_question=question)

    pipeline = InfoPipeline(
        llm_small=llm_small,
        llm_large=llm_large,
        rag_builder=rag_builder,
        debug=debug,
    )

    return pipeline.handle(context)
