"""
JSON schema for email processing rules
"""
from typing import Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field

class RuleCondition(BaseModel):
    """Schema for a rule condition"""
    field: Literal['from', 'subject', 'message', 'received_date']
    predicate: Union[
        Literal['contains', 'does_not_contain', 'equals', 'does_not_equal'],  # For string fields
        Literal['less_than', 'greater_than']  # For date fields
    ]
    value: str
    unit: Optional[Literal['days', 'months']] = None  # Only for date predicates

class RuleAction(BaseModel):
    """Schema for a rule action"""
    type: Literal['mark_as_read', 'mark_as_unread', 'move_message']
    destination: Optional[str] = None  # Only for move_message action

class Rule(BaseModel):
    """Schema for a single rule"""
    identifier: str  # Permanent identifier for the rule
    name: str
    predicate: Literal['all', 'any']
    conditions: List[RuleCondition]
    actions: List[RuleAction]
    active: bool = True

class RulesConfig(BaseModel):
    """Schema for the entire rules configuration"""
    rules: List[Rule]


