"""Smoke tests for the no-model lightweight NLP path."""
from embedding_engine import get_cache_stats, get_embedding
from nlp_engine import detect_emotion, detect_intent, detect_sentiment, get_rule_based_reply


def test_intent_detection():
    assert detect_intent("hello vennela") == "greeting"
    assert detect_intent("who are you?") == "identity"
    assert detect_intent("thanks ra") == "thanks"
    assert detect_intent("backend status") == "status"


def test_rule_based_reply():
    memory = {"profile": {"name": "Sai"}, "summary": "User name: Sai"}
    reply = get_rule_based_reply("greeting", "hi", memory)
    assert reply is not None
    assert "Sai" in reply


def test_fallback_nlp():
    assert detect_emotion("I am very happy") == "joy"
    assert detect_sentiment("I am stuck with an error") == "NEGATIVE"


def test_fallback_embedding():
    vector = get_embedding("Vennela AI lightweight memory")
    assert len(vector) == 128
    assert get_cache_stats()["cached_embeddings"] >= 1
