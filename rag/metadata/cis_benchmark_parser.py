from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List
import re


def parse_benchmark_from_filename(path: Path) -> Dict[str, Any]:
    """
    Ornek dosya adi: CIS_Ubuntu_Linux_24.04_LTS_Benchmark_v1.0.0.pdf
    Doküman-level metadata: benchmark_product, os_family, os_version, benchmark_version
    """
    name = path.stem
    parts = name.split("_")
    lower = name.lower()
    meta: Dict[str, Any] = {}

    version_matches = re.findall(r"\d+\.\d+(?:\.\d+)?", name)
    if version_matches:
        meta["os_version"] = version_matches[0]
    else:
        int_matches = re.findall(r"\b\d+\b", name)
        if int_matches:
            meta["os_version"] = int_matches[0]

    bench_ver_match = re.search(r"v(\d+\.\d+\.\d+)", name, re.IGNORECASE)
    if bench_ver_match:
        meta["benchmark_version"] = bench_ver_match.group(1)

    benchmark_words = {"benchmark", "benchmarks"}
    product_tokens: List[str] = []
    for p in parts[1:]:
        pl = p.lower()
        if re.match(r"\d+\.\d+(?:\.\d+)?", p) or pl in benchmark_words:
            break
        product_tokens.append(p)
    if product_tokens:
        product = " ".join(product_tokens).replace("-", " ")
        meta["benchmark_product"] = product

    prod_lower = meta.get("benchmark_product", "").lower()
    check_str = prod_lower or lower
    if "ubuntu" in check_str or "linux" in check_str:
        meta["os_family"] = "linux"
    elif "windows" in check_str:
        meta["os_family"] = "windows"
    return meta


def extract_profile_applicability(text: str) -> List[str]:
    """
    Chunk icinden 'Profile Applicability' blogunu cikarir.
    Cikti: ["Level 1 - Server", "Level 1 - Workstation"]
    """
    lines = [line.strip() for line in text.splitlines()]
    profiles: List[str] = []
    capture = False
    for line in lines:
        if "profile applicability" in line.lower():
            capture = True
            continue
        if capture:
            if not line:
                break
            if line.startswith(("\u2022", "-", "*")):
                cleaned = line.lstrip("\u2022-*").strip()
                if cleaned:
                    profiles.append(cleaned)
            else:
                break
    return profiles


def extract_section_info(text: str) -> Dict[str, Any]:
    """
    Chunk metninden CIS section numarasi, basligi ve degerlendirme statusunu cikarir.

    Ornek:
      '5.1.1 Ensure permissions on /etc/ssh/sshd_config are configured (Automated)'
      -> section_id='5.1.1', section_title='Ensure ...', assessment_status='Automated'
    """
    meta: Dict[str, Any] = {}

    # N.N.N Ensure ... veya N.N.N.N Ensure ... — en fazla 4 seviye
    pattern = re.search(
        r"(\d+(?:\.\d+){1,3})\s+(Ensure\s+[^\n(]+?)(?:\s*\((Automated|Manual)\))?(?:\n|$)",
        text,
        re.IGNORECASE,
    )
    if pattern:
        meta["section_id"] = pattern.group(1)
        meta["section_title"] = pattern.group(2).strip()
        if pattern.group(3):
            meta["assessment_status"] = pattern.group(3)

    # section_id bulunamazsa assessment_status'u yine de cek
    if "assessment_status" not in meta:
        status_match = re.search(r"\((Automated|Manual)\)", text, re.IGNORECASE)
        if status_match:
            meta["assessment_status"] = status_match.group(1)

    return meta


def is_toc_or_frontmatter(text: str) -> bool:
    """
    Sayfanin TOC veya on bolum (kapak, terimler, icindekiler) olup olmadigini
    tespit eder. Bu sayfalar indexe alinmamali.
    """
    lower = text.lower()
    frontmatter_keywords = [
        "table of contents",
        "terms of use",
        "acknowledgements",
        "profile definitions",
        "typographical conventions",
        "recommendation definitions",
        "important usage information",
        "consensus guidance",
        "intended audience",
    ]
    for kw in frontmatter_keywords:
        if kw in lower:
            return True
    # TOC karakteristigi: nokta + sayi satirlari - 'Configure SSH ......... 521'
    dotted_lines = re.findall(r"\.{4,}\s*\d+", text)
    if len(dotted_lines) >= 4:
        return True
    # Audit checklist sayfasi: "Recommendation Set Correctly Yes No" tablosu
    if "set correctly" in lower and ("yes" in lower or "no" in lower):
        return True
    return False


def extract_cis_chunk_metadata(text: str) -> Dict[str, Any]:
    """
    Tek bir chunk metninden CIS'e ozel chunk-level metadata doner.

    Sema:
      {
        "profile_applicability": ["Level 1 - Server", ...] | None,
        "section_id":        "5.1.1" | None,
        "section_title":     "Ensure ..." | None,
        "assessment_status": "Automated" | "Manual" | None,
      }
    """
    profiles = extract_profile_applicability(text)
    section = extract_section_info(text)

    return {
        "profile_applicability": profiles or None,
        "section_id": section.get("section_id"),
        "section_title": section.get("section_title"),
        "assessment_status": section.get("assessment_status"),
    }
