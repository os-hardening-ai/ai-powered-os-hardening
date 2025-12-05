# prompts/simple_prompts.py
"""
Basit Sorular için Minimal Format Prompts

Maliyet optimizasyonu için:
- Uzun CoT reasoning yok
- Minimal format (emojisiz, sadece gerekli bilgi)
- Kısa ve öz yanıtlar
"""

from __future__ import annotations
from context import RequestContext


def build_simple_prompt(ctx: RequestContext) -> str:
    """
    Basit bilgi soruları için minimal prompt.

    Özellikler:
    - Emojisiz, sade format
    - Direkt cevap (1-3 paragraf)
    - ZT referansı minimal (varsa 1 cümle)

    Args:
        ctx: Request context

    Returns:
        Minimal prompt string
    """

    prompt = f"""Sen bir siber güvenlik uzmanısın. Kullanıcının sorusuna kısa, net ve pratik bir şekilde cevap ver.

SORU: "{ctx.user_question}"

BAĞLAM:
- OS: {ctx.os or 'genel'}
- Rol: {ctx.role or 'sysadmin'}

GÖREV:
Soruya KISA ve ÖZ bir şekilde cevap ver (1-3 paragraf).

FORMAT:
1. Ana cevap (açık ve net)
2. Örnek komut/config varsa ekle
3. Önemli uyarı varsa 1 cümle ile belirt

NOT:
- Gereksiz emoji kullanma
- Çok fazla bölüm açma
- Direkt ve pratik ol
- Zero Trust ile ilgiliyse sadece 1 cümle ile bahset

CEVAP:"""

    return prompt


def build_medium_prompt(ctx: RequestContext) -> str:
    """
    Orta karmaşıklıktaki sorular için dengeli prompt.

    Özellikler:
    - Orta seviye detay
    - Basit format (2-3 bölüm)
    - ZT referansı varsa kısaca

    Args:
        ctx: Request context

    Returns:
        Orta seviye prompt string
    """

    prompt = f"""Sen bir Zero Trust siber güvenlik uzmanısın. Kullanıcının sorusuna pratik ve uygulanabilir bir şekilde cevap ver.

SORU: "{ctx.user_question}"

BAĞLAM:
- OS: {ctx.os or 'genel'}
- Rol: {ctx.role or 'sysadmin'}
- Security Level: {ctx.security_level}

GÖREV:
Kullanıcıya pratik, adım adım bir cevap sun.

FORMAT (Basit):

ÖZET
[1-2 cümle: Ne yapılacak?]

ÖNERİLEN ADIMLAR
1. [İlk adım]
2. [İkinci adım]
...

ÖRNEK KOMUTLAR
```bash
# Örnek komutlar
```

ZERO TRUST İLİŞKİSİ (opsiyonel)
[Sadece alakalıysa, 1-2 cümle]

RİSK / UYARILAR
[Varsa, önemli noktalar]

CEVAP:"""

    return prompt


# ─────────────────────────────────────────────
# Convenience Functions
# ─────────────────────────────────────────────

def get_prompt_for_complexity(
    ctx: RequestContext,
    complexity: str
) -> str:
    """
    Soru karmaşıklığına göre uygun prompt'u döndür.

    Args:
        ctx: Request context
        complexity: "simple" | "medium" | "complex"

    Returns:
        Uygun prompt string
    """
    if complexity == "simple":
        return build_simple_prompt(ctx)
    elif complexity == "medium":
        return build_medium_prompt(ctx)
    else:
        # Complex için CoT kullanılacak (cot_prompts.py'den)
        from .cot_prompts import CoTSecurityAnalyzer
        analyzer = CoTSecurityAnalyzer(use_few_shot=True)
        return analyzer.build_cot_prompt(ctx)


# ─────────────────────────────────────────────
# Example Usage
# ─────────────────────────────────────────────

if __name__ == "__main__":
    from context import RequestContext

    # Test simple prompt
    ctx_simple = RequestContext(
        user_question="SELinux nedir?",
        os="rhel8",
        role="sysadmin",
    )

    print("="*70)
    print("SIMPLE PROMPT")
    print("="*70)
    print(build_simple_prompt(ctx_simple))
    print("\n")

    # Test medium prompt
    ctx_medium = RequestContext(
        user_question="SSH yapılandırmasını nasıl güvenli hale getiririm?",
        os="ubuntu_22_04",
        role="sysadmin",
    )

    print("="*70)
    print("MEDIUM PROMPT")
    print("="*70)
    print(build_medium_prompt(ctx_medium))
