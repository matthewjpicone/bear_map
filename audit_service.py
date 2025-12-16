"""Audit logging service for tracking changes to entities.

This module provides utilities for logging all changes to castles,
bear traps, banners, and settings with before/after values.
"""

import json
from datetime import datetime
from typing import Any, Optional, Dict, List
from sqlalchemy.orm import Session
from database import AuditLog, SessionLocal


class AuditLogger:
    """Service for logging audit events."""

    @staticmethod
    def log_create(
        user: str,
        entity_type: str,
        entity_id: str,
        after_value: Dict[str, Any],
        description: Optional[str] = None,
    ) -> None:
        """Log entity creation.

        Args:
            user: Username or identifier of the user who created the entity.
            entity_type: Type of entity (castle, bear_trap, banner, settings).
            entity_id: ID of the created entity.
            after_value: The new entity data.
            description: Optional human-readable description.
        """
        db = SessionLocal()
        try:
            log_entry = AuditLog(
                user=user,
                entity_type=entity_type,
                entity_id=entity_id,
                action="create",
                before_value=None,
                after_value=json.dumps(after_value),
                description=description
                or f"Created {entity_type} {entity_id}",
            )
            db.add(log_entry)
            db.commit()
        finally:
            db.close()

    @staticmethod
    def log_update(
        user: str,
        entity_type: str,
        entity_id: str,
        field_name: str,
        before_value: Any,
        after_value: Any,
        description: Optional[str] = None,
    ) -> None:
        """Log entity update.

        Args:
            user: Username or identifier of the user who made the update.
            entity_type: Type of entity (castle, bear_trap, banner, settings).
            entity_id: ID of the updated entity.
            field_name: Name of the field that was updated.
            before_value: Previous value of the field.
            after_value: New value of the field.
            description: Optional human-readable description.
        """
        db = SessionLocal()
        try:
            log_entry = AuditLog(
                user=user,
                entity_type=entity_type,
                entity_id=entity_id,
                action="update",
                field_name=field_name,
                before_value=json.dumps(before_value)
                if not isinstance(before_value, str)
                else before_value,
                after_value=json.dumps(after_value)
                if not isinstance(after_value, str)
                else after_value,
                description=description
                or f"Updated {entity_type} {entity_id} field {field_name}",
            )
            db.add(log_entry)
            db.commit()
        finally:
            db.close()

    @staticmethod
    def log_delete(
        user: str,
        entity_type: str,
        entity_id: str,
        before_value: Dict[str, Any],
        description: Optional[str] = None,
    ) -> None:
        """Log entity deletion.

        Args:
            user: Username or identifier of the user who deleted the entity.
            entity_type: Type of entity (castle, bear_trap, banner, settings).
            entity_id: ID of the deleted entity.
            before_value: The entity data before deletion.
            description: Optional human-readable description.
        """
        db = SessionLocal()
        try:
            log_entry = AuditLog(
                user=user,
                entity_type=entity_type,
                entity_id=entity_id,
                action="delete",
                before_value=json.dumps(before_value),
                after_value=None,
                description=description
                or f"Deleted {entity_type} {entity_id}",
            )
            db.add(log_entry)
            db.commit()
        finally:
            db.close()

    @staticmethod
    def log_move(
        user: str,
        entity_type: str,
        entity_id: str,
        old_position: Dict[str, int],
        new_position: Dict[str, int],
        description: Optional[str] = None,
    ) -> None:
        """Log entity movement.

        Args:
            user: Username or identifier of the user who moved the entity.
            entity_type: Type of entity (castle, bear_trap, banner).
            entity_id: ID of the moved entity.
            old_position: Previous position {x, y}.
            new_position: New position {x, y}.
            description: Optional human-readable description.
        """
        db = SessionLocal()
        try:
            log_entry = AuditLog(
                user=user,
                entity_type=entity_type,
                entity_id=entity_id,
                action="move",
                field_name="position",
                before_value=json.dumps(old_position),
                after_value=json.dumps(new_position),
                description=description
                or f"Moved {entity_type} {entity_id} from "
                f"({old_position.get('x')}, {old_position.get('y')}) to "
                f"({new_position.get('x')}, {new_position.get('y')})",
            )
            db.add(log_entry)
            db.commit()
        finally:
            db.close()

    @staticmethod
    def get_logs(
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        user: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Retrieve audit logs with optional filtering.

        Args:
            entity_type: Filter by entity type.
            entity_id: Filter by entity ID.
            user: Filter by user.
            limit: Maximum number of logs to return.
            offset: Number of logs to skip.

        Returns:
            List of audit log entries as dictionaries.
        """
        db = SessionLocal()
        try:
            query = db.query(AuditLog)

            if entity_type:
                query = query.filter(AuditLog.entity_type == entity_type)
            if entity_id:
                query = query.filter(AuditLog.entity_id == entity_id)
            if user:
                query = query.filter(AuditLog.user == user)

            query = query.order_by(AuditLog.timestamp.desc())
            query = query.offset(offset).limit(limit)

            logs = query.all()
            return [log.to_dict() for log in logs]
        finally:
            db.close()

    @staticmethod
    def get_entity_history(
        entity_type: str, entity_id: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get complete history for a specific entity.

        Args:
            entity_type: Type of entity.
            entity_id: ID of the entity.
            limit: Maximum number of logs to return.

        Returns:
            List of audit log entries for the entity.
        """
        return AuditLogger.get_logs(
            entity_type=entity_type, entity_id=entity_id, limit=limit
        )

    @staticmethod
    def export_logs_csv(
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        user: Optional[str] = None,
    ) -> str:
        """Export audit logs as CSV format.

        Args:
            entity_type: Filter by entity type.
            entity_id: Filter by entity ID.
            user: Filter by user.

        Returns:
            CSV formatted string of audit logs.
        """
        import csv
        import io

        logs = AuditLogger.get_logs(
            entity_type=entity_type, entity_id=entity_id, user=user, limit=10000
        )

        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "id",
                "timestamp",
                "user",
                "entity_type",
                "entity_id",
                "action",
                "field_name",
                "before_value",
                "after_value",
                "description",
            ],
        )

        writer.writeheader()
        for log in logs:
            writer.writerow(log)

        return output.getvalue()
