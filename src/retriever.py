import os
import json

_sop_documents: list[dict] | None = None


def load_sops_from_dynamodb() -> list[dict]:
    global _sop_documents
    if _sop_documents is not None:
        return _sop_documents
    print(f"   [Retriever] Loading SOPs from local JSON file...")
    try:
        with open("data/sops.json", "r", encoding="utf-8") as f:
            items = json.load(f)
        for item in items:
            item["sop_id"] = item["id"]
        items.sort(key=lambda x: x.get("sop_id", ""))
        _sop_documents = items
        print(f"   [Retriever] Loaded {len(items)} SOP documents from JSON.")
        return _sop_documents
    except Exception as e:
        print(f"   [Retriever] ERROR loading SOPs from JSON: {e}")
        raise


def simple_string_match(query: str, text: str) -> float:
    """Simple string matching for demonstration purposes."""
    query = query.lower()
    text = text.lower()
    score = 0.0
    
    # Count matching words
    query_words = query.split()
    text_words = text.split()
    
    matching_words = set(query_words) & set(text_words)
    if matching_words:
        score = len(matching_words) / len(query_words)
    
    # Bonus for exact phrase matches
    if query in text:
        score += 0.5
    
    return min(score, 1.0)


def retrieve_relevant_sops(query_text: str, top_k: int = 3) -> list[dict]:
    """
    Simple string-based search over the SOP collection.

    Args:
        query_text: Natural-language description of the network fault.
        top_k:      Number of top SOPs to return (default 3).

    Returns:
        List of SOP dicts sorted by relevance (highest first).
        Each dict contains: sop_id, content, score, and any other fields.
    """
    sops = load_sops_from_dynamodb()
    if not sops:
        return []

    print(f"   [Retriever] Using simple string matching for SOP retrieval...")
    
    scored = []
    for sop in sops:
        content = sop.get("content", "")
        score = simple_string_match(query_text, content)
        scored.append({**sop, "score": float(score)})

    scored.sort(key=lambda x: x["score"], reverse=True)
    top = scored[:top_k]

    for s in top:
        print(f"   [Retriever] Retrieved: {s['sop_id']} | Score: {s['score']:.4f}")

    return top


# ---------------------------------------------------------------------------
# Legacy alias — kept so existing callers (main.py) are not broken.
# ---------------------------------------------------------------------------
def retrieve_sops(query: str, k: int = 3) -> list[str]:
    """Return top-k SOP content strings (legacy interface)."""
    results = retrieve_relevant_sops(query_text=query, top_k=k)
    return [r["content"] for r in results]


def get_all_sop_embeddings() -> list[dict]:
    """
    Legacy function for compatibility.
    Returns all SOP documents with dummy embeddings.
    """
    sops = load_sops_from_dynamodb()
    return [
        {
            "sop_id": sop.get("sop_id", f"DOC-{i}"),
            "content": sop.get("content", ""),
            "embedding": [0.0] * 384,  # Dummy embedding
        }
        for i, sop in enumerate(sops)
    ]


def get_query_embedding(query_text: str) -> list[float]:
    """
    Legacy function for compatibility.
    Returns dummy embedding.
    """
    return [0.0] * 384  # Dummy embedding
