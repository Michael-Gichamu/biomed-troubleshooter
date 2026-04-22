"""Per-equipment-model RAG cache used by the ``rag_node``.

The cache is populated in a daemon thread with a 5-second budget so that a
cold-start sentence-transformers load does not block the first user turn.
Subsequent turns for the same equipment model return from the cache.
"""

import threading

# Cache for RAG results per equipment model (loaded once, reused forever).
_rag_cache: dict[str, list] = {}


def _get_cached_rag_knowledge(equipment_model: str, force_refresh: bool = False) -> list:
    """Get diagnostic knowledge from RAG, caching per equipment model.

    Truly non-blocking: uses threading.Thread + join(timeout=5). A
    ThreadPoolExecutor would call ``shutdown(wait=True)`` on ``__exit__`` and
    block until the thread finishes — which is why initialisation used to take
    5 minutes. ``Thread.join(timeout)`` returns once the timeout expires and
    does **not** wait for the thread. The daemon thread keeps running in the
    background so RAG will be ready for later conversations.
    """
    if not force_refresh and equipment_model in _rag_cache:
        return _rag_cache[equipment_model]

    from src.studio.tools import query_diagnostic_knowledge

    result_holder: list = [None]

    def _do_query():
        try:
            result_holder[0] = query_diagnostic_knowledge.invoke(
                {
                    "query": "diagnostic procedures troubleshooting fault",
                    "equipment_model": equipment_model,
                    "top_k": 5,
                }
            )
        except Exception as exc:
            print(f"[RAG] Query thread error (non-fatal): {exc}")

    t = threading.Thread(target=_do_query, daemon=True, name=f"rag-query-{equipment_model}")
    t.start()
    t.join(timeout=5.0)  # returns immediately after 5 s; does NOT block

    if t.is_alive():
        # sentence-transformers still loading — proceed without RAG now.
        # Not cached so the next conversation will retry.
        print("[RAG] Cold-start timeout -- proceeding without RAG knowledge.")
        return []

    r = result_holder[0]
    results = r.get("results", []) if isinstance(r, dict) else []
    _rag_cache[equipment_model] = results
    return results
