# eval/run_eval.py
from __future__ import annotations

"""
Basit Eval Scripti
------------------
Bu script, pipeline'ı birkaç örnek prompt üzerinde koşturur ve:

- Safety category (beklenen vs. gerçek)
- Intent (beklenen vs. gerçek)

için kaba bir başarı oranı hesaplar.

Kullanım:
    python -m eval.run_eval
veya proje kökünden:
    python eval/run_eval.py
"""

from typing import Tuple

from context import RequestContext
from pipeline import run_pipeline
from models import get_llm_clients
from eval.dataset import get_eval_dataset


def _compare(expected: str | None, actual: str | None) -> Tuple[bool, str]:
    if expected is None:
        return True, "skip"
    if actual is None:
        return False, f"expected={expected}, actual=None"
    if expected == actual:
        return True, f"expected={expected}, actual={actual}"
    return False, f"expected={expected}, actual={actual}"


def main() -> None:
    llm_small, llm_large = get_llm_clients()
    dataset = get_eval_dataset()

    safety_correct = 0
    safety_total = 0

    intent_correct = 0
    intent_total = 0

    print("\n[PIPELINE EVAL BAŞLADI]\n")

    for example in dataset:
        name = example["name"]
        user_input = example["input"]
        expected_intent = example.get("expected_intent")
        expected_safety = example.get("expected_safety")

        print(f"--- CASE: {name} ---")
        print(f"INPUT: {user_input}")

        ctx = RequestContext(
            user_question=user_input,
            os="ubuntu_22_04",
            role="sysadmin",
            security_level="balanced",
            zt_maturity="medium",
        )

        ctx = run_pipeline(ctx, llm_small=llm_small, llm_large=llm_large)

        actual_intent = ctx.intent
        actual_safety = ctx.safety.category if ctx.safety else None

        ok_safety, msg_safety = _compare(expected_safety, actual_safety)
        ok_intent, msg_intent = _compare(expected_intent, actual_intent)

        if expected_safety is not None:
            safety_total += 1
            if ok_safety:
                safety_correct += 1
        if expected_intent is not None:
            intent_total += 1
            if ok_intent:
                intent_correct += 1

        print(f"SAFETY: {msg_safety}")
        print(f"INTENT: {msg_intent}")
        print(f"FINAL_ANSWER (ilk 120 karakter): { (ctx.final_answer or '')[:120]!r}")
        print()

    print("=== ÖZET ===")
    if safety_total > 0:
        print(f"Safety accuracy: {safety_correct}/{safety_total} "
              f"({(safety_correct / safety_total) * 100:.1f}%)")
    else:
        print("Safety accuracy: N/A")

    if intent_total > 0:
        print(f"Intent accuracy: {intent_correct}/{intent_total} "
              f"({(intent_correct / intent_total) * 100:.1f}%)")
    else:
        print("Intent accuracy: N/A")

    print("\n[PIPELINE EVAL BİTTİ]\n")


if __name__ == "__main__":
    main()
