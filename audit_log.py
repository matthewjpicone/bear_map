"""Audit log system for tracking changes to castles, maps, and settings.

This module provides functionality for recording and retrieving audit logs
of all changes made to entities in the Bear Map system.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from contextlib import contextmanager

# Database path
DB_PATH = Path(__file__).parent / "audit_logs.db"


class AuditLogger:
    """Handles audit logging operations for the Bear Map system.
    
    Attributes:
        db_path: Path to the SQLite database file.
    """

    def __init__(self, db_path: str | Path = DB_PATH):
        """Initialize the audit logger.
        
        Args:
            db_path: Path to the SQLite database file. Defaults to DB_PATH.
        """
        self.db_path = Path(db_path)
        self._init_db()

    def _init_db(self):
        """Initialize the database schema if it doesn't exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    user TEXT,
                    before_value TEXT,
                    after_value TEXT,
                    changes TEXT,
                    metadata TEXT
                )
            """)
            
            # Create indexes for common queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_entity 
                ON audit_logs(entity_type, entity_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp 
                ON audit_logs(timestamp DESC)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_action 
                ON audit_logs(action)
            """)
            
            conn.commit()

    @contextmanager
    def _get_connection(self):
        """Context manager for database connections.
        
        Yields:
            sqlite3.Connection: Database connection.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def log_change(
        self,
        entity_type: str,
        entity_id: str,
        action: str,
        before_value: Optional[dict] = None,
        after_value: Optional[dict] = None,
        user: Optional[str] = None,
        changes: Optional[dict] = None,
        metadata: Optional[dict] = None
    ) -> int:
        """Log a change to an entity.
        
        Args:
            entity_type: Type of entity (e.g., "castle", "bear_trap", "banner", "settings").
            entity_id: Unique identifier for the entity.
            action: Action performed (e.g., "create", "update", "delete", "move").
            before_value: Entity state before the change.
            after_value: Entity state after the change.
            user: User who made the change (from auth system).
            changes: Dictionary of specific field changes.
            metadata: Additional metadata about the change.
            
        Returns:
            The ID of the created audit log entry.
        """
        timestamp = datetime.utcnow().isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO audit_logs 
                (timestamp, entity_type, entity_id, action, user, 
                 before_value, after_value, changes, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                timestamp,
                entity_type,
                entity_id,
                action,
                user or "anonymous",
                json.dumps(before_value) if before_value else None,
                json.dumps(after_value) if after_value else None,
                json.dumps(changes) if changes else None,
                json.dumps(metadata) if metadata else None
            ))
            conn.commit()
            return cursor.lastrowid

    def get_entity_logs(
        self,
        entity_type: str,
        entity_id: str,
        limit: Optional[int] = None
    ) -> list[dict]:
        """Get audit logs for a specific entity.
        
        Args:
            entity_type: Type of entity to filter by.
            entity_id: ID of entity to filter by.
            limit: Maximum number of logs to return.
            
        Returns:
            List of audit log entries as dictionaries.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = """
                SELECT * FROM audit_logs 
                WHERE entity_type = ? AND entity_id = ?
                ORDER BY timestamp DESC
            """
            params = [entity_type, entity_id]
            
            if limit:
                query += " LIMIT ?"
                params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            return [self._row_to_dict(row) for row in rows]

    def get_global_logs(
        self,
        limit: Optional[int] = None,
        entity_type: Optional[str] = None,
        action: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> list[dict]:
        """Get global audit logs with optional filters.
        
        Args:
            limit: Maximum number of logs to return.
            entity_type: Filter by entity type.
            action: Filter by action type.
            start_date: Filter by start date (ISO format).
            end_date: Filter by end date (ISO format).
            
        Returns:
            List of audit log entries as dictionaries.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = "SELECT * FROM audit_logs WHERE 1=1"
            params = []
            
            if entity_type:
                query += " AND entity_type = ?"
                params.append(entity_type)
            
            if action:
                query += " AND action = ?"
                params.append(action)
            
            if start_date:
                query += " AND timestamp >= ?"
                params.append(start_date)
            
            if end_date:
                query += " AND timestamp <= ?"
                params.append(end_date)
            
            query += " ORDER BY timestamp DESC"
            
            if limit:
                query += " LIMIT ?"
                params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            return [self._row_to_dict(row) for row in rows]

    def get_stats(self) -> dict:
        """Get statistics about audit logs.
        
        Returns:
            Dictionary containing log statistics.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) as total FROM audit_logs")
            total = cursor.fetchone()["total"]
            
            cursor.execute("""
                SELECT entity_type, COUNT(*) as count 
                FROM audit_logs 
                GROUP BY entity_type
            """)
            by_entity = {row["entity_type"]: row["count"] for row in cursor.fetchall()}
            
            cursor.execute("""
                SELECT action, COUNT(*) as count 
                FROM audit_logs 
                GROUP BY action
            """)
            by_action = {row["action"]: row["count"] for row in cursor.fetchall()}
            
            return {
                "total_logs": total,
                "by_entity_type": by_entity,
                "by_action": by_action
            }

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        """Convert a database row to a dictionary.
        
        Args:
            row: SQLite row object.
            
        Returns:
            Dictionary representation of the row.
        """
        result = dict(row)
        
        # Parse JSON fields
        for field in ["before_value", "after_value", "changes", "metadata"]:
            if result.get(field):
                try:
                    result[field] = json.loads(result[field])
                except json.JSONDecodeError:
                    pass
        
        return result


# Global instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get the global audit logger instance.
    
    Returns:
        The global AuditLogger instance.
    """
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


def log_castle_update(
    castle_id: str,
    before: dict,
    after: dict,
    user: Optional[str] = None
) -> int:
    """Helper function to log castle updates.
    
    Args:
        castle_id: ID of the castle.
        before: Castle state before update.
        after: Castle state after update.
        user: User who made the change.
        
    Returns:
        The ID of the created audit log entry.
    """
    logger = get_audit_logger()
    
    # Calculate specific changes
    changes = {}
    for key in set(list(before.keys()) + list(after.keys())):
        if before.get(key) != after.get(key):
            changes[key] = {
                "from": before.get(key),
                "to": after.get(key)
            }
    
    return logger.log_change(
        entity_type="castle",
        entity_id=castle_id,
        action="update",
        before_value=before,
        after_value=after,
        user=user,
        changes=changes
    )


def log_entity_action(
    entity_type: str,
    entity_id: str,
    action: str,
    data: Optional[dict] = None,
    user: Optional[str] = None
) -> int:
    """Helper function to log general entity actions.
    
    Args:
        entity_type: Type of entity (e.g., "bear_trap", "banner").
        entity_id: ID of the entity.
        action: Action performed.
        data: Entity data.
        user: User who made the change.
        
    Returns:
        The ID of the created audit log entry.
    """
    logger = get_audit_logger()
    
    if action == "create":
        return logger.log_change(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            after_value=data,
            user=user
        )
    elif action == "delete":
        return logger.log_change(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            before_value=data,
            user=user
        )
    else:  # update, move, etc.
        return logger.log_change(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            after_value=data,
            user=user
        )
