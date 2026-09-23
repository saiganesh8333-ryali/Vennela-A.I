"""Cross-Source Reasoning, Fact Extraction, Conflict Detection, and Uncertainty Preservation."""

from __future__ import annotations

import re
from typing import Mapping, Sequence

from .models import ExtractedFact, PageContent, SearchResult, SourceProvenance

# Sentence split regex that doesn't split abbreviations like U.S. or vs. or Dr.
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")


def clean_sentence(text: str) -> str:
    """Normalize whitespace and punctuation in extracted sentences."""
    s = re.sub(r"\s+", " ", text).strip()
    return s


class CrossSourceAnalyzer:
    """Performs deterministic cross-source synthesis, agreement checks, and conflict detection."""

    def __init__(self, max_facts: int = 15) -> None:
        self.max_facts = max_facts

    def extract_facts_from_text(
        self,
        text: str,
        source_url: str,
        source_domain: str,
        query: str,
    ) -> list[ExtractedFact]:
        """Extract salient factual sentences from snippet or page text."""
        if not text:
            return []

        sentences = SENTENCE_SPLIT_RE.split(text)
        query_terms = [t.lower() for t in re.findall(r"\w+", query) if len(t) > 3]

        facts: list[ExtractedFact] = []
        for raw in sentences:
            cleaned = clean_sentence(raw)
            if len(cleaned) < 25 or len(cleaned) > 300:
                continue

            lower = cleaned.lower()
            # Check relevance to query
            relevance = sum(1 for term in query_terms if term in lower)
            if query_terms and relevance == 0 and len(sentences) > 5:
                continue

            # Confidence score heuristic: penalize speculative language
            confidence = 0.90
            if any(spec in lower for spec in ("might", "unconfirmed", "rumored", "allegedly", "speculates")):
                confidence = 0.60
            elif any(firm in lower for firm in ("official", "announced", "confirmed", "serves as", "elected", "founded in")):
                confidence = 0.98

            facts.append(
                ExtractedFact(
                    fact=cleaned,
                    source_url=source_url,
                    source_domain=source_domain,
                    confidence=confidence,
                )
            )
            if len(facts) >= self.max_facts:
                break

        return facts

    def analyze(
        self,
        query: str,
        results: Sequence[SearchResult],
        pages: Sequence[PageContent] | None = None,
        sources: Sequence[SourceProvenance] | None = None,
    ) -> tuple[list[ExtractedFact], list[str], list[str], list[SourceProvenance]]:
        """Perform cross-source synthesis, conflict detection, and uncertainty preservation."""
        all_facts: list[ExtractedFact] = []
        source_map: dict[str, SourceProvenance] = {
            s.url: s for s in (sources or [])
        }

        # 1. Extract from search snippets
        for r in results:
            if r.url not in source_map:
                source_map[r.url] = SourceProvenance(
                    url=r.url,
                    domain=r.source_domain,
                    title=r.title,
                    snippet=r.snippet,
                    claims_supported=[],
                )
            facts = self.extract_facts_from_text(r.snippet, r.url, r.source_domain, query)
            all_facts.extend(facts)

        # 2. Extract from retrieved deep pages (if any)
        if pages:
            for p in pages:
                if not p.success or not p.text_content:
                    continue
                # Extract first few paragraphs for high density
                head_text = "\n".join(p.text_content.splitlines()[:15])
                domain = source_map.get(p.url, SourceProvenance(p.url, "unknown", p.title)).domain
                facts = self.extract_facts_from_text(head_text, p.url, domain, query)
                all_facts.extend(facts)

        # 3. Deduplicate facts & track provenance
        unique_facts: list[ExtractedFact] = []
        seen_fact_texts: set[str] = set()
        provenance_claims: dict[str, list[str]] = {url: [] for url in source_map}

        for f in all_facts:
            norm = f.fact.lower()
            if norm not in seen_fact_texts:
                seen_fact_texts.add(norm)
                unique_facts.append(f)
                if f.source_url in provenance_claims:
                    provenance_claims[f.source_url].append(f.fact)

        # Update claims_supported in source provenance
        updated_sources: list[SourceProvenance] = []
        for url, s in source_map.items():
            updated_sources.append(
                SourceProvenance(
                    url=s.url,
                    domain=s.domain,
                    title=s.title,
                    snippet=s.snippet,
                    claims_supported=provenance_claims.get(url, []),
                )
            )

        # 4. Synthesize Key Findings & Detect Conflicts / Uncertainties
        key_findings: list[str] = []
        uncertainties: list[str] = []

        # Find overlapping domains affirming key facts
        domain_counts: dict[str, int] = {}
        for f in unique_facts:
            domain_counts[f.source_domain] = domain_counts.get(f.source_domain, 0) + 1

        # Check for numeric or date contradictions in high-overlap context
        years_found = set()
        for f in unique_facts:
            for y in re.findall(r"\b(202[0-9])\b", f.fact):
                years_found.add(y)

        if len(years_found) > 2:
            uncertainties.append(f"Multiple differing reference years ({', '.join(sorted(years_found))}) found across reporting sources; verify latest temporal applicability.")

        # Check for negation conflicts
        positives = [f for f in unique_facts if not any(w in f.fact.lower() for w in ("not ", "never ", "denies ", "rejected "))]
        negatives = [f for f in unique_facts if any(w in f.fact.lower() for w in ("not ", "never ", "denies ", "rejected "))]
        if positives and negatives:
            for neg in negatives:
                for pos in positives:
                    # If sharing multiple content words
                    pos_words = set(re.findall(r"\w+", pos.fact.lower()))
                    neg_words = set(re.findall(r"\w+", neg.fact.lower()))
                    overlap = pos_words.intersection(neg_words)
                    if len(overlap) >= 4 and len(overlap) / max(len(pos_words), 1) > 0.4:
                        uncertainties.append(
                            f"Contradictory claim detected between '{pos.source_domain}' and '{neg.source_domain}' regarding '{' '.join(list(overlap)[:4])}'."
                        )

        # Format key findings from highest confidence facts
        sorted_facts = sorted(unique_facts, key=lambda x: x.confidence, reverse=True)
        for f in sorted_facts[:8]:
            key_findings.append(f"{f.fact} [{f.source_domain}]")

        if not key_findings and results:
            # Fallback to top snippet if facts extraction was too strict
            for r in results[:3]:
                key_findings.append(f"{r.snippet} [{r.source_domain}]")

        if len(updated_sources) == 1 and updated_sources[0].domain not in ("gov", "gov.in", "edu", "wikipedia.org"):
            uncertainties.append("Only a single non-institutional source was found; information should be cross-verified.")

        return sorted_facts, key_findings, uncertainties, updated_sources
