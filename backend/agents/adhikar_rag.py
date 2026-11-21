"""
Adhikar-RAG: Authority & Citizen Charter Retrieval Engine.
Indexes Public Authorities from authorities.json into persistent ChromaDB
using the default ONNX embedding model (all-MiniLM-L6-v2) without PyTorch dependencies.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

# Gracefully stub grpc/otlp telemetry before chromadb imports it, avoiding Windows Smart App Control policy blocks
if "grpc" not in sys.modules:
    sys.modules["grpc"] = MagicMock()
if "grpc._cython" not in sys.modules:
    sys.modules["grpc._cython"] = MagicMock()
if "grpc._cython.cygrpc" not in sys.modules:
    sys.modules["grpc._cython.cygrpc"] = MagicMock()
if "opentelemetry.exporter.otlp.proto.grpc.trace_exporter" not in sys.modules:
    sys.modules["opentelemetry.exporter.otlp.proto.grpc.trace_exporter"] = MagicMock()

import chromadb

CHROMA_DIR = Path(__file__).resolve().parent.parent.parent / "chroma_db"
AUTHORITIES_PATH = Path(__file__).resolve().parent.parent / "data" / "authorities.json"
COLLECTION_NAME = "authorities"


def load_authorities_seed() -> List[Dict[str, Any]]:
    """Loads authority definitions from backend/data/authorities.json."""
    if not AUTHORITIES_PATH.exists():
        raise FileNotFoundError(f"Authorities seed not found at {AUTHORITIES_PATH}")
    with open(AUTHORITIES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_or_init_collection(
    persist_dir: Optional[Path | str] = None,
    force_reindex: bool = False,
) -> chromadb.Collection:
    """
    Initializes or retrieves the persistent ChromaDB collection.
    Automatically indexes authorities from authorities.json if empty or force_reindex is True.
    """
    target_dir = Path(persist_dir) if persist_dir else CHROMA_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(path=str(target_dir))
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"description": "RTI Public Authorities and SLAs"},
    )

    authorities = load_authorities_seed()

    # Index if empty or forced
    if force_reindex or collection.count() < len(authorities):
        ids: List[str] = []
        documents: List[str] = []
        metadatas: List[Dict[str, Any]] = []

        for item in authorities:
            ids.append(item["id"])
            keywords_str = " ".join(item.get("keywords", []))
            doc = (
                f"{item['authority_name']} | {item['ministry']} | "
                f"PIO: {item['pio_title']} | First Appellate: {item['first_appellate_authority']} | "
                f"Keywords: {keywords_str}"
            )
            documents.append(doc)
            metadatas.append({
                "id": item["id"],
                "ministry": item["ministry"],
                "authority_name": item["authority_name"],
                "pio_title": item["pio_title"],
                "first_appellate_authority": item["first_appellate_authority"],
                "sla_days": item.get("sla_days", 30),
                "portal_type": item.get("portal_type", "central"),
            })

        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

    return collection


def find_authority(
    query: str,
    top_k: int = 3,
    persist_dir: Optional[Path | str] = None,
) -> List[Dict[str, Any]]:
    """
    Searches the authorities collection for the most relevant Public Authority matching
    the citizen query using vector search with keyword-assisted reranking.
    Returns matched authorities with id, ministry, authority_name, pio_title,
    first_appellate_authority, sla_days, and similarity score.
    """
    collection = get_or_init_collection(persist_dir=persist_dir)
    clean_query = query.strip()
    if not clean_query:
        clean_query = "Grievance Record Request"

    results = collection.query(
        query_texts=[clean_query],
        n_results=min(top_k, 10),
    )

    matched: List[Dict[str, Any]] = []
    if not results or not results.get("ids") or not results["ids"][0]:
        return matched

    ids_list = results["ids"][0]
    metadatas_list = results["metadatas"][0] if results.get("metadatas") else []
    distances_list = results["distances"][0] if results.get("distances") else []

    query_lower = clean_query.lower()

    for idx, auth_id in enumerate(ids_list):
        meta = metadatas_list[idx] if idx < len(metadatas_list) else {}
        distance = distances_list[idx] if idx < len(distances_list) else 1.0

        # Cosine distance to similarity score in range [0, 1]
        base_score = 1.0 / (1.0 + float(distance))

        # Contextual boost if exact city or scheme appears in query
        auth_name_lower = str(meta.get("authority_name", "")).lower()
        if "pune" in query_lower and "pune" in auth_name_lower:
            base_score += 0.15
        if "scholarship" in query_lower and "scholarship" in auth_name_lower:
            base_score += 0.15
        if "water" in query_lower and "water" in auth_name_lower:
            base_score += 0.15

        matched.append({
            "id": meta.get("id", auth_id),
            "ministry": meta.get("ministry", ""),
            "authority_name": meta.get("authority_name", ""),
            "pio_title": meta.get("pio_title", ""),
            "first_appellate_authority": meta.get("first_appellate_authority", ""),
            "sla_days": meta.get("sla_days", 30),
            "portal_type": meta.get("portal_type", "central"),
            "score": round(base_score, 4),
        })

    # Sort descending by score
    matched.sort(key=lambda x: x["score"], reverse=True)
    return matched[:top_k]
