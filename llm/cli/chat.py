# run_chat.py
from __future__ import annotations

import sys
from datetime import datetime
from typing import Optional

from llm.core.context import RequestContext
from llm.pipelines.optimized import run_optimized_pipeline_with_retry
from llm.core.config import CONFIG
from llm.clients import get_llm_clients
from llm.core.session_store import global_session_store


# ─────────────────────────────────────────────
# CLI Helpers
# ─────────────────────────────────────────────

def print_banner() -> None:
    """Başlangıç banner'ını yazdır."""
    banner = """
================================================================

       Zero Trust Siber Guvenlik Chatbot

  Komutlar:
    /help     - Yardim menusu
    /config   - Mevcut konfigurasyon
    /context  - Baglam ayarlari (OS, rol, security level)
    /history  - Son konusma gecmisi
    /reset    - Session'i sifirla
    /quit     - Cikis (veya q, exit)

================================================================
"""
    print(banner)


def print_help() -> None:
    """Yardım menüsünü yazdır."""
    help_text = """
KOMUTLAR:

  /help        Bu yardım menüsünü gösterir
  /config      Aktif LLM konfigürasyonunu gösterir
  /context     Güvenlik bağlamını değiştir (OS, rol, security_level)
  /history     Son 5 konuşma turunu gösterir
  /reset       Session'ı sıfırla (hafızayı temizle)
  /quit        Programdan çıkış yap (veya: q, exit, quit)

GUVENLIK BAGLAMI:

  OS seçenekleri:
    - ubuntu_22_04, debian_12, centos_9
    - windows_11, windows_server_2022
    - generic_linux, generic_windows

  Rol seçenekleri:
    - sysadmin    : Sistem yöneticisi
    - soc         : Security Operations Center analisti
    - developer   : Yazılım geliştirici
    - devops      : DevOps mühendisi

  Security Level:
    - minimal     : Temel güvenlik
    - balanced    : Dengeli (varsayılan)
    - strict      : Maksimum güvenlik

  Zero Trust Maturity:
    - low         : ZT yeni başlayan
    - medium      : Orta seviye (varsayılan)
    - high        : İleri seviye ZT

ORNEKLER:

  Sen: SSH hardening için öneriler ver
  Sen: Windows RDP güvenliğini nasıl artırırım?
  Sen: /context os=ubuntu_22_04 role=soc level=strict
"""
    print(help_text)


def print_context_info(ctx: RequestContext) -> None:
    """Mevcut güvenlik bağlamını göster."""
    print("\nMEVCUT GUVENLIK BAGLAMI:")
    print(f"  OS:               {ctx.os or 'belirtilmedi'}")
    print(f"  Rol:              {ctx.role or 'belirtilmedi'}")
    print(f"  Security Level:   {ctx.security_level}")
    print(f"  ZT Maturity:      {ctx.zt_maturity}")
    print()


def update_context_from_command(
    current_ctx: RequestContext,
    command: str,
) -> RequestContext:
    """
    /context komutunu parse eder ve RequestContext'i günceller.
    
    Örnek: /context os=ubuntu_22_04 role=soc level=strict zt=high
    """
    parts = command.split()[1:]  # "/context" kısmını atla
    
    for part in parts:
        if "=" not in part:
            continue
        
        key, value = part.split("=", 1)
        key = key.strip().lower()
        value = value.strip()
        
        if key == "os":
            current_ctx.os = value
        elif key == "role":
            current_ctx.role = value
        elif key in ("level", "security", "security_level"):
            if value in ("minimal", "balanced", "strict"):
                current_ctx.security_level = value  # type: ignore[assignment]
        elif key in ("zt", "zt_maturity", "maturity"):
            if value in ("low", "medium", "high"):
                current_ctx.zt_maturity = value  # type: ignore[assignment]
    
    print("Baglam guncellendi!")
    print_context_info(current_ctx)
    
    return current_ctx


