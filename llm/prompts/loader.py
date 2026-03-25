# prompts/loader.py
"""
Prompt Template Loader

Prompt şablonlarını llm/prompts/templates/ klasöründeki .md dosyalarından yükler.
Değişken ikamesi için str.format_map() kullanır: {variable_name} sözdizimi.
"""

from __future__ import annotations
import functools
from pathlib import Path

_TEMPLATES_DIR = Path(__file__).parent / "templates"


@functools.lru_cache(maxsize=None)
def load_template(name: str) -> str:
    """
    Şablon dosyasını yükle ve önbelleğe al.

    Args:
        name: Şablon adı (dosya uzantısı olmadan, örn. "simple", "medium", "cot")

    Returns:
        Şablon içeriği

    Raises:
        FileNotFoundError: Şablon dosyası bulunamazsa
    """
    path = _TEMPLATES_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt template not found: {path}")
    return path.read_text(encoding="utf-8")


def render_template(name: str, **variables: str) -> str:
    """
    Şablonu yükle ve değişkenleri doldur.

    Args:
        name: Şablon adı
        **variables: Şablondaki {placeholder} değerleri

    Returns:
        Doldurulmuş prompt string
    """
    template = load_template(name)
    return template.format_map(variables)
