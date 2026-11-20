"""Configuration constants for the standalone Web Hunt Agent."""

AGENT_NAME = "Web Hunt Agent"
AGENT_ID = "web_hunt"
AGENT_VERSION = "1.0.0"
AGENT_DESCRIPTION = "Researches the public web and returns source-backed structured findings."
CAPABILITIES = (
    "web_search",
    "web_research",
    "source_collection",
    "page_reading",
    "information_extraction",
    "cross_source_analysis",
    "research_caching",
)
