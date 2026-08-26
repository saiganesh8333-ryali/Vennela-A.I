import pytest
from memory.schema_validator import _supabase_docs_generator, validate_long_term_schema


def _make_doc_generator(docs):
    """Yield (doc_id, doc_dict) pairs from a list of dicts."""
    for i, d in enumerate(docs):
        yield f"user_{i}", d


def test_all_canonical_entries():
    docs = [
        {"long_term": [
            {"text": "a", "timestamp": "2021-01-01T00:00:00Z", "importance": 0.5},
            {"text": "b", "timestamp": "2021-01-02T00:00:00Z", "importance": 0.9},
        ]}
    ]

    res = validate_long_term_schema(documents=_make_doc_generator(docs))
    assert res["available"] is True
    assert res["total_entries"] == 2
    assert res["canonical_count"] == 2
    assert res["legacy_count"] == 0
    assert res["malformed_count"] == 0
    assert res["canonical_pct"] == 100.0


def test_mixed_canonical_and_legacy():
    docs = [
        {"long_term": [
            "legacy one",
            {"text": "c", "timestamp": "2021-01-03T00:00:00Z", "importance": 0.1},
            "another legacy"
        ]}
    ]

    res = validate_long_term_schema(documents=_make_doc_generator(docs))
    assert res["total_entries"] == 3
    assert res["canonical_count"] == 1
    assert res["legacy_count"] == 2
    assert res["legacy_pct"] == round((2 / 3) * 100.0, 2)


def test_malformed_entries_and_missing_fields():
    docs = [
        {"long_term": [
            {"text": 123, "timestamp": None, "importance": "high"},
            42,
            {"text": "ok", "importance": 0.2},
        ]}
    ]

    res = validate_long_term_schema(documents=_make_doc_generator(docs))
    assert res["total_entries"] == 3
    assert res["canonical_count"] == 0
    assert res["malformed_count"] == 3
    mfc = res["missing_field_counts"]
    assert mfc.get("text", 0) >= 1
    assert mfc.get("timestamp", 0) >= 2
    assert mfc.get("importance", 0) >= 1


def test_empty_datastore():
    docs = []
    res = validate_long_term_schema(documents=_make_doc_generator(docs))
    assert res["available"] is True
    assert res["scanned_docs"] == 0
    assert res["total_entries"] == 0
    assert res["canonical_pct"] == 0.0
    assert res["legacy_pct"] == 0.0
    assert res["malformed_pct"] == 0.0


def test_sample_limit_applied():
    docs = [
        {"long_term": ["a"]},
        {"long_term": ["b"]},
        {"long_term": ["c"]},
    ]
    res = validate_long_term_schema(documents=_make_doc_generator(docs), sample_limit=2)
    assert res["scanned_docs"] == 2
    assert res["total_entries"] == 2


def test_live_query_uses_memories_table(monkeypatch):
    calls = {}

    class FakeResponse:
        error = None
        status_code = 200
        data = [{"id": "m1", "long_term": [{"text": "a", "timestamp": "2021-01-01T00:00:00Z", "importance": 0.1}]}]

    class FakeTable:
        def __init__(self):
            self.last_select = None

        def select(self, cols):
            self.last_select = cols
            return self

        def limit(self, n):
            self.last_limit = n
            return self

        def execute(self):
            calls["table"] = self.last_table
            calls["select"] = self.last_select
            calls["limit"] = getattr(self, "last_limit", None)
            return FakeResponse()

    class FakeClient:
        def __init__(self):
            self.table_called = None

        def table(self, name):
            self.table_called = name
            tbl = FakeTable()
            tbl.last_table = name
            return tbl

    fake_client = FakeClient()

    import types
    fake_module = types.SimpleNamespace(create_client=lambda url, key: fake_client)

    monkeypatch.setenv("SUPABASE_URL", "https://example.com")
    monkeypatch.setenv("SUPABASE_KEY", "key")
    monkeypatch.setitem(__import__("sys").modules, "supabase", fake_module)

    rows = list(_supabase_docs_generator(sample_limit=5))

    assert rows
    assert fake_client.table_called == "memories"
    assert calls["table"] == "memories"
    assert calls["select"] == "id,long_term"
    assert calls["limit"] == 5
