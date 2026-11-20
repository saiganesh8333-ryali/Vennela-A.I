"""Standalone CLI interface for Vennela Web Intelligence."""

from __future__ import annotations

import argparse
import json
import sys

from .config import WebIntelligenceSettings
from .engine import ResearchEngine
from .providers.mock import MockSearchProvider
from .reader.mock_reader import MockPageReader


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="web_intelligence",
        description="Vennela Internet Intelligence / Web Hunt Layer CLI",
    )
    parser.add_argument("query", type=str, help="Research or informational query to hunt")
    parser.add_argument("--mock", action="store_true", help="Use offline mock provider for testing")
    parser.add_argument("--deep", action="store_true", help="Perform deep webpage retrieval and parsing")
    parser.add_argument("--json", action="store_true", help="Output raw structured JSON")
    parser.add_argument("--max-results", type=int, default=5, help="Maximum search results per query")
    return parser


def format_cli_output(result) -> str:
    lines = []
    lines.append("=" * 65)
    lines.append("   VENNELA INTERNET INTELLIGENCE / WEB HUNT LAYER v0.1")
    lines.append("=" * 65)
    lines.append(f"Query: {result.original_query}")
    lines.append(f"Search Required: {'YES' if result.needs_search else 'NO'}")
    lines.append(f"Timestamp: {result.timestamp}")

    if not result.needs_search:
        lines.append("\n[Static / Conversational Query]")
        lines.append(f"Reason: {result.metadata.get('reasoning', 'No web search necessary')}")
        lines.append("=" * 65)
        return "\n".join(lines)

    lines.append("\n[Generated Search Queries]:")
    for idx, sq in enumerate(result.search_queries, 1):
        lines.append(f"  {idx}. {sq}")

    lines.append("\n[Key Findings]:")
    if result.key_findings:
        for idx, finding in enumerate(result.key_findings, 1):
            lines.append(f"  * {finding}")
    else:
        lines.append("  (No key findings synthesized)")

    lines.append("\n[Sources & Provenance]:")
    if result.sources:
        for idx, src in enumerate(result.sources, 1):
            lines.append(f"  [{idx}] {src.title}")
            lines.append(f"      URL: {src.url}")
            lines.append(f"      Domain: {src.domain}")
            if src.claims_supported:
                lines.append(f"      Verified claims: {len(src.claims_supported)}")
    else:
        lines.append("  (No sources verified)")

    if result.uncertainties:
        lines.append("\n[Uncertainties / Conflicting Claims]:")
        for idx, unc in enumerate(result.uncertainties, 1):
            lines.append(f"  ! {unc}")

    if result.errors_and_warnings:
        lines.append("\n[Diagnostics & Warnings]:")
        for idx, err in enumerate(result.errors_and_warnings, 1):
            lines.append(f"  ? {err}")

    lines.append("\n[Execution Metadata]:")
    lines.append(f"  Provider: {result.metadata.get('provider', 'unknown')}")
    lines.append(f"  Reader: {result.metadata.get('reader', 'unknown')}")
    lines.append(f"  Execution Time: {result.metadata.get('elapsed_ms', 0)} ms")
    lines.append(f"  Pages Retrieved: {result.metadata.get('pages_retrieved_count', 0)}")
    lines.append(f"  Cache Hits: {result.metadata.get('cache_hits', 0)}")
    lines.append("=" * 65)

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    settings = WebIntelligenceSettings.from_env()

    if args.mock:
        engine = ResearchEngine(
            settings=settings,
            search_provider=MockSearchProvider(),
            page_reader=MockPageReader(),
        )
    else:
        engine = ResearchEngine(settings=settings)

    result = engine.hunt(
        query=args.query,
        deep_retrieval=args.deep,
        max_results=args.max_results,
    )

    if args.json:
        print(result.to_json())
    else:
        print(format_cli_output(result))

    return 0


if __name__ == "__main__":
    sys.exit(main())