def print_history(session_id: str) -> None:
    """Session history'i yazdır."""
    history = global_session_store.get_history(session_id)
    
    if not history:
        print("Henuz konusma gecmisi yok.\n")
        return

    print(f"\nSON {len(history)} KONUSMA TURU:\n")

    for i, turn in enumerate(history, start=1):
        role_label = "Sen" if turn.role == "user" else "Asistan"

        print(f"{role_label} ({i}):")
        
        # Uzun mesajları truncate et
        content = turn.content
        if len(content) > 200:
            content = content[:200] + "..."
        
        print(f"  {content}")
        
        if turn.intent:
            print(f"  [Intent: {turn.intent}]")
        
        print()


# ─────────────────────────────────────────────
# Main Chat Loop
# ─────────────────────────────────────────────

def main() -> None:
    """Ana CLI chat döngüsü."""
    
    # Config summary (debug modda)
    CONFIG.print_summary()
    
    # LLM client'larını yükle
    try:
        llm_small, llm_large = get_llm_clients()
    except Exception as e:
        print(f"HATA: LLM client yuklenemedi: {e}")
        print("   Lutfen .env dosyanizi ve API key'lerinizi kontrol edin.")
        sys.exit(1)
    
    # Banner
    print_banner()
    
    # Session ID (istersen UUID kullanabilirsin)
    session_id = f"session-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    
    # Default güvenlik bağlamı
    default_ctx = RequestContext(
        user_question="",  # Her turda güncellenecek
        os="ubuntu_22_04",
        role="sysadmin",
        security_level="balanced",
        zt_maturity="medium",
    )
    
    print(f"Session ID: {session_id}\n")
    print_context_info(default_ctx)

    # Chat loop
    while True:
        try:
            user_input = input("Sen: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nCikiliyor... Guvenli kal!")
            break
        
        # Boş input kontrolü
        if not user_input:
            continue
        
        # Komut kontrolü
        cmd = user_input.lower()
        
        if cmd in ("q", "quit", "exit", "/quit"):
            print("\nGorusuruz, guvenli kal!")
            break
        
        if cmd in ("/help", "/h", "help"):
            print_help()
            continue
        
        if cmd in ("/config", "/conf"):
            CONFIG.print_summary()
            continue
        
        if cmd.startswith("/context"):
            default_ctx = update_context_from_command(default_ctx, user_input)
            continue
        
        if cmd in ("/history", "/hist"):
            print_history(session_id)
            continue
        
        if cmd in ("/reset", "/clear"):
            global_session_store.reset_session(session_id)
            print("Session sifirlandi (hafiza temizlendi).\n")
            continue
        
        # Normal soru-cevap akışı
        
        # Session'a user turn ekle
        global_session_store.add_turn(
            session_id=session_id,
            role="user",
            content=user_input,
        )
        
        # Context oluştur (her turda yeni instance)
        ctx = RequestContext(
            user_question=user_input,
            os=default_ctx.os,
            role=default_ctx.role,
            security_level=default_ctx.security_level,
            zt_maturity=default_ctx.zt_maturity,
            request_id=f"{session_id}-{datetime.now().strftime('%H%M%S')}",
        )
        
        # İsteğe bağlı: History'den bağlam ekle (RAG benzeri)
        # history = global_session_store.get_history(session_id)
        # if history:
        #     ctx.retrieved_context = _summarize_history(history)
        
        # Optimized Pipeline'ı çalıştır (retry ile)
        print("\nIsleniyor...\n")

        ctx = run_optimized_pipeline_with_retry(
            ctx=ctx,
            llm_small=llm_small,
            llm_large=llm_large,
            max_retries=CONFIG.max_retries,
            priority="balanced",
        )
        
        answer = ctx.final_answer or "(Bos cevap dondu, bir hata olmus olabilir.)"

        # Cevabı yazdır
        print("Asistan:\n")
        print(answer)
        print("\n" + "─" * 70 + "\n")
        
        # Session'a assistant turn ekle
        global_session_store.add_turn(
            session_id=session_id,
            role="assistant",
            content=answer,
            intent=str(ctx.intent) if ctx.intent else None,
            safety=ctx.safety.category if ctx.safety else None,
        )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nKesintiye ugradi. Guvenli kal!")
        sys.exit(0)
    except Exception as e:
        print(f"\nBeklenmeyen hata: {e}")
        if CONFIG.enable_debug_logs:
            import traceback
            traceback.print_exc()
        sys.exit(1)