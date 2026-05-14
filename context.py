
import os
from memory import get_memory

VENNELA_PROMPT = os.getenv("VENNELA_PROMPT")

def format_user_memory(user_memory):
    return f"""
Name: {user_memory.get('name', '')}
Preferred Name: {user_memory.get('preferred_name', '')}
Goal: {user_memory.get('education', {}).get('goal', '')}

Interests: {', '.join(user_memory.get('interests', []))}
Projects: {', '.join(user_memory.get('projects', []))}
"""

def build_context(user_id, msg):
    user_memory = get_memory(user_id)

    user_block = format_user_memory(user_memory)

    return f"""
SYSTEM:
{VENNELA_PROMPT}

USER INFO:
{user_block}

MESSAGE:
{msg}
"""