"""Database setup and models for audit log system.

This module provides the database connection, models, and utilities
for the audit log system using SQLAlchemy with SQLite.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Database setup
DATABASE_URL = "sqlite:///./bear_map.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class AuditLog(Base):
    """Audit log model for tracking all changes to entities.

    Attributes:
        id: Primary key auto-incrementing ID.
        timestamp: When the change occurred.
        user: Username or identifier of the user who made the change.
        entity_type: Type of entity (castle, bear_trap, banner, settings, map).
        entity_id: ID of the specific entity that was changed.
        action: Type of action (create, update, delete, move).
        field_name: Name of the field that was changed (for update actions).
        before_value: Previous value of the field (JSON string).
        after_value: New value of the field (JSON string).
        description: Human-readable description of the change.
    """

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    user = Column(String(100), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False, index=True)
    entity_id = Column(String(100), nullable=True, index=True)
    action = Column(String(50), nullable=False)
    field_name = Column(String(100), nullable=True)
    before_value = Column(Text, nullable=True)
    after_value = Column(Text, nullable=True)
    description = Column(Text, nullable=True)

    def to_dict(self):
        """Convert audit log entry to dictionary.

        Returns:
            Dictionary representation of the audit log entry.
        """
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "user": self.user,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "action": self.action,
            "field_name": self.field_name,
            "before_value": self.before_value,
            "after_value": self.after_value,
            "description": self.description,
        }


def get_db():
    """Dependency for getting database session.

    Yields:
        Database session that will be closed after use.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize the database by creating all tables."""
    Base.metadata.create_all(bind=engine)
