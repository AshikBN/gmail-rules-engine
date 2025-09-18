"""
Database connection management for the Gmail Rules Engine
"""
import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base

# Get database URL from environment variable
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///gmail_rules.db')

# Create engine
engine = create_engine(DATABASE_URL)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db() -> None:
    """Initialize the database, creating all tables"""
    Base.metadata.create_all(bind=engine)

def get_db_session() -> Session:
    """Get a new database session"""
    db = SessionLocal()
    try:
        return db
    except Exception:
        db.close()
        raise