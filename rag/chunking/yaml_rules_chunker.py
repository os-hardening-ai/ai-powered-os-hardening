from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any

import yaml

from rag.chunking.base import IChunker, Chunk
from rag.embeddings import get_embedding_client
from rag.embeddings.base import IEmbeddingClient


def _build_chunk_text(rule: Dict[str, Any]) -> str:
    """
    Her kural dict'inden RAG için zengin bir metin blogu üretir.
    Title + description + directive + config + script içeriği tek chunk.
    """
    parts: List[str] = []

    rule_id = rule.get("id", "")
    title = rule.get("title", "")
    section = rule.get("section", "")
    category = rule.get("category", "")
    level = rule.get("level", "")
    description = rule.get("description", "")
    auto_remediate = rule.get("auto_remediate", True)
    expected_value = rule.get("expected_value", "")
    sshd_directive = rule.get("sshd_directive", "")
    kernel_module = rule.get("kernel_module", "")
    config_files = rule.get("config_files", [])
    tags = rule.get("tags", [])

    # Başlık satırı
    parts.append(f"Rule ID: {rule_id}")
    parts.append(f"Title: {title}")
    parts.append(f"Section: {section} | Category: {category} | Level: {level}")

    if description:
        parts.append(f"\nDescription:\n{description}")

    if expected_value:
        parts.append(f"\nExpected Value: {expected_value}")

    if sshd_directive:
        parts.append(f"SSH Directive: {sshd_directive}")

    if kernel_module:
        parts.append(f"Kernel Module: {kernel_module}")

    if config_files:
        files_str = ", ".join(config_files)
        parts.append(f"Config Files: {files_str}")

    remediation_info = "manual" if not auto_remediate else "automated"
    parts.append(f"Remediation: {remediation_info}")

    if tags:
        parts.append(f"Tags: {', '.join(tags)}")

    # Audit komutu (kısa form — tam script ayrı alanda)
    audit_cmd = rule.get("audit_command", "")
    if audit_cmd:
        parts.append(f"\nAudit Command:\n{audit_cmd}")

    remediation_cmd = rule.get("remediation_command", "")
    if remediation_cmd:
        parts.append(f"\nRemediation Command:\n{remediation_cmd}")

    # Tam script içerikleri (en fazla 1500 karakter — bütünlük için)
    audit_script = rule.get("audit_script_content", "")
    if audit_script:
        truncated = audit_script[:1500]
        if len(audit_script) > 1500:
            truncated += "\n... (truncated)"
        parts.append(f"\nAudit Script:\n{truncated}")

    remediation_script = rule.get("remediation_script_content", "")
    if remediation_script:
        truncated = remediation_script[:1500]
        if len(remediation_script) > 1500:
            truncated += "\n... (truncated)"
        parts.append(f"\nRemediation Script:\n{truncated}")

    return "\n".join(parts)


class YamlRulesChunker(IChunker):
    """
    data/rules/ubuntu_24_04_rules.yaml gibi YAML kural dosyalarını
    her kural için ayrı bir Chunk'a dönüştürür.

    Her chunk: başlık + açıklama + directive + config + script içeriği
    Metadata: rule_id, section, category, level, tags, auto_remediate, source_id
    """

    def __init__(self, embedding_client: IEmbeddingClient | None = None) -> None:
        self.embedding_client = embedding_client or get_embedding_client()

    def chunk(self, source_id: str, path: str) -> List[Chunk]:
        yaml_path = Path(path)
        if not yaml_path.exists():
            raise FileNotFoundError(f"YAML rules file not found: {yaml_path}")

        with yaml_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        rules: List[Dict[str, Any]] = data.get("rules", [])
        if not rules:
            return []

        print(f"[YamlRulesChunker] {len(rules)} kural yuklendi: {yaml_path.name}")

        # Tüm chunk metinlerini üret
        texts = [_build_chunk_text(rule) for rule in rules]

        # Toplu embedding
        print(f"[YamlRulesChunker] {len(texts)} chunk icin embedding hesaplaniyor...")
        embeddings = self.embedding_client.embed_texts(texts)
        print("[YamlRulesChunker] Embedding tamamlandi.")

        chunks: List[Chunk] = []
        for rule, text, emb in zip(rules, texts, embeddings):
            rule_id = rule.get("id", f"rule_{len(chunks)}")
            metadata: Dict[str, Any] = {
                "source_id": source_id,
                "doc_type": "yaml_rule",
                "rule_id": rule_id,
                "section": rule.get("section", ""),
                "category": rule.get("category", ""),
                "level": rule.get("level", ""),
                "auto_remediate": rule.get("auto_remediate", True),
                "manual_review": rule.get("manual_review", False),
                "tags": rule.get("tags", []),
                "sshd_directive": rule.get("sshd_directive", ""),
                "kernel_module": rule.get("kernel_module", ""),
                "config_files": rule.get("config_files", []),
                "num_chars": len(text),
                "title": rule.get("title", ""),
            }

            chunk_id = f"{source_id}-{rule_id}"
            chunks.append(
                Chunk(
                    id=chunk_id,
                    text=text,
                    metadata=metadata,
                    embedding=emb if isinstance(emb, list) else emb.tolist(),
                )
            )

        print(f"[YamlRulesChunker] {len(chunks)} chunk olusturuldu.")
        return chunks
