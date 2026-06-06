# Mimari Karar Kayıtları (ADR)

Bu belge, projedeki temel mühendislik kararlarını ve gerekçelerini özetler.
Biçim: her karar için **Bağlam → Karar → Sonuç/Ödünleşim**.

---

## ADR-001 — Birincil LLM: Cerebras gpt-oss-120b (+ fallback zinciri)
**Bağlam:** Düşük gecikme + sıfıra yakın maliyet + makul kalite gerekiyordu; başlangıçta Groq kullanıldı, kota/kararlılık sorunları yaşandı.
**Karar:** Birincil **Cerebras gpt-oss-120b** (~1.4 sn, ücretsiz katman 1M token/gün); **Gemini/OpenRouter** fallback; `FallbackLLM` + `LaneLoadBalancer` ile çoklu sağlayıcı round-robin.
**Sonuç:** Gecikme Groq'a göre ~15-20× iyileşti, maliyet ≈ $0. Ödünleşim: ücretsiz katmanın **istek/dakika** limiti → lane yük dengeleme ile aşıldı; sağlayıcıya bağımlılık fallback ile azaltıldı.

## ADR-002 — 4 Katmanlı Güvenli Pipeline (Safety → Intent → Routing → Validation)
**Bağlam:** LLM çıktısının güvenli, kapsam-içi ve gerekçeli olması gerekiyordu.
**Karar:** Sorumlulukları ayrık 4 katman + tek otoriteli **semantik kapsam kapısı** (kapsam yalnız L1'de).
**Sonuç:** Test edilebilir, gözlemlenebilir karar yolu (`layer_path`); prompt-injection/jailbreak L1'de filtrelenir. Ödünleşim: katman başına küçük gecikme (Grafana'da ölçülüyor).

## ADR-003 — Enhanced RAG: hibrit getirme + iddia doğrulama
**Bağlam:** Salt-LLM cevapları kaynaksız/uydurma riskine açıktı; kurumsal güvenlik tavsiyesi **kaynağa dayanmalı**.
**Karar:** Dense (0.6) + BM25 (0.4) + RRF hibrit, MMR çeşitlilik (λ=0.7), **ClaimVerifier** ile groundedness skoru; Novita qwen3-embedding-8b (4096-dim) + Qdrant Cloud.
**Sonuç:** Groundedness 0.722→0.889, CIS atıf 0.333→0.833 (H1). Ödünleşim: +~3 sn gecikme; `context_recall` (0.408) zayıf halka (gelecek-iş: reranker + korpus boşluğu).

## ADR-004 — Kimlik: JWT + RBAC (API-gateway yerine uygulama-içi)
**Bağlam:** Tek-VPS, küçük ekip; harici API-gateway operasyonel yük getirir.
**Karar:** Uygulama-içi **JWT (HS256) + RBAC** + Redis rate-limit + audit log; M2M için hash'li **API-key**.
**Sonuç:** Sıfır ek altyapı, rol-bazlı erişim. Ödünleşim: ölçeklenince merkezi gateway (Kong/Traefik) gelecek-iş.

## ADR-005 — Dağıtım: Docker Compose (Kubernetes DEĞİL)
**Bağlam:** Tek VPS (2 core / 8 GB), öğrenci ekip, hızlı iterasyon.
**Karar:** **Docker Compose** (+ prod override + Caddy otomatik TLS); CD = GitHub Actions → SSH → `git pull && compose up`.
**Sonuç:** Basit, tekrarlanabilir, düşük operasyonel yük. Ödünleşim: yatay ölçek/HA yok → **k3s/Kubernetes + ArgoCD gelecek-iş** (yalnız çok-sunucu gerekince; tek VPS için gereksiz karmaşıklık).

## ADR-006 — Kalıcı durum: SQLite (+ Redis yardımcı)
**Bağlam:** Kullanıcılar/audit/sohbet-geçmişi kalıcı olmalı; tek instance.
**Karar:** **SQLite** (auth.db, owner-scoped) birincil kalıcı depo; **Redis** yardımcı (embedding cache, rate-limit sayaçları, JWT blacklist) — **fail-open**.
**Sonuç:** Sıfır-yapılandırma kalıcılık + hızlı sıcak veri. Ödünleşim: çok-instance ölçek için **PostgreSQL** gelecek-iş.

## ADR-007 — Niyet sınıflandırma: TF-IDF + LogReg (LLM yerine)
**Bağlam:** Her istekte niyet tespiti gerekiyor; LLM çağrısı pahalı/yavaş.
**Karar:** Hafif **TF-IDF + LogReg** (conf 0.60), pattern fallback; 5362 örnek / 7 kategori.
**Sonuç:** %93.48 test doğruluğu, milisaniyelik + maliyetsiz, CI'da regresyon-kapısı. Ödünleşim: yeni kategori = yeniden eğitim (otomatik script mevcut).
