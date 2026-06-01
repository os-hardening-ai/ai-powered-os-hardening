"""
EmbeddingIntentRouter testleri — AĞSIZ (sahte embedder enjekte edilir).

Router'ın matematiğini (kosinüs-kNN, sınıf top-k ortalaması, OOS eşiği, cache imzası)
gerçek Novita API'sine ihtiyaç duymadan doğrular. Sahte embedder her metni kontrollü bir
2B "kavram" vektörüne eşler; böylece beklenen sınıf deterministik bilinir.
"""

from __future__ import annotations

import numpy as np
import pytest

from llm.ml.embedding_router import EmbeddingIntentRouter, _l2_normalize


# Kontrollü mini referans seti (gerçek CSV yerine) — 4 yön (greeting/info/action/thanks)
_TINY_CSV = """text,intent
selam,greeting
merhaba,greeting
naber,greeting
ssh nedir,info_request
ufw nedir,info_request
firewall açıklaması,info_request
ssh kapat,action_request
ufw yapılandır,action_request
teşekkürler,thanks
sağ ol,thanks
"""

# Kavram → 4B yön vektörü. Aynı intent'teki örnekler aynı yöne yakın olur.
_CONCEPT = {
    "greeting": np.array([1.0, 0, 0, 0]),
    "info": np.array([0, 1.0, 0, 0]),
    "action": np.array([0, 0, 1.0, 0]),
    "thanks": np.array([0, 0, 0, 1.0]),
}


def _vec_for(text: str) -> np.ndarray:
    t = text.lower()
    if any(w in t for w in ["selam", "merhaba", "naber", "günaydın"]):
        base = _CONCEPT["greeting"]
    elif any(w in t for w in ["kapat", "yapılandır", "uygula", "yaz"]):
        base = _CONCEPT["action"]
    elif any(w in t for w in ["teşekkür", "sağ ol"]):
        base = _CONCEPT["thanks"]
    elif any(w in t for w in ["ssh", "ufw", "firewall", "nedir", "açıklama"]):
        base = _CONCEPT["info"]
    else:
        base = np.array([0.25, 0.25, 0.25, 0.25])  # belirsiz → hiçbir yöne güçlü değil (OOS)
    return base.astype(np.float32)


class FakeEmbedder:
    def embed_texts(self, texts):
        return np.vstack([_vec_for(t) for t in texts]).astype(np.float32)

    def embed_query(self, text):
        return _vec_for(text)


@pytest.fixture
def router(tmp_path):
    csv = tmp_path / "tiny.csv"
    csv.write_text(_TINY_CSV, encoding="utf-8")
    cache = tmp_path / "emb.npz"
    return EmbeddingIntentRouter(
        embed_client=FakeEmbedder(), csv_path=csv, cache_path=cache,
        oos_threshold=0.6, topk=2, debug=False,
    )


class TestRouting:
    def test_greeting(self, router):
        assert router.predict("merhaba").type == "greeting"
        assert router.predict("selam dostum").type == "greeting"  # 'selam' kavramı

    def test_info(self, router):
        assert router.predict("ssh nedir").type == "info_request"

    def test_action(self, router):
        assert router.predict("ssh kapat").type == "action_request"

    def test_thanks(self, router):
        assert router.predict("çok teşekkürler").type == "thanks"

    def test_out_of_scope_low_similarity(self, router):
        # Hiçbir kavram kelimesi içermeyen girdi → belirsiz yön (0.25,0.25,..) → eşik altı → OOS
        r = router.predict("kayısı reçeli mevsiminde")
        assert r.type == "out_of_scope", f"beklenen out_of_scope, gelen {r.type}"

    def test_confidence_in_range(self, router):
        r = router.predict("merhaba")
        assert 0.0 <= r.confidence <= 1.0
        assert isinstance(r.probabilities, dict) and r.probabilities


class TestCache:
    def test_cache_written_and_reused(self, tmp_path):
        csv = tmp_path / "c.csv"; csv.write_text(_TINY_CSV, encoding="utf-8")
        cache = tmp_path / "c.npz"
        r1 = EmbeddingIntentRouter(embed_client=FakeEmbedder(), csv_path=csv, cache_path=cache)
        assert cache.exists(), "cache npz yazılmalı"

        # 2. örnek: embed ETMEYEN bir client ile yüklenebilmeli (cache HIT kanıtı)
        class NoEmbed:
            def embed_texts(self, texts):
                raise AssertionError("cache HIT olmalıydı — embed_texts çağrılmamalı")
            def embed_query(self, text):
                return _vec_for(text)
        r2 = EmbeddingIntentRouter(embed_client=NoEmbed(), csv_path=csv, cache_path=cache)
        assert r2.predict("merhaba").type == "greeting"

    def test_csv_change_invalidates_cache(self, tmp_path):
        csv = tmp_path / "c.csv"; csv.write_text(_TINY_CSV, encoding="utf-8")
        cache = tmp_path / "c.npz"
        EmbeddingIntentRouter(embed_client=FakeEmbedder(), csv_path=csv, cache_path=cache)
        # CSV değişti → imza değişmeli → yeniden embed (NoEmbed ile çağrılırsa hata)
        csv.write_text(_TINY_CSV + "iyi günler,greeting\n", encoding="utf-8")

        class CountEmbed(FakeEmbedder):
            calls = 0
            def embed_texts(self, texts):
                CountEmbed.calls += 1
                return super().embed_texts(texts)
        EmbeddingIntentRouter(embed_client=CountEmbed(), csv_path=csv, cache_path=cache)
        assert CountEmbed.calls == 1, "CSV değişince cache geçersiz olmalı → yeniden embed"


def test_l2_normalize_unit_norm():
    v = _l2_normalize(np.array([[3.0, 4.0]]))
    assert abs(float(np.linalg.norm(v[0])) - 1.0) < 1e-6
