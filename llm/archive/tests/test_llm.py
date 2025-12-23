# test_llm.py
from models import llm_small, llm_large
from config import print_config_summary, LLM_PROVIDER

def main():
    # Config özeti yazdır
    print_config_summary()
    
    # Test prompt
    prompt = "Siber güvenlik nedir? Kısaca açıkla."
    
    print(f"📝 Prompt: {prompt}")
    print(f"⏳ Model cevabı bekleniyor ({LLM_PROVIDER})...\n")
    
    try:
        # Küçük model ile test
        print("🔹 SMALL MODEL testi:")
        response_small = llm_small(prompt)
        print(f"✅ Cevap:\n{response_small}\n")
        
        # Büyük model ile test (opsiyonel)
        test_large = input("\n🔸 LARGE MODEL da test edilsin mi? (y/N): ").lower()
        if test_large == 'y':
            print("\n🔹 LARGE MODEL testi:")
            response_large = llm_large(prompt)
            print(f"✅ Cevap:\n{response_large}\n")
        
    except Exception as e:
        print(f"\n❌ Hata: {e}")
        print("\nÇözüm önerileri:")
        print("  1. .env dosyasında API key'i kontrol et")
        print("  2. LLM_PROVIDER değerini kontrol et")
        print("  3. İnternet bağlantını kontrol et")
        if LLM_PROVIDER == "groq":
            print("  4. Groq API key al: https://console.groq.com/keys")

if __name__ == "__main__":
    main()