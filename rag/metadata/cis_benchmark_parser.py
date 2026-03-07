from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List
import re


def parse_benchmark_from_filename(path: Path) -> Dict[str, Any]:
    """
    Örnek dosya adı:
      CIS_Ubuntu_Linux_24.04_LTS_Benchmark_v1.0.0.pdf

    Hedef metadata (doküman-level):
      - benchmark_product: "Ubuntu Linux"
      - os_family: "linux" | "windows"
      - os_version: "24.04" (veya "10", "11" vb.)
      - benchmark_version: "1.0.0"
    """
    name = path.stem  # uzantısız
    parts = name.split("_")
    lower = name.lower()

    meta: Dict[str, Any] = {}

    # ---- OS VERSION ----
    # Önce x.y veya x.y.z formatını yakalamaya çalış
    version_matches = re.findall(r"\d+\.\d+(?:\.\d+)?", name)
    if version_matches:
        meta["os_version"] = version_matches[0]
    else:
        # Olmazsa, plain integer (10, 11 vs) yakalamayı dene
        int_matches = re.findall(r"\b\d+\b", name)
        if int_matches:
            meta["os_version"] = int_matches[0]

    # ---- BENCHMARK VERSION ----
    # v1.0.0, v2.1.3 gibi
    bench_ver_match = re.search(r"v(\d+\.\d+\.\d+)", name, re.IGNORECASE)
    if bench_ver_match:
        meta["benchmark_version"] = bench_ver_match.group(1)

    # ---- PRODUCT (Ubuntu Linux / Windows vs) ----
    # CIS_Ubuntu_Linux_24.04_LTS_Benchmark_v1.0.0
    # -> "Ubuntu Linux"
    benchmark_words = {"benchmark", "benchmarks"}
    product_tokens: List[str] = []

    # İlk parça genelde vendor (CIS), o yüzden 1. indexten başlıyoruz
    for p in parts[1:]:
        pl = p.lower()
        # Versiyon / benchmark kelimesi görünce product tarafı bitmiş say
        if re.match(r"\d+\.\d+(?:\.\d+)?", p) or pl in benchmark_words:
            break
        product_tokens.append(p)

    if product_tokens:
        product = " ".join(product_tokens).replace("-", " ")
        meta["benchmark_product"] = product

    # ---- OS FAMILY ----
    # Ürüne bak, yoksa dosya adına bak
    prod_lower = meta.get("benchmark_product", "").lower()
    check_str = prod_lower or lower

    if "ubuntu" in check_str or "linux" in check_str:
        meta["os_family"] = "linux"
    elif "windows" in check_str:
        meta["os_family"] = "windows"

    return meta


def extract_profile_applicability(text: str) -> List[str]:
    """
    Chunk içinden 'Profile Applicability' bloğunu çıkarır.

    Örnek metin:

      7.2.1 Ensure accounts in /etc/passwd use shadowed passwords
      (Automated)
      Profile Applicability:
      •  Level 1 - Server
      •  Level 1 - Workstation

    Çıktı:
      ["Level 1 - Server", "Level 1 - Workstation"]
    """
    lines = [l.strip() for l in text.splitlines()]
    profiles: List[str] = []
    capture = False

    for line in lines:
        lower = line.lower()

        if "profile applicability" in lower:
            capture = True
            continue

        if capture:
            # Boş satır → block bitti
            if not line:
                break

            # Bullet (•, -, *) ile başlayan satırlar
            if line.startswith(("•", "-", "*")):
                cleaned = line.lstrip("•-*").strip()
                if cleaned:
                    profiles.append(cleaned)
            else:
                # Bullet değilse, muhtemelen başka bölüme geçmiştir
                break

    return profiles


def extract_cis_chunk_metadata(text: str) -> Dict[str, Any]:
    """
    Tek bir chunk metninden CIS'e özel chunk-level metadata döner.

    Şema:
      {
        "profile_applicability": [ ... ] | None
      }
    """
    profiles = extract_profile_applicability(text)

    return {
        "profile_applicability": profiles or None,
    }
