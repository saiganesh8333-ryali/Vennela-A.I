"""
Verify available Gemini models using the installed google-generativeai SDK and GEMINI_API_KEY.

Usage:
  - Set environment variable GEMINI_API_KEY to a valid key for your account.
  - Run: python testing_files/verify_gemini_models.py

This script attempts several common SDK entrypoints to list models and prints those that look like Gemini model IDs.
It is safe to run locally; it does not modify code.
"""
import os
import sys
import importlib

KEY = os.getenv('GEMINI_API_KEY')
if not KEY:
    print('GEMINI_API_KEY not set in environment. Set it and re-run this script.')
    sys.exit(1)

try:
    genai = importlib.import_module('google.generativeai')
except Exception as e:
    print('Could not import google.generativeai:', e)
    print('Ensure the SDK and its native dependencies (protobuf, grpc) are installed and compatible with your Python version.')
    sys.exit(1)

try:
    genai.configure(api_key=KEY)
except Exception as e:
    print('Warning: genai.configure raised:', e)

candidates = []
# Try a few known / likely method names
tried = []

# 1) genai.list_models()
if hasattr(genai, 'list_models'):
    tried.append('genai.list_models')
    try:
        models = genai.list_models()
        candidates.append(('genai.list_models', models))
    except Exception as e:
        print('genai.list_models() failed:', e)

# 2) genai.get_models()
if hasattr(genai, 'get_models'):
    tried.append('genai.get_models')
    try:
        models = genai.get_models()
        candidates.append(('genai.get_models', models))
    except Exception as e:
        print('genai.get_models() failed:', e)

# 3) genai.models if present
if hasattr(genai, 'models'):
    tried.append('genai.models')
    try:
        mobj = genai.models
        if hasattr(mobj, 'list'):
            try:
                models = mobj.list()
                candidates.append(('genai.models.list', models))
            except Exception as e:
                print('genai.models.list() failed:', e)
        elif hasattr(mobj, 'list_models'):
            try:
                models = mobj.list_models()
                candidates.append(('genai.models.list_models', models))
            except Exception as e:
                print('genai.models.list_models() failed:', e)
    except Exception as e:
        print('Accessing genai.models failed:', e)

# 4) As a fallback, try to call a non-network method that may list built-in models (unlikely)

print('\nTried entrypoints:', tried)
print('\nResults (filtered for strings containing "gemini"):\n')
found = []
for name, res in candidates:
    try:
        # Try to iterate and find string model ids
        entries = []
        if isinstance(res, dict):
            entries = list(res.keys())
        else:
            # Try to extract ids from iterable
            try:
                for item in res:
                    # item may be a mapping or object
                    if isinstance(item, str):
                        entries.append(item)
                    elif hasattr(item, 'id'):
                        entries.append(getattr(item, 'id'))
                    elif isinstance(item, dict) and 'id' in item:
                        entries.append(item['id'])
            except Exception:
                # Fallback: stringify
                entries = [str(res)]

        gemini_like = [e for e in entries if 'gemini' in str(e).lower()]
        if gemini_like:
            print(f'{name}:')
            for g in gemini_like:
                print(' -', g)
            found.extend(gemini_like)
    except Exception as e:
        print('Error processing result from', name, e)

if not found:
    print('No gemini-like model ids found in the SDK listing results. It may be necessary to query the provider API directly or consult your account dashboard for supported models.')
else:
    print('\nVerified gemini-like model ids:', found)

print('\nIf models are returned, set GEMINI_MODEL_CHAIN to a comma-separated list of the exact model IDs to use for fallback, e.g.:')
print('  export GEMINI_MODEL_CHAIN="gemini-3.5-flash,gemini-3.5-flash-lite,gemini-3.6-flash"')
