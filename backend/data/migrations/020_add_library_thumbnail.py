"""DEPRECATED: library_items lives in workspace .knowledge_index.db, not app.db.

The actual migration adding thumbnail_path lives at
backend/services/knowledge_migrations.py migration 11 (run via
run_knowledge_index_migrations). This file is preserved as a no-op so
yoyo's _yoyo_migration history remains consistent and existing installs
do not attempt to re-apply.
"""

from yoyo import step


def apply(conn):
    pass


def rollback(conn):
    pass


steps = [step(apply, rollback)]
