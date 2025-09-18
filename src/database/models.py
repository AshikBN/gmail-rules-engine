"""
Database models for the Gmail Rules Engine
"""
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class Email(Base):
    """Email model for storing Gmail messages"""
    __tablename__ = 'emails'

    id = Column(Integer, primary_key=True)
    gmail_id = Column(String(255), unique=True, nullable=False)
    from_address = Column(String(255), nullable=False)
    to_address = Column(String(255))
    subject = Column(String(255))
    content = Column(Text)
    received_date = Column(DateTime, nullable=False)
    is_read = Column(Boolean, default=False)
    current_label = Column(String(255), default='INBOX')
    created_at = Column(DateTime, default=datetime.utcnow)

class Rule(Base):
    """Rule model for storing email processing rules"""
    __tablename__ = 'rules'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    identifier = Column(String(255), nullable=False, unique=True)  # Permanent ID from rules.json
    predicate = Column(String(50), nullable=False)  # 'all' or 'any'
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    conditions = relationship('RuleCondition', back_populates='rule', cascade='all, delete-orphan')
    actions = relationship('RuleAction', back_populates='rule', cascade='all, delete-orphan')

class RuleCondition(Base):
    """Condition model for storing rule conditions"""
    __tablename__ = 'rule_conditions'

    id = Column(Integer, primary_key=True)
    rule_id = Column(Integer, ForeignKey('rules.id'), nullable=False)
    field = Column(String(50), nullable=False)  # from, subject, message, received_date
    predicate = Column(String(50), nullable=False)  # contains, not_contains, equals, etc.
    value = Column(String(255), nullable=False)
    unit = Column(String(50))  # days or months for date predicates
    
    rule = relationship('Rule', back_populates='conditions')

class RuleAction(Base):
    """Action model for storing rule actions"""
    __tablename__ = 'rule_actions'

    id = Column(Integer, primary_key=True)
    rule_id = Column(Integer, ForeignKey('rules.id'), nullable=False)
    action_type = Column(String(50), nullable=False)  # mark_as_read, mark_as_unread, move_message
    action_value = Column(String(255))  # For move_message, stores destination
    
    rule = relationship('Rule', back_populates='actions')

class ProcessedEmail(Base):
    """Model for tracking which emails have been processed by which rules"""
    __tablename__ = 'processed_emails'

    id = Column(Integer, primary_key=True)
    gmail_id = Column(String(255), nullable=False)
    rule_identifier = Column(String(255), nullable=False)  # Use identifier instead of rule_id
    processed_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('gmail_id', 'rule_identifier', name='uix_email_rule'),
    )