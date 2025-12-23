#!/usr/bin/env python3
"""
RAG + LLM Entegrasyon Test Script

API endpoint'lerini test eder ve sonuçları gösterir.
"""

import requests
import json
from typing import Dict, Any


# API base URL
BASE_URL = "http://localhost:8000"


def test_chat_endpoint(question: str, use_rag: bool = True, **kwargs) -> Dict[str, Any]:
    """
    /api/chat endpoint'ini test et

    Args:
        question: Kullanıcı sorusu
        use_rag: RAG kullanılsın mı
        **kwargs: Ek parametreler

    Returns:
        Response dict
    """
    payload = {
        "question": question,
        "use_rag": use_rag,
        "rag_top_k": kwargs.get("rag_top_k", 5),
        "rag_min_score": kwargs.get("rag_min_score", 0.7),
        "os": kwargs.get("os", "ubuntu_22_04"),
        "role": kwargs.get("role", "sysadmin"),
        "security_level": kwargs.get("security_level", "balanced"),
        "zt_maturity": kwargs.get("zt_maturity", "medium"),
    }

    print(f"\n{'='*70}")
    print(f"SORU: {question}")
    print(f"RAG: {'Aktif' if use_rag else 'Devre Dışı'}")
    print(f"{'='*70}\n")

    try:
        response = requests.post(
            f"{BASE_URL}/api/chat",
            json=payload,
            timeout=60
        )
        response.raise_for_status()

        data = response.json()

        # Cevabı yazdır
        print("CEVAP:")
        print(data["answer"])
        print()

        # Intent ve safety
        print(f"Intent: {data.get('intent', 'N/A')}")
        print(f"Safety: {data.get('safety_category', 'N/A')}")
        print()

        # RAG kaynakları
        if data.get("rag_sources"):
            print("RAG KAYNAKLARI:")
            for idx, source in enumerate(data["rag_sources"], start=1):
                print(f"  {idx}. {source['source']} - {source['section']}")
                print(f"     Relevance: {source['score']:.3f}")
            print()

        # Stats
        stats = data.get("stats", {})
        print("İSTATİSTİKLER:")
        print(f"  LLM Calls: {stats.get('total_calls', 0)}")
        print(f"  RAG Retrievals: {stats.get('rag_retrieval_count', 0)}")
        print(f"  Cost Estimate: ${stats.get('total_cost_estimate', 0):.4f}")
        print()

        return data

    except requests.exceptions.RequestException as e:
        print(f"❌ HATA: {e}")
        return {}


def test_rag_only_endpoint(query: str, top_k: int = 5) -> Dict[str, Any]:
    """
    /rag/search endpoint'ini test et (RAG-only, LLM yok)

    Args:
        query: Arama sorgusu
        top_k: Kaç sonuç isteniyor

    Returns:
        Response dict
    """
    payload = {
        "query": query,
        "top_k": top_k
    }

    print(f"\n{'='*70}")
    print(f"RAG-ONLY TEST: {query}")
    print(f"{'='*70}\n")

    try:
        response = requests.post(
            f"{BASE_URL}/rag/search",
            json=payload,
            timeout=30
        )
        response.raise_for_status()

        data = response.json()

        print(f"Query: {data['query']}")
        print(f"Top-K: {data['top_k']}")
        print(f"\nSONUÇLAR:")

        for idx, result in enumerate(data["results"], start=1):
            print(f"\n{idx}. ID: {result['id']}")
            print(f"   Score: {result['score']:.3f}")
            print(f"   Text: {result['text'][:150]}...")

            if result.get("metadata"):
                print(f"   Metadata: {json.dumps(result['metadata'], indent=6)}")

        return data

    except requests.exceptions.RequestException as e:
        print(f"❌ HATA: {e}")
        return {}


def test_health():
    """Health check endpoint'ini test et"""
    print(f"\n{'='*70}")
    print("HEALTH CHECK")
    print(f"{'='*70}\n")

    try:
        response = requests.get(f"{BASE_URL}/health")
        response.raise_for_status()

        data = response.json()
        print(json.dumps(data, indent=2))

    except requests.exceptions.RequestException as e:
        print(f"❌ HATA: {e}")


def main():
    """Ana test fonksiyonu"""

    print("""
    ╔═══════════════════════════════════════════════════════════════╗
    ║         RAG + LLM ENTEGRASYON TEST SÜİTİ                     ║
    ╚═══════════════════════════════════════════════════════════════╝
    """)

    # Test 1: Health check
    test_health()

    # Test 2: RAG + LLM (güvenlik sorusu)
    test_chat_endpoint(
        question="SSH hardening için en önemli 3 adım nedir?",
        use_rag=True,
        security_level="strict"
    )

    # Test 3: RAG + LLM (firewall sorusu)
    test_chat_endpoint(
        question="Ubuntu 22.04'te firewall konfigürasyonu nasıl yapılır?",
        use_rag=True,
        rag_top_k=3
    )

    # Test 4: LLM-only (RAG olmadan)
    test_chat_endpoint(
        question="Zero Trust nedir?",
        use_rag=False
    )

    # Test 5: Smalltalk (RAG gerekmez)
    test_chat_endpoint(
        question="Merhaba, nasılsın?",
        use_rag=True  # Pipeline otomatik devre dışı bırakır
    )

    # Test 6: RAG-only endpoint
    test_rag_only_endpoint(
        query="password policy",
        top_k=3
    )

    print(f"\n{'='*70}")
    print("TÜM TESTLER TAMAMLANDI")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    import sys

    # Eğer argüman verilmişse özel test yap
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
        test_chat_endpoint(question, use_rag=True)
    else:
        # Tüm testleri çalıştır
        main()
