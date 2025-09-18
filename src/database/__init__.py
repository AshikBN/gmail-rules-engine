"""
Database package for Gmail Rules Engine
"""
from .connection import get_db_session, init_db
from .models import Base, Email, ProcessedEmail, Rule, RuleAction, RuleCondition

__all__ = [
    'Base',
    'Email',
    'Rule',
    'RuleCondition',
    'RuleAction',
    'ProcessedEmail',
    'init_db',
    'get_db_session',
]