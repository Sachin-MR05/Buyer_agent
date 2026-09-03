from __future__ import annotations

import re

from app.registry.models import MerchantEntryPublic
from app.registry.service import RegistryService

_STOPWORDS = {
    "a", "an", "the", "me", "my", "for", "to", "of", "in", "on", "at",
    "buy", "get", "find", "please", "want", "need", "some", "any", "with",
}


def _tokenize(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in _STOPWORDS and len(w) > 1}


class RegistryTool:
    """search_registry(query) - the Buyer Agent's local, network-free tool
    for shortlisting merchants. Ranks by token overlap between the query
    and each merchant's name + description; ties broken by recency.

    Deliberately simple keyword matching rather than embeddings: the
    registry is small (a handful of shops a person has pasted in), so a
    fast local heuristic beats the latency/cost of an embedding call, and
    it never needs the LLM or the network to run.
    """

    def __init__(self, registry_service: RegistryService):
        self._registry = registry_service

    def search(self, query: str, limit: int) -> list[MerchantEntryPublic]:
        query_tokens = _tokenize(query)
        merchants = self._registry.all_for_matching()
        if not merchants:
            return []

        scored: list[tuple[float, MerchantEntryPublic]] = []
        for m in merchants:
            merchant_tokens = _tokenize(f"{m.shop_name} {m.description}")
            overlap = len(query_tokens & merchant_tokens)
            score = float(overlap)
            scored.append((score, m))

        # If nothing matched at all (e.g. a very generic request like "buy
        # me a gift"), fall back to offering every registered shop rather
        # than an empty list - the LLM/user can still narrow it down.
        if all(score == 0 for score, _ in scored):
            return merchants[:limit]

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [m for score, m in scored[:limit] if score > 0] or merchants[:limit]
