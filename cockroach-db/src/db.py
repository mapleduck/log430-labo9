"""
Database connection management – CockroachDB edition
SPDX-License-Identifier: LGPL-3.0-or-later
Auteurs: Gabriel C. Ullmann, Fabio Petrillo, 2025
"""

import re
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.dialects.postgresql.psycopg2 import PGDialect_psycopg2
from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

Base = declarative_base()

_engine = None
_SessionFactory = None


class CockroachDBDialect(PGDialect_psycopg2):
    """PostgreSQL dialect patched to accept CockroachDB's version string."""

    def _get_server_version_info(self, connection):
        try:
            return super()._get_server_version_info(connection)
        except AssertionError:
            # CockroachDB returns e.g. "CockroachDB CCL v26.1.1 ..."
            v = connection.exec_driver_sql("SELECT version()").scalar()
            m = re.search(r"v(\d+)\.(\d+)\.(\d+)", v)
            if m:
                return tuple(int(x) for x in m.groups())
            return (14, 0, 0)  # safe PostgreSQL-compatible fallback


def get_engine():
    global _engine
    if _engine is None:
        if DB_PASSWORD:
            connection_string = (
                f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}"
                f"@{DB_HOST}:{DB_PORT}/{DB_NAME}?sslmode=disable"
            )
        else:
            connection_string = (
                f"postgresql+psycopg2://{DB_USER}"
                f"@{DB_HOST}:{DB_PORT}/{DB_NAME}?sslmode=disable"
            )
        _engine = create_engine(
            connection_string,
            echo=False,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
        )
        # Patch the dialect instance on the already-created engine
        _engine.dialect.__class__ = CockroachDBDialect
    return _engine


def get_sqlalchemy_session():
    global _SessionFactory
    engine = get_engine()
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(bind=engine)
    return _SessionFactory(), engine
