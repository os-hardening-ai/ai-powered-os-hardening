# Changelog

Tüm önemli değişiklikler burada belgelenir.
Biçim: [Keep a Changelog](https://keepachangelog.com/tr/1.1.0/) · Sürümleme: [SemVer](https://semver.org/lang/tr/).

## [1.4.0] - 2026-06-06
Ürünleşme & entegrasyon sürümü.

### Eklendi
- **Partner API-key (M2M)** kimlik doğrulama (hash'li, RBAC-uyumlu) + `/version` ucu + OpenAI-uyumlu
  sözleşme + onboarding script (`scripts/gen_partner_key.py`).
- **CI/CD:** testler + niyet eval-gate; güvenlik taraması (pip-audit / Trivy / gitleaks);
  Compose-native SSH deploy; Dependabot (pip / github-actions / docker).
- **Gözlemlenebilirlik:** model-bazlı LLM sağlık dashboard'u (`05_llm_providers`) + RAG kalite panelleri
  (similarity / groundedness / retrieval / cost); model-bazlı gecikme metriği
  (`hardening_llm_call_duration_seconds`); 3 yeni alarm (LLMChainFailure / HighLLMFallbackRate / LowGroundedness).
- **Sağlamlık:** `/ready` probe, docker kaynak limitleri, SECURITY.md, ADR (mimari kararlar), OpenAPI export.

### Düzeltildi
- **Bağımlılık güvenliği (Dependabot):** `requests ≥ 2.33.0`, `pytest ≥ 9.0.3`, `aiohttp ≥ 3.14.0`.
- **Gözlemlenebilirlik:** Grafana Disk/CPU "No data" panelleri; hata-oranı + disk **alarmları**
  (etiket/mountpoint düzeltmeleri — önceden sessizce hiç tetiklenmiyordu).

### Güvenlik
- Güvenlik başlıkları doğrulandı (CSP/HSTS/X-Frame-Options...); API anahtarları SHA-256 hash'li saklanır.

## [1.3.0] - 2026-05-31
- JWT (HS256) + RBAC + audit log + kullanıcı-bazlı rate-limit; cevap-groundedness refinement döngüsü.

## [1.2.0] - 2026-05-30
- Cerebras/SambaNova birincil (`gpt-oss-120b`) + Gemini/Novita fallback; H3 çözüldü (P50 ~3.5-4.6 sn);
  gerçek SSE token-streaming; İP-5/6/7/8 + H1 ölçüm harness'leri.

## [1.1.0] - 2026-04-29
- Enhanced RAG: hybrid BM25+Dense (RRF), MMR, QueryPlanner (HyDE+subquery+stepback), ClaimVerifier.

## [1.0.0] - 2025-12-24
- İlk sürüm: 4-katmanlı pipeline, SSE, ML intent sınıflandırma, RAG.

[1.4.0]: https://github.com/os-hardening-ai/ai-powered-os-hardening/releases/tag/v1.4.0
