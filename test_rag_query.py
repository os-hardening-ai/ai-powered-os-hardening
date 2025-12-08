"""Test RAG system end-to-end"""
from __future__ import annotations
import sys
import os
import io

# UTF-8 encoding fix for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    os.system('chcp 65001 > nul 2>&1')

import requests
import json

API_URL = "http://localhost:8000/api/chat"

# Test query that requires CIS Benchmark RAG knowledge
test_query = "Ubuntu 22.04'te cramfs nasıl devre dışı bırakılır?"

print("=" * 80)
print("RAG SYSTEM END-TO-END TEST")
print("=" * 80)
print(f"\n📝 Test Query: {test_query}")
print(f"🎯 Expected: Should retrieve CIS Benchmark info about cramfs\n")

try:
    response = requests.post(
        API_URL,
        json={"question": test_query},
        timeout=30
    )

    if response.status_code == 200:
        result = response.json()

        print("✅ API Response Status: 200 OK\n")
        print(f"🔀 Layer Path: {result.get('layer_path', 'N/A')}")
        print(f"🛡️  Safety: {result.get('safety_category', 'N/A')}")
        print(f"🎯 Intent: {result.get('intent_type', 'N/A')}")
        print(f"⏱️  Time: {result.get('total_time_s', 'N/A')}s")
        print(f"💰 Cost: ${result.get('estimated_cost', 'N/A')}")

        # Check RAG sources
        print(f"\n📚 RAG Sources: {len(result.get('rag_sources', []))} found")
        if result.get('rag_sources'):
            print("\nRAG Sources Details:")
            for idx, source in enumerate(result.get('rag_sources', []), 1):
                print(f"  {idx}. Score: {source.get('score', 0):.3f}")
                print(f"     Source: {source.get('source', 'N/A')}")
                print(f"     Section: {source.get('section', 'N/A')}\n")

        # Check answer content
        answer = result.get('answer', '')
        print(f"📄 Answer Length: {len(answer)} characters")
        print("\n" + "─" * 80)
        print("ANSWER CONTENT:")
        print("─" * 80)
        print(answer)
        print("─" * 80)

        # Verify RAG integration
        print("\n🔍 RAG Integration Verification:")
        if result.get('rag_sources'):
            print("  ✅ RAG sources retrieved")
        else:
            print("  ❌ No RAG sources found")

        if 'cramfs' in answer.lower() or 'cis' in answer.lower():
            print("  ✅ Answer contains relevant keywords")
        else:
            print("  ⚠️  Answer may not be using RAG context")

        if result.get('layer_path') == '1→2→3B':
            print("  ✅ Correct routing path (Info Pipeline)")
        else:
            print(f"  ⚠️  Unexpected path: {result.get('layer_path')}")

    else:
        print(f"❌ API Error: {response.status_code}")
        print(response.text)

except Exception as e:
    print(f"❌ Test Failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
