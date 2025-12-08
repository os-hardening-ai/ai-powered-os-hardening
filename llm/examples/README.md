# Examples

This folder contains example scripts demonstrating how to use the AI-Powered OS Hardening system.

## Available Examples

### 1. Simple Chat ([simple_chat.py](simple_chat.py))
Basic interactive chat with the security assistant.

**Usage**:
```bash
# Interactive mode
python examples/simple_chat.py

# Single question mode
python examples/simple_chat.py "SSH nedir?"
```

**Features**:
- Interactive question-answer loop
- Configuration management
- RAG source display
- Error handling

**Example Output**:
```
[SORU] SSH nedir?
[BEKLEYIN] Cevap hazırlanıyor...

============================================================
[CEVAP]
============================================================
SSH (Secure Shell), ağ üzerinden güvenli uzaktan bağlantı...

============================================================
[KAYNAKLAR]
============================================================

1. CIS_Ubuntu_22_04.pdf (Skor: 0.89)
   Bölüm: 5.2 SSH Server Configuration
```

---

### 2. Script Generation ([script_generation.py](script_generation.py))
Examples of generating hardening scripts for different scenarios.

**Usage**:
```bash
python examples/script_generation.py
```

**Examples Included**:
1. SSH Hardening for Ubuntu 22.04
2. Firewall Rules for Windows Server 2022
3. RDP Hardening for Windows 10
4. Script with Zero Trust Enrichment for Debian 11

**Example**:
```python
ctx = RequestContext(
    user_input="Ubuntu 22.04 için SSH hardening scripti oluştur",
    os_type="ubuntu_22_04",
    role="admin",
    security_level="high"
)
result = pipeline.run(ctx)
```

**Output**:
- Generated bash/PowerShell scripts
- Layer path (e.g., 1→2→3C)
- Cost estimation
- Zero Trust enrichment (ZT principles, standards, rollback)

---

### 3. Info Queries ([info_queries.py](info_queries.py))
Examples of asking informational questions about security concepts.

**Usage**:
```bash
python examples/info_queries.py
```

**Examples Included**:
1. What is SSH?
2. Zero Trust Architecture principles
3. CIS Benchmarks overview
4. Firewall concepts (stateful vs stateless)
5. NIST standards (NIST 800-207)

**Example**:
```python
ctx = RequestContext(
    user_input="Zero Trust Architecture nedir? Temel prensipleri nelerdir?",
    os_type="ubuntu_22_04",
    role="user"
)
result = pipeline.run(ctx)
```

**Output**:
- Detailed answers with RAG sources
- Layer path (1→2→3B)
- Cost estimation
- Source citations

---

### 4. Different OS Types ([different_os_types.py](different_os_types.py))
Demonstrates script generation for various operating systems.

**Usage**:
```bash
python examples/different_os_types.py
```

**Supported OS Types**:
1. Ubuntu 22.04 - SSH hardening
2. Debian 11 - Firewall configuration
3. CentOS 7 - SELinux configuration
4. Windows Server 2022 - Security hardening
5. Windows 10 - RDP security
6. RHEL 8 - Audit configuration

**Example**:
```python
ctx = RequestContext(
    user_input="SSH güvenlik ayarları için script oluştur",
    os_type="ubuntu_22_04",  # or debian_11, centos_7, windows_10, etc.
    role="admin",
    security_level="high"
)
```

**Output**:
- OS-specific scripts (bash for Linux, PowerShell for Windows)
- Layer path
- Cost estimation

---

## Common Usage Patterns

### Basic Info Query
```python
from llm.models import get_llm_clients
from llm.pipeline_v2 import SecurityPipeline, RequestContext

llm_small, llm_large = get_llm_clients()
pipeline = SecurityPipeline(llm_small=llm_small, llm_large=llm_large, use_rag=True)

ctx = RequestContext(
    user_input="CIS Benchmarks nedir?",
    os_type="ubuntu_22_04",
    role="user"
)

result = pipeline.run(ctx)
print(result.answer)
```

### Script Generation
```python
from llm.models import get_llm_clients
from llm.pipeline_v2 import SecurityPipeline, RequestContext

llm_small, llm_large = get_llm_clients()
pipeline = SecurityPipeline(llm_small=llm_small, llm_large=llm_large, use_rag=True)

ctx = RequestContext(
    user_input="Windows Server 2022 için firewall scripti oluştur",
    os_type="windows_server_2022",
    role="admin",
    security_level="high"
)

result = pipeline.run(ctx)
print(result.answer)  # PowerShell script
```

### With Zero Trust Enrichment
```python
result = pipeline.run(ctx)

# Access ZT enrichment if available
if hasattr(result, 'zt_enrichment') and result.zt_enrichment:
    print(f"ZT Principles: {result.zt_enrichment.zt_principles}")
    print(f"Standards: {result.zt_enrichment.standards}")
    print(f"Impact Level: {result.zt_enrichment.impact_level}")
    print(f"Rollback: {result.zt_enrichment.rollback_approach}")
```

---

## Environment Setup

All examples require:

1. **API Key**: Set GROQ_API_KEY environment variable
   ```bash
   export GROQ_API_KEY="your-key-here"
   ```

2. **Dependencies**: Install requirements
   ```bash
   pip install -r requirements.txt
   ```

3. **Python Version**: Python 3.10+

---

## Output Structure

All examples return a `PipelineResult` or specific result type with:

- `success`: Boolean indicating success
- `answer`: The generated response/script
- `layer_path`: Path through the 4-layer pipeline (e.g., "1→2→3C")
- `estimated_cost`: Estimated API cost in USD
- `intent`: Detected intent type
- `zt_enrichment`: Zero Trust enrichment (for action requests)
- `validation`: Output validation results (for action requests)
- `rag_sources`: Retrieved sources (when RAG is used)

---

## Troubleshooting

### "API key not found"
```bash
# Set the environment variable
export GROQ_API_KEY="your-key-here"
```

### "Module not found"
```bash
# Install dependencies
pip install -r requirements.txt
```

### "Connection refused"
Make sure the API server is running if using API examples:
```bash
python -m main
```

---

## Next Steps

After exploring these examples:

1. Read [docs/guides/QUICKSTART_BASIT.md](../docs/guides/QUICKSTART_BASIT.md) for a simple guide
2. Check [docs/TESTING_GUIDE.md](../docs/TESTING_GUIDE.md) for testing
3. Review [docs/API.md](../docs/API.md) for API usage
4. Run tests: `python tests/run_all_tests.py`

---

## Contributing

To add a new example:

1. Create a new `.py` file in this folder
2. Follow the existing structure
3. Include clear docstrings and comments
4. Add usage instructions
5. Update this README

---

For more information, see the [main documentation](../docs/README.md).
