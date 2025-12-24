from __future__ import annotations
import json
import requests


BASE_URL = "http://localhost:8000"


def pretty_print_response(resp_json: dict) -> None:
    print("\n=== RAG CEVABI ===")
    print(f"Sorgu: {resp_json.get('query')}")
    print(f"Top K: {resp_json.get('top_k')}")
    print("\n--- Sonuçlar ---")
    for i, hit in enumerate(resp_json.get("results", []), start=1):
        print(f"\n[{i}] score={hit.get('score'):.4f} id={hit.get('id')}")
        meta = hit.get("metadata", {})
        page = meta.get("page")
        chunk_index = meta.get("chunk_index")
        if page is not None:
            print(f"  (page={page}, chunk_index={chunk_index})")
        print("- text preview:")
        text = hit.get("text", "")
        print("  " + text[:300].replace("\n", " ") + ("..." if len(text) > 300 else ""))


def test_query(query: str, top_k: int = 1) -> None:
    url = f"{BASE_URL}/rag/search"
    payload = {
        "query": query,
        "top_k": top_k,
    }
    print(f"[TEST] POST {url}")
    print(f"[TEST] body = {json.dumps(payload, ensure_ascii=False)}")

    resp = requests.post(url, json=payload)
    print(f"[TEST] status = {resp.status_code}")

    try:
        data = resp.json()
    except Exception:
        print("[TEST] JSON parse edilemedi, raw text:")
        print(resp.text)
        return

    pretty_print_response(data)


if __name__ == "__main__":
    # Buraya istediğin test sorularını koy
    test_query("Ubuntu 24.04 firewall nasıl ayarlanır?", top_k=5)
    print("\n" + "=" * 80 + "\n")
    test_query("1. DÜnya Savaşında Osmanlının müttefiklerini ver bana?", top_k=5)
