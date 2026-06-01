"""
Different OS Types Integration Tests
--------------------------------------
Farklı işletim sistemlerinde SSH hardening script üretimini test eder.

Çalıştırma:
    python tests/integration/test_different_os_types.py
"""

import sys
import os

# NOT: pytest altında sys.stdout/stderr DEĞİŞTİRİLMEZ — capture mekanizmasını bozar
# ("I/O operation on closed file" → tüm suite toplanmaz). Yalnız standalone script
# olarak çalışınca (pytest import edilmemişken) Windows konsol UTF-8 düzeltmesi uygulanır.
if sys.platform == 'win32' and "pytest" not in sys.modules:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    os.system('chcp 65001 > nul')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from llm.clients import get_llm_clients
from llm.pipelines.secure_v2 import SecurePipelineV2
from llm.core.context import RequestContext


OS_TYPES = [
    ("Ubuntu 22.04",        "ubuntu_22_04",         "SSH hardening yapılandırması nasıl yapılır?"),
    ("Debian 11",           "debian_11",            "SSH güvenliğini nasıl sağlarım?"),
    ("CentOS 7",            "centos_7",             "SSH servisini nasıl güvenli hale getiririm?"),
    ("Windows Server 2022", "windows_server_2022",  "SSH ve uzak erişim güvenliğini nasıl sağlarım?"),
    ("Windows 10",          "windows_10",           "Uzak masaüstü güvenliğini nasıl artırırım?"),
    ("RHEL 8",              "rhel_8",               "SSH hardening nasıl yapılır?"),
]


def run_os_example(os_name: str, os_id: str, question: str):
    print("\n" + "="*70)
    print(f"[OS] {os_name}")
    print("="*70)

    llm_small, llm_large = get_llm_clients()
    pipeline = SecurePipelineV2(
        llm_ultra_fast=llm_small,
        llm_small=llm_small,
        llm_large=llm_large,
        debug=False,
    )

    ctx = RequestContext(
        user_question=question,
        os=os_id,
        role="sysadmin",
        security_level="balanced",
    )

    print(f"Soru: {ctx.user_question}")
    print(f"OS:   {ctx.os}")
    print("\n[PROCESSING]...\n")

    result = pipeline.run(ctx)

    print("[RESULT]")
    print(f"Layer Path: {result.layer_path}")
    print(f"Cost: ${result.estimated_cost:.4f}")
    print("\n[ANSWER]")
    print("-"*70)
    print(result.answer[:800] + ("..." if len(result.answer) > 800 else ""))
    print("-"*70 + "\n")


def main():
    print("\n" + "="*70)
    print("DIFFERENT OS TYPES INTEGRATION TESTS")
    print("="*70)
    print(f"\n{len(OS_TYPES)} farklı OS türünde SSH/uzak erişim hardening testleri\n")

    for os_name, os_id, question in OS_TYPES:
        try:
            run_os_example(os_name, os_id, question)
        except Exception as e:
            print(f"[ERROR] {os_name} failed: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "="*70)
    print("[COMPLETE] All OS type tests finished")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
