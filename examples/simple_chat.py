"""
Basitleştirilmiş sohbet örneği
Kullanıcı sadece soru sorar, sistem otomatik yapılandırır
"""
import requests
import sys
import os

# src modülünü import edebilmek için
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.config_manager import ConfigManager


def chat(question: str):
    """Basit sohbet - kullanıcı sadece soru sorar"""

    # Konfigürasyonu al (ilk seferinde kurulum yapar)
    manager = ConfigManager()
    config = manager.get_config()

    # API'ye gönder
    print(f"\n💬 Soru: {question}\n")
    print("⏳ Cevap hazırlanıyor...\n")

    try:
        response = requests.post(
            "http://localhost:8000/api/chat",
            json={
                "question": question,
                "os": config["os"],
                "role": config["role"],
                "security_level": config["security_level"],
                "use_rag": config["use_rag"],
                "rag_top_k": config["rag_top_k"],
                "rag_min_score": config["rag_min_score"]
            },
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()

            print("="*60)
            print("📝 CEVAP:")
            print("="*60)
            print(data["answer"])

            if data.get("rag_sources"):
                print("\n" + "="*60)
                print("📚 KAYNAKLAR:")
                print("="*60)
                for i, source in enumerate(data["rag_sources"], 1):
                    print(f"\n{i}. {source['source']} (Skor: {source['score']:.2f})")
                    print(f"   Bölüm: {source['section']}")

            print("\n" + "="*60 + "\n")
        else:
            print(f"❌ Hata: {response.status_code}")
            print(response.text)

    except requests.exceptions.ConnectionError:
        print("❌ Backend'e bağlanılamadı!")
        print("Sunucunun çalıştığından emin olun: python -m src.main")
    except Exception as e:
        print(f"❌ Hata: {e}")


def interactive_mode():
    """İnteraktif mod - sürekli soru-cevap"""
    print("\n" + "="*60)
    print("🤖 AI-POWERED OS HARDENING - İNTERAKTİF SOHBET")
    print("="*60)
    print("\nÇıkmak için 'quit' veya 'exit' yazın")
    print("Ayarları sıfırlamak için 'reset' yazın\n")

    manager = ConfigManager()

    while True:
        try:
            question = input("💬 Soru: ").strip()

            if not question:
                continue

            if question.lower() in ['quit', 'exit', 'q']:
                print("\n👋 Görüşmek üzere!")
                break

            if question.lower() == 'reset':
                manager.reset_config()
                manager = ConfigManager()
                continue

            chat(question)

        except KeyboardInterrupt:
            print("\n\n👋 Görüşmek üzere!")
            break
        except Exception as e:
            print(f"\n❌ Hata: {e}\n")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Tek soru modu
        question = " ".join(sys.argv[1:])
        chat(question)
    else:
        # İnteraktif mod
        interactive_mode()
