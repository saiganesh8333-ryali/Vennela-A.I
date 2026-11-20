"""
🔥 MINIMAL TEST MODE — Disable memory/history for quick testing

Use this to verify the system prompt fix works WITHOUT old history pollution.

USAGE:
1. Uncomment the TEST_MODE line in main.py
2. Run the server
3. Test: "what is programming"
4. Expected: Direct answer (NO greetings, NO history)
"""

# =========================
# MINIMAL TEST MODE HELPER
# =========================

def get_minimal_messages_for_testing(system_prompt: str, user_message: str) -> list:
    """
    Create minimal message structure for testing (NO HISTORY).
    
    Args:
        system_prompt: System prompt content
        user_message: User message
        
    Returns:
        List with ONLY system + current user message
    """
    messages = [
        {
            "role": "system",
            "content": system_prompt
        },
        {
            "role": "user",
            "content": user_message
        }
    ]
    
    return messages


# =========================
# TO USE IN main.py:
# =========================

"""
In the chat() endpoint, replace:

    messages = load_messages(user_id, memory, relevant_memory)

WITH:

    # TEST MODE: Minimal messages (no history pollution)
    from cleanup_bad_history import get_minimal_messages_for_testing
    
    system_prompt = format_smart_memory(memory, relevant_memory)
    messages = get_minimal_messages_for_testing(system_prompt, user_message)

Then test it. If AI responds naturally without greetings, your system prompt is CORRECT.

If still getting greetings with minimal setup, the problem is:
- Groq model behavior (try different model)
- Frontend auto-sending messages
- Or system prompt needs adjustment
"""

print(__doc__)
