from __future__ import annotations

from .repository import SQLiteRepository


class SQLiteStore(SQLiteRepository):
    """Backward-compatible persistence entry point.

    The repository now owns the full schema, position lifecycle refresh,
    dashboard bundle assembly, and export helpers. Keeping this subclass lets
    older imports continue to work while the codebase converges on one
    persistence implementation.
    """

    pass
