"""Run the read-only long_term schema validator against the configured datastore.

This script prefers Supabase (when SUPABASE_URL and SUPABASE_KEY are present) and
keeps Firebase disabled by default to avoid accidental use. It is read-only and will
never modify datastore contents.
"""
import json
import logging
import os

logging.basicConfig(level=logging.ERROR)

from dotenv import load_dotenv

load_dotenv()
os.environ.setdefault("FIREBASE_ENABLED", "false")

from memory.schema_validator import validate_long_term_schema

if __name__ == "__main__":
    res = validate_long_term_schema(sample_limit=100)

    fields = [
        "available",
        "scanned_docs",
        "total_entries",
        "canonical_count",
        "canonical_pct",
        "legacy_count",
        "legacy_pct",
        "malformed_count",
        "malformed_pct",
        "missing_field_counts",
        "error",
        "error_type",
        "error_message",
        "message",
    ]

    output = {k: res.get(k) for k in fields if k in res}
    print(json.dumps(output, indent=2))
