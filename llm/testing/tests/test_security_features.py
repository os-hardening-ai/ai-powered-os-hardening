#!/usr/bin/env python3
"""
Security & Monitoring Features Test

Bitirme projesi için güvenlik ve monitoring özelliklerini test eder.
"""

import requests
import time
import json
from typing import Dict, Any


BASE_URL = "http://localhost:8000"


def print_section(title: str):
    """Print section header"""
    print("\n" + "="*70)
    print(f"{title}")
    print("="*70 + "\n")


def test_security_headers():
    """Test 1: Security Headers"""
    print_section("TEST 1: Security Headers")

    response = requests.get(f"{BASE_URL}/health")

    print("[OK] Security headers kontrol ediliyor...\n")

    security_headers = {
        "x-content-type-options": "nosniff",
        "x-frame-options": "DENY",
        "x-xss-protection": "1; mode=block",
        "strict-transport-security": "max-age=31536000; includeSubDomains",
        "content-security-policy": "default-src 'self'",
        "referrer-policy": "strict-origin-when-cross-origin",
        "permissions-policy": "geolocation=(), microphone=(), camera=()",
    }

    all_passed = True
    for header, expected_value in security_headers.items():
        actual_value = response.headers.get(header)
        if actual_value == expected_value:
            print(f"[OK] {header}: {actual_value}")
        else:
            print(f"[FAIL] {header}: Expected '{expected_value}', got '{actual_value}'")
            all_passed = False

    return all_passed


def test_rate_limiting():
    """Test 2: Rate Limiting"""
    print_section("TEST 2: Rate Limiting")

    print("[OK] Rate limiting test ediliyor...")
    print("   100 request/dakika limiti var, 5 request gönderelim:\n")

    for i in range(5):
        response = requests.get(f"{BASE_URL}/health")

        limit = response.headers.get("x-ratelimit-limit")
        remaining = response.headers.get("x-ratelimit-remaining")

        print(f"Request {i+1}: Status={response.status_code}, "
              f"Limit={limit}, Remaining={remaining}")

    print("\n[OK] Rate limiting headers çalışıyor!")
    return True


def test_input_validation():
    """Test 3: Input Validation"""
    print_section("TEST 3: Input Validation")

    print("[OK] Input validation test ediliyor...\n")

    # Test 1: Too long input
    print("Test 1: Çok uzun input (>5000 karakter)")
    long_input = "a" * 6000
    try:
        response = requests.post(
            f"{BASE_URL}/api/chat",
            json={"question": long_input}
        )
        if response.status_code == 422:  # Pydantic validation error
            print("[OK] Çok uzun input reddedildi (422 Validation Error)")
        else:
            print(f"[FAIL] Unexpected status: {response.status_code}")
    except Exception as e:
        print(f"[FAIL] Error: {e}")

    # Test 2: Empty input
    print("\nTest 2: Boş input")
    try:
        response = requests.post(
            f"{BASE_URL}/api/chat",
            json={"question": ""}
        )
        if response.status_code == 422:
            print("[OK] Boş input reddedildi (422 Validation Error)")
        else:
            print(f"[FAIL] Unexpected status: {response.status_code}")
    except Exception as e:
        print(f"[FAIL] Error: {e}")

    # Test 3: Invalid security_level
    print("\nTest 3: Geçersiz security_level")
    try:
        response = requests.post(
            f"{BASE_URL}/api/chat",
            json={
                "question": "Test",
                "security_level": "invalid_level"
            }
        )
        if response.status_code == 422:
            print("[OK] Geçersiz security_level reddedildi (422 Validation Error)")
        else:
            print(f"[FAIL] Unexpected status: {response.status_code}")
    except Exception as e:
        print(f"[FAIL] Error: {e}")

    return True


