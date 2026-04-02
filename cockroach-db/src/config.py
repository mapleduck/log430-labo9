"""
Database configuration – CockroachDB edition
SPDX-License-Identifier: LGPL-3.0-or-later
Auteurs : Gabriel C. Ullmann, Fabio Petrillo, 2025
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

DB_HOST     = os.getenv("DB_HOST", "cockroach1")
DB_PORT     = os.getenv("DB_PORT", "26257")
DB_NAME     = os.getenv("DB_NAME", "labo09")
DB_USER     = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
