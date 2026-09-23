"""Module execution entry point for `python -m web_intelligence`."""

import sys
from .cli import main

if __name__ == "__main__":
    sys.exit(main())