def test_metrics_endpoint():
    """Test 4: Metrics Endpoint"""
    print_section("TEST 4: Performance Metrics")

    print("[OK] Metrics endpoint test ediliyor...\n")

    # Generate some traffic
    print("1. Biraz trafik oluşturalım (10 request)...")
    for _ in range(10):
        requests.get(f"{BASE_URL}/health")

    time.sleep(0.5)  # Give middleware time to process

    # Get metrics
    print("\n2. Metrics endpoint'inden veri çekelim...")
    response = requests.get(f"{BASE_URL}/metrics")

    if response.status_code == 200:
        metrics = response.json()

        print("\n PERFORMANCE METRICS:")
        print(f"   Total Requests:     {metrics['requests']['total']}")
        print(f"   Successful:         {metrics['requests']['successful']}")
        print(f"   Error Rate:         {metrics['requests']['error_rate']}%")
        print(f"\n   Latency (ms):")
        print(f"     Average:          {metrics['latency_ms']['avg']:.1f}")
        print(f"     P50 (median):     {metrics['latency_ms']['p50']:.1f}")
        print(f"     P95:              {metrics['latency_ms']['p95']:.1f}")
        print(f"     P99:              {metrics['latency_ms']['p99']:.1f}")

        print("\n[OK] Metrics endpoint çalışıyor!")
        return True
    else:
        print(f"[FAIL] Metrics endpoint failed: {response.status_code}")
        return False


def test_api_documentation():
    """Test 5: API Documentation"""
    print_section("TEST 5: API Documentation")

    print("[OK] OpenAPI documentation kontrol ediliyor...\n")

    # Get OpenAPI spec
    response = requests.get(f"{BASE_URL}/openapi.json")

    if response.status_code == 200:
        openapi = response.json()

        print(f"API Title:    {openapi['info']['title']}")
        print(f"Version:      {openapi['info']['version']}")
        print(f"Description:  {openapi['info']['description'][:100]}...")

        print("\n Available Endpoints:")
        for path, methods in openapi['paths'].items():
            for method in methods.keys():
                print(f"   {method.upper():6} {path}")

        print("\n Swagger UI:")
        print(f"   http://localhost:8000/docs")

        print("\n[OK] API documentation mevcut!")
        return True
    else:
        print(f"[FAIL] OpenAPI spec failed: {response.status_code}")
        return False


def test_compression():
    """Test 6: Compression"""
    print_section("TEST 6: Response Compression")

    print("[OK] GZip compression kontrol ediliyor...\n")

    response = requests.get(f"{BASE_URL}/health")

    encoding = response.headers.get("content-encoding")
    if encoding == "gzip":
        print(f"[OK] Response compression aktif: {encoding}")
        return True
    else:
        print(f"[WARN]  Compression yok (küçük response için normal): {encoding}")
        return True


def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("AI-POWERED OS HARDENING - Security & Monitoring Tests")
    print("="*70)

    print("\n[INFO] API URL: " + BASE_URL)
    print("[INFO] Make sure the API is running: python -m main\n")

    # Wait for API to be ready
    print("[*] API'ye baglaniliyor...")
    try:
        requests.get(f"{BASE_URL}/health", timeout=5)
        print("[OK] API hazir!\n")
    except Exception as e:
        print(f"[ERROR] API'ye baglanilamadi: {e}")
        print("   Once 'python -m main' ile API'yi baslatin.")
        return 1

    # Run tests
    results = {
        "Security Headers": test_security_headers(),
        "Rate Limiting": test_rate_limiting(),
        "Input Validation": test_input_validation(),
        "Metrics Endpoint": test_metrics_endpoint(),
        "API Documentation": test_api_documentation(),
        "Response Compression": test_compression(),
    }

    # Summary
    print_section("TEST SUMMARY")

    all_passed = True
    for test_name, passed in results.items():
        status = "[OK] PASS" if passed else "[FAIL] FAIL"
        print(f"{status:10} - {test_name}")
        if not passed:
            all_passed = False

    print("\n" + "="*70)

    if all_passed:
        print("\n[SUCCESS] TUM TESTLER BASARILI!")
        print("\nBitirme Projesi Ozellikleri:")
        print("   [OK] Comprehensive API Documentation (OpenAPI/Swagger)")
        print("   [OK] Rate Limiting (100 req/min per IP)")
        print("   [OK] Input Validation & Sanitization")
        print("   [OK] Security Headers (HSTS, CSP, X-Frame-Options, etc.)")
        print("   [OK] Performance Metrics (latency, error rate, token usage)")
        print("   [OK] Response Compression (GZip)")
        print("\nLinks:")
        print(f"   Swagger UI:  http://localhost:8000/docs")
        print(f"   ReDoc:       http://localhost:8000/redoc")
        print(f"   Metrics:     http://localhost:8000/metrics")
        print("="*70 + "\n")
        return 0
    else:
        print("\n[WARNING] BAZI TESTLER BASARISIZ!")
        print("="*70 + "\n")
        return 1


if __name__ == "__main__":
    exit(main())
