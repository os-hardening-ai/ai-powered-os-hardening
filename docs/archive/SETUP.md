# Kurulum Rehberi

## Sistem Gereksinimleri

- Python 3.12+
- 8GB RAM (minimum)
- 20GB disk alanı (RAG index için)

## Kurulum Adımları

### 1. Repository Clone

```bash
git clone https://github.com/os-hardening-ai/ai-powered-os-hardening.git
cd ai-powered-os-hardening
```

### 2. Virtual Environment (Önerilen)

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# veya
venv\Scripts\activate  # Windows
```

### 3. Dependencies

```bash
pip install -r requirements.txt
```

### 4. Environment Variables

`.env` dosyası oluşturun:

```env
# LLM Provider
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_your_key_here

# Embedding
EMBEDDING_PROVIDER=cohere
COHERE_API_KEY=your_cohere_key

# Vector Store
VECTOR_STORE_PROVIDER=qdrant
QDRANT_URL=http://localhost:6333
```

### 5. RAG Index Oluşturma

```bash
python -m scripts.build_index_ubuntu
```

### 6. API Başlatma

```bash
python -m main
```

## Ücretsiz Groq Kurulumu

1. https://console.groq.com/keys adresine gidin
2. Ücretsiz hesap oluşturun
3. API key alın
4. `.env` dosyasına ekleyin

## Troubleshooting

**Problem**: ModuleNotFoundError  
**Çözüm**: `pip install -r requirements.txt`

**Problem**: Qdrant connection error  
**Çözüm**: Qdrant'ı Docker ile başlatın: `docker run -p 6333:6333 qdrant/qdrant`
