"""Shared layer for backend services (app, bot, monitor).

Owns cross-service concerns:
  - shared.config:  Hydra-based configuration loader
  - shared.db:      SQLAlchemy async engine and session factory
  - shared.models:  ORM models (single declarative Base)
  - shared.queries: per-domain query helpers
"""
