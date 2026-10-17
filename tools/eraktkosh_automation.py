#!/usr/bin/env python3
"""CLI helper that invokes the backend eRaktKosh scraper service.

The scraper runs automatically in the FastAPI backend service every 10 minutes.
This CLI tool allows triggering the backend scraper service directly from the command line.

Usage:
  # Continuous 10-minute automated loop:
  python tools/eraktkosh_automation.py

  # Single-run test:
  python tools/eraktkosh_automation.py --once
"""

import sys
from pathlib import Path

# Add backend to sys.path so app modules are discoverable
backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.services.eraktkosh_scraper import main

if __name__ == "__main__":
    main()
