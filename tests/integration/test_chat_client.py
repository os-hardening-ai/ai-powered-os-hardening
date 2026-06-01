"""
Chat API Client Integration Test
-----------------------------------
Çalışan API sunucusuna HTTP istekleri göndererek chat endpoint'ini test eder.
API sunucusunun http://localhost:8000 adresinde çalışması gerekir.

Çalıştırma:
    # Önce sunucuyu başlatın:
    python main.py

    # Sonra bu testi çalıştırın:
    python tests/integration/test_chat_client.py "SSH nedir?"
    python tests/integration/test_chat_client.py  # interaktif mod
"""

import sys
import os
import io

# NOT: pytest altında sys.stdout/stderr DEĞİŞTİRİLMEZ — capture mekanizmasını bozar
# ("I/O operation on closed file" → tüm suite toplanmaz). Yalnız standalone script
# olarak çalışınca (pytest import edilmemişken) Windows konsol UTF-8 düzeltmesi uygulanır.
if sys.platform == 'win32' and "pytest" not in sys.modules:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    os.system('chcp 65001 > nul 2>&1')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

import requests
from src.config_manager import ConfigManager

API_BASE = "http://localhost:8000"


def chat(question: str):
    manager = ConfigManager()
    config = manager.get_config()

    print(f"\n[SORU] {question}\n")
    print("[BEKLEYIN] Cevap hazırlanıyor...\n")

    try:
        response = requests.post(
            f"{API_BASE}/api/chat",
            json={
                "question": question,
                "os": config["os"],
                "role": config["role"],
                "security_level": config["security_level"],
                "use_rag": config["use_rag"],
                "rag_top_k": config["rag_top_k"],
                "rag_min_score": config["rag_min_score"],
            },
            timeout=60,
        )

        if response.status_code == 200:
            data = response.json()

            print("="*60)
            print("[CEVAP]")
            print("="*60)
            print(data["answer"])

            if data.get("rag_sources"):
                print("\n" + "="*60)
                print("[KAYNAKLAR]")
                print("="*60)
                for i, source in enumerate(data["rag_sources"], 1):
                    print(f"\n{i}. {source['source']} (Skor: {source['score']:.2f})")
                    print(f"   Bölüm: {source['section']}")

            print("\n" + "="*60 + "\n")
        else:
            print(f"[HATA] HTTP {response.status_code}")
            print(response.text)

    except requests.exceptions.ConnectionError:
        print(f"[HATA] {API_BASE} adresine bağlanılamadı!")
        print("Sunucunun çalıştığından emin olun: python main.py")
    except Exception as e:
        print(f"[HATA] {e}")


def interactive_mode():
    print("\n" + "="*60)
    print("AI-POWERED OS HARDENING - INTERAKTIF SOHBET")
    print("="*60)
    print(f"\nAPI: {API_BASE}")
    print("Çıkmak için 'quit' veya 'exit' yazın\n")

    manager = ConfigManager()

    while True:
        try:
            question = input("[SORU] ").strip()

            if not question:
                continue

            if question.lower() in ['quit', 'exit', 'q']:
                print("\n[CIKIS] Görüşmek üzere!")
                break

            if question.lower() == 'reset':
                manager.reset_config()
                manager = ConfigManager()
                continue

            chat(question)

        except KeyboardInterrupt:
            print("\n\n[CIKIS] Görüşmek üzere!")
            break
        except Exception as e:
            print(f"\n[HATA] {e}\n")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        chat(" ".join(sys.argv[1:]))
    else:
        interactive_mode()
