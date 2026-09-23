"""Query Planner and Rewriter for Vennela Web Intelligence."""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Sequence

from .models import ResearchPlan

# Regex patterns for queries that do not require live web search
STATIC_MATH_PATTERNS = [
    r"^\s*what\s+is\s+[\d\.\+\-\*\/\^\(\)\s\%]+\??\s*$",
    r"^\s*calculate\s+[\d\.\+\-\*\/\^\(\)\s\%]+\??\s*$",
    r"^\s*[\d\.\s]+\s*[\+\-\*\/]\s*[\d\.\s]+\s*=?\??\s*$",
    r"^\s*evaluate\s+[\d\.\+\-\*\/\^\(\)\s\%]+\??\s*$",
]

GREETING_CONVERSATION_PATTERNS = [
    r"^\s*(hi|hello|hey|greetings|good\s+(morning|afternoon|evening))\b",
    r"^\s*(who\s+are\s+you|what\s+is\s+your\s+name|how\s+are\s+you(\s+doing)?(\s+today)?)\??\s*$",
    r"^\s*(tell\s+me\s+a\s+joke|thank\s+you|thanks|bye|goodbye)\??\s*$",
]

STATIC_EXPLANATION_PATTERNS = [
    r"^\s*(what\s+is|explain|describe)\s+(photosynthesis|gravity|mitosis|pythagorean\s+theorem|newton'?s\s+laws?|dna)\??\s*$",
    r"^\s*(define|meaning\s+of)\s+[a-z]{3,15}\??\s*$",
    r"^\s*how\s+to\s+(write\s+a\s+(python\s+)?(for\s+loop|function|list\s+comprehension)|reverse\s+a\s+string|print\s+hello\s+world)\??\s*$",
]

# Patterns that explicitly require live / current information
CURRENT_INDICATORS = [
    "current",
    "currently",
    "latest",
    "recent",
    "today",
    "now",
    "this year",
    "this week",
    "upcoming",
    "newest",
    "breaking news",
    "price of",
    "stock price",
    "who is the prime minister",
    "who is the president",
    "who is the chief minister",
    "who is the governor",
    "who won",
    "score of",
    "weather in",
]

# Multi-facet indicators requiring broad or comparative searches
MULTI_QUERY_INDICATORS = [
    "developments",
    "advancements",
    "breakthroughs",
    "trends",
    "ecosystem",
    "landscape",
    "compare",
    "vs",
    "versus",
    "pros and cons",
    "alternatives to",
    "best practices for",
    "state of",
    "market analysis",
    "comprehensive overview",
]


class QueryPlanner:
    """Analyzes intent, determines search necessity, rewrites queries, and decomposes complex topics."""

    def __init__(self, current_year: int | None = None) -> None:
        self.current_year = current_year or datetime.now(timezone.utc).year

    def should_search(self, query: str) -> tuple[bool, str]:
        """Determine if a query requires live web search or can be answered statically."""
        clean = query.strip()
        lower = clean.lower()

        # 1. Math check
        for pat in STATIC_MATH_PATTERNS:
            if re.match(pat, lower):
                return False, "Query is basic arithmetic/math calculation"

        # 2. Greeting / conversation check
        for pat in GREETING_CONVERSATION_PATTERNS:
            if re.match(pat, lower):
                return False, "Query is conversational greeting or persona query"

        # 3. Static knowledge / code syntax check
        for pat in STATIC_EXPLANATION_PATTERNS:
            if re.match(pat, lower):
                return False, "Query is standard static/timeless definition"

        # 4. Check for obvious current indicators
        if any(ind in lower for ind in CURRENT_INDICATORS):
            return True, "Query requires current/live temporal information"

        # 5. Length / complexity fallback
        if len(clean.split()) <= 1 and not clean.endswith("?"):
            return False, "Single-word query without context"

        return True, "Informational query requiring web search"

    def is_multi_search_needed(self, query: str) -> bool:
        """Identify if a topic is broad/comparative enough to warrant multiple queries."""
        lower = query.lower()
        if any(ind in lower for ind in MULTI_QUERY_INDICATORS):
            return True
        # If query has 'and' or 'or' connecting distinct concepts
        if " and " in lower and len(query.split()) > 6:
            return True
        return False

    def rewrite_and_expand(self, query: str) -> list[str]:
        """Rewrite raw user query into optimized search engine queries."""
        clean = query.strip().rstrip("?.! ")
        lower = clean.lower()
        year_str = str(self.current_year)

        # Comparative query: e.g. "Compare X vs Y" or "X vs Y"
        match_vs = re.search(r"(?:compare\s+)?([A-Za-z0-9_\-\.\s]+?)\s+(?:vs\.?|versus)\s+([A-Za-z0-9_\-\.\s]+)", clean, re.IGNORECASE)
        if match_vs:
            item_a = match_vs.group(1).strip()
            item_b = match_vs.group(2).strip()
            return [
                f"{item_a} vs {item_b} comparison {year_str}",
                f"{item_a} pros cons architecture features",
                f"{item_b} pros cons architecture features",
            ]

        # Current position/role query: e.g. "Who is the current Chief Minister of Andhra Pradesh?"
        match_current_role = re.search(r"who\s+is\s+(?:the\s+)?(?:current\s+)?([a-zA-Z\s]+)", clean, re.IGNORECASE)
        if match_current_role and ("chief minister" in lower or "prime minister" in lower or "president" in lower or "ceo" in lower):
            role_target = match_current_role.group(1).strip()
            return [
                f"current {role_target} {year_str}",
                f"{role_target} official government portal latest",
            ]

        # Broad developments/trends query: e.g. "latest AI agent developments"
        if any(ind in lower for ind in ("developments", "advancements", "trends", "breakthroughs", "state of")):
            base_topic = re.sub(r"\b(latest|current|recent|new|today|in\s+\d{4})\b", "", clean, flags=re.IGNORECASE).strip()
            return [
                f"{base_topic} latest developments breakthroughs {year_str}",
                f"{base_topic} architecture state of the art {year_str}",
                f"{base_topic} real world applications and updates",
            ]

        # Standard current query
        if any(ind in lower for ind in ("latest", "current", "recent", "today", "now")):
            if year_str not in clean:
                return [clean, f"{clean} {year_str}"]
            return [clean]

        # Default single focused search query
        return [clean]

    def plan(self, query: str) -> ResearchPlan:
        """Create a full execution plan for a user query."""
        needs_search, reasoning = self.should_search(query)

        if not needs_search:
            return ResearchPlan(
                original_query=query,
                needs_search=False,
                intent="STATIC_OR_CONVERSATIONAL",
                search_queries=[],
                reasoning=reasoning,
                requires_deep_retrieval=False,
            )

        queries = self.rewrite_and_expand(query)
        is_multi = len(queries) > 1
        requires_deep = self.is_multi_search_needed(query)

        return ResearchPlan(
            original_query=query,
            needs_search=True,
            intent="MULTI_FACET_RESEARCH" if is_multi else "FOCUSED_SEARCH",
            search_queries=queries,
            reasoning=reasoning,
            requires_deep_retrieval=requires_deep,
        )
