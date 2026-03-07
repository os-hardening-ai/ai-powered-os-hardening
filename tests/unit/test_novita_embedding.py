from rag.embeddings import get_embedding_client

if __name__ == "__main__":
    emb = get_embedding_client()

    texts = [
        "Ubuntu 24.04 üzerinde cramfs kernel modülünü disable etmelisin.",
        "CIS benchmark, gereksiz filesystem modüllerinin kapatılmasını önerir."
    ]

    vecs = emb.embed_texts(texts)
    print("Shape:", vecs.shape)  # (2, 4096) bekliyoruz

    q_vec = emb.embed_query("Ubuntu 24.04'te hangi filesystem modülleri disable edilmeli?")
    print("Query vec shape:", q_vec.shape)
