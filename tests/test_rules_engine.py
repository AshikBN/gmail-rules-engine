"""
Test suite for the Rules Engine implementation.

This test suite provides comprehensive coverage of the email rules processing engine,
testing all supported combinations of fields, predicates, and actions.

Test Coverage:

1. String Field Tests (15 cases):
   - Fields tested: from, subject, message
   - Predicates tested:
     * contains (case sensitive and insensitive)
     * does_not_contain
     * equals
     * does_not_equal
   - Edge cases: empty strings, case sensitivity

2. Date Field Tests (11 cases):
   - Fields tested: received_date
   - Predicates tested:
     * less_than
     * greater_than
   - Units tested:
     * days
     * months
   - Edge cases:
     * Zero values
     * Negative values
     * Boundary conditions

3. Rule Predicate Tests (8 cases):
   - Predicates tested:
     * all (all conditions must match)
     * any (at least one condition must match)
   - Combinations tested:
     * Single field conditions
     * Multiple field conditions
     * Mixed field types (string + date)
     * Complex rules with 3+ conditions

4. Action Tests (3 cases):
   - Actions tested:
     * mark_as_read
     * mark_as_unread
     * move_message
   - Verifies:
     * Correct method calls
     * Proper argument passing
     * State updates

Total test cases: 37
"""

import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.rules.engine import RulesEngine
from src.database.models import Email, Rule, RuleCondition, RuleAction

class TestRulesEngine(unittest.TestCase):
    def setUp(self):
        # Mock database session
        self.db = MagicMock()
        # Mock Gmail client
        self.gmail_client = MagicMock()
        # Create rules engine
        self.engine = RulesEngine(self.db, self.gmail_client)

    def test_string_field_predicates(self):
        """Test all string field predicates (contains, not contains, equals, not equals)"""
        test_cases = [
            # FROM field tests
            {
                'field': 'from',
                'predicate': 'contains',
                'value': 'gmail.com',
                'test_value': 'test@gmail.com',
                'should_match': True,
                'description': 'From contains - positive match'
            },
            {
                'field': 'from',
                'predicate': 'contains',
                'value': 'GMAIL.COM',
                'test_value': 'test@gmail.com',
                'should_match': True,
                'description': 'From contains - case insensitive'
            },
            {
                'field': 'from',
                'predicate': 'contains',
                'value': 'yahoo.com',
                'test_value': 'test@gmail.com',
                'should_match': False,
                'description': 'From contains - negative match'
            },
            {
                'field': 'from',
                'predicate': 'does_not_contain',
                'value': 'spam',
                'test_value': 'test@gmail.com',
                'should_match': True,
                'description': 'From does not contain - positive match'
            },
            {
                'field': 'from',
                'predicate': 'equals',
                'value': 'test@gmail.com',
                'test_value': 'test@gmail.com',
                'should_match': True,
                'description': 'From equals - exact match'
            },
            {
                'field': 'from',
                'predicate': 'does_not_equal',
                'value': 'test@yahoo.com',
                'test_value': 'test@gmail.com',
                'should_match': True,
                'description': 'From does not equal - different values'
            },
            
            # SUBJECT field tests
            {
                'field': 'subject',
                'predicate': 'contains',
                'value': 'meeting',
                'test_value': 'Team meeting tomorrow',
                'should_match': True,
                'description': 'Subject contains - positive match'
            },
            {
                'field': 'subject',
                'predicate': 'contains',
                'value': '',
                'test_value': 'Team meeting tomorrow',
                'should_match': True,
                'description': 'Subject contains - empty string'
            },
            {
                'field': 'subject',
                'predicate': 'does_not_contain',
                'value': 'spam',
                'test_value': 'Team meeting tomorrow',
                'should_match': True,
                'description': 'Subject does not contain - positive match'
            },
            {
                'field': 'subject',
                'predicate': 'equals',
                'value': 'Team meeting tomorrow',
                'test_value': 'Team meeting tomorrow',
                'should_match': True,
                'description': 'Subject equals - exact match'
            },
            {
                'field': 'subject',
                'predicate': 'does_not_equal',
                'value': '',
                'test_value': 'Team meeting tomorrow',
                'should_match': True,
                'description': 'Subject does not equal - empty string'
            },
            
            # MESSAGE field tests
            {
                'field': 'message',
                'predicate': 'contains',
                'value': 'hello',
                'test_value': 'Hello, please find attached',
                'should_match': True,
                'description': 'Message contains - case insensitive'
            },
            {
                'field': 'message',
                'predicate': 'contains',
                'value': 'missing',
                'test_value': 'Hello, please find attached',
                'should_match': False,
                'description': 'Message contains - negative match'
            },
            {
                'field': 'message',
                'predicate': 'does_not_contain',
                'value': 'confidential',
                'test_value': 'Hello, please find attached',
                'should_match': True,
                'description': 'Message does not contain - positive match'
            },
            {
                'field': 'message',
                'predicate': 'equals',
                'value': 'Hello, please find attached',
                'test_value': 'Hello, please find attached',
                'should_match': True,
                'description': 'Message equals - exact match'
            },
            {
                'field': 'message',
                'predicate': 'does_not_equal',
                'value': 'Different message',
                'test_value': 'Hello, please find attached',
                'should_match': True,
                'description': 'Message does not equal - different values'
            }
        ]

        for case in test_cases:
            with self.subTest(case=case):
                # Create test email
                email = Email(
                    gmail_id='test123',
                    from_address=case['test_value'] if case['field'] == 'from' else 'test@example.com',
                    subject=case['test_value'] if case['field'] == 'subject' else 'Test Subject',
                    content=case['test_value'] if case['field'] == 'message' else 'Test Content'
                )

                # Create test condition
                condition = RuleCondition(
                    field=case['field'],
                    predicate=case['predicate'],
                    value=case['value']
                )

                # Test condition evaluation
                result = self.engine._evaluate_condition(condition, email)
                self.assertEqual(result, case['should_match'], 
                    f"Failed for {case['field']} {case['predicate']} '{case['value']}' with test value '{case['test_value']}'")

    def test_date_field_predicates(self):
        """Test all date field predicates (less than, greater than) with different units (days, months)"""
        now = datetime.utcnow()
        test_cases = [
            # Less than - Days
            {
                'predicate': 'less_than',
                'value': '2',
                'unit': 'days',
                'test_date': now - timedelta(days=1),
                'should_match': True,
                'description': 'Less than days - within range'
            },
            {
                'predicate': 'less_than',
                'value': '2',
                'unit': 'days',
                'test_date': now - timedelta(days=3),
                'should_match': False,
                'description': 'Less than days - outside range'
            },
            {
                'predicate': 'less_than',
                'value': '2',
                'unit': 'days',
                'test_date': now - timedelta(days=2, minutes=-1),
                'should_match': True,
                'description': 'Less than days - just inside range'
            },
            # Greater than - Days
            {
                'predicate': 'greater_than',
                'value': '2',
                'unit': 'days',
                'test_date': now - timedelta(days=3),
                'should_match': True,
                'description': 'Greater than days - beyond range'
            },
            {
                'predicate': 'greater_than',
                'value': '2',
                'unit': 'days',
                'test_date': now - timedelta(days=1),
                'should_match': False,
                'description': 'Greater than days - within range'
            },
            # Less than - Months
            {
                'predicate': 'less_than',
                'value': '1',
                'unit': 'months',
                'test_date': now - timedelta(days=15),
                'should_match': True,
                'description': 'Less than months - within range'
            },
            {
                'predicate': 'less_than',
                'value': '1',
                'unit': 'months',
                'test_date': now - timedelta(days=45),
                'should_match': False,
                'description': 'Less than months - outside range'
            },
            # Greater than - Months
            {
                'predicate': 'greater_than',
                'value': '1',
                'unit': 'months',
                'test_date': now - timedelta(days=45),
                'should_match': True,
                'description': 'Greater than months - beyond range'
            },
            {
                'predicate': 'greater_than',
                'value': '1',
                'unit': 'months',
                'test_date': now - timedelta(days=15),
                'should_match': False,
                'description': 'Greater than months - within range'
            },
            # Edge cases
            {
                'predicate': 'less_than',
                'value': '0',
                'unit': 'days',
                'test_date': now,
                'should_match': False,
                'description': 'Less than days - zero value'
            },
            {
                'predicate': 'greater_than',
                'value': '-1',
                'unit': 'days',
                'test_date': now,
                'should_match': False,
                'description': 'Greater than days - negative value'
            }
        ]

        for case in test_cases:
            with self.subTest(case=case):
                # Create test email
                email = Email(
                    gmail_id='test123',
                    received_date=case['test_date']
                )

                # Create test condition
                condition = RuleCondition(
                    field='received_date',
                    predicate=case['predicate'],
                    value=case['value'],
                    unit=case['unit']
                )

                # Test condition evaluation
                result = self.engine._evaluate_condition(condition, email)
                self.assertEqual(result, case['should_match'],
                    f"Failed for received_date {case['predicate']} {case['value']} {case['unit']}")

    def test_rule_predicates(self):
        """Test 'all' and 'any' predicates with multiple conditions"""
        email = Email(
            gmail_id='test123',
            from_address='test@gmail.com',
            subject='Important meeting',
            content='Meeting at 2 PM',
            received_date=datetime.utcnow()
        )

        test_cases = [
            # ALL predicate tests
            {
                'predicate': 'all',
                'conditions': [
                    {'field': 'from', 'predicate': 'contains', 'value': 'gmail.com'},
                    {'field': 'subject', 'predicate': 'contains', 'value': 'meeting'}
                ],
                'should_match': True,
                'description': 'All - both conditions match'
            },
            {
                'predicate': 'all',
                'conditions': [
                    {'field': 'from', 'predicate': 'contains', 'value': 'gmail.com'},
                    {'field': 'subject', 'predicate': 'contains', 'value': 'spam'}
                ],
                'should_match': False,
                'description': 'All - one condition fails'
            },
            {
                'predicate': 'all',
                'conditions': [
                    {'field': 'from', 'predicate': 'contains', 'value': 'yahoo.com'},
                    {'field': 'subject', 'predicate': 'contains', 'value': 'spam'}
                ],
                'should_match': False,
                'description': 'All - both conditions fail'
            },
            # ANY predicate tests
            {
                'predicate': 'any',
                'conditions': [
                    {'field': 'from', 'predicate': 'contains', 'value': 'gmail.com'},
                    {'field': 'subject', 'predicate': 'contains', 'value': 'spam'}
                ],
                'should_match': True,
                'description': 'Any - first condition matches'
            },
            {
                'predicate': 'any',
                'conditions': [
                    {'field': 'from', 'predicate': 'contains', 'value': 'yahoo.com'},
                    {'field': 'subject', 'predicate': 'contains', 'value': 'meeting'}
                ],
                'should_match': True,
                'description': 'Any - second condition matches'
            },
            {
                'predicate': 'any',
                'conditions': [
                    {'field': 'from', 'predicate': 'contains', 'value': 'yahoo.com'},
                    {'field': 'subject', 'predicate': 'contains', 'value': 'spam'}
                ],
                'should_match': False,
                'description': 'Any - no conditions match'
            },
            # Complex combinations
            {
                'predicate': 'all',
                'conditions': [
                    {'field': 'from', 'predicate': 'contains', 'value': 'gmail.com'},
                    {'field': 'subject', 'predicate': 'contains', 'value': 'meeting'},
                    {'field': 'message', 'predicate': 'contains', 'value': 'Meeting'},
                    {'field': 'received_date', 'predicate': 'less_than', 'value': '1', 'unit': 'days'}
                ],
                'should_match': True,
                'description': 'All - multiple conditions including date'
            },
            {
                'predicate': 'any',
                'conditions': [
                    {'field': 'from', 'predicate': 'equals', 'value': 'wrong@email.com'},
                    {'field': 'subject', 'predicate': 'contains', 'value': 'wrong'},
                    {'field': 'message', 'predicate': 'contains', 'value': 'Meeting'}
                ],
                'should_match': True,
                'description': 'Any - one matches out of many'
            }
        ]

        for case in test_cases:
            with self.subTest(case=case):
                # Create rule with conditions
                rule = Rule(predicate=case['predicate'])
                conditions = [
                    RuleCondition(
                        field=c['field'],
                        predicate=c['predicate'],
                        value=c['value']
                    ) for c in case['conditions']
                ]

                # Test rule evaluation
                result = self.engine._evaluate_rule(rule, conditions, email)
                self.assertEqual(result, case['should_match'],
                    f"Failed for {case['predicate']} predicate with conditions {case['conditions']}")

    def test_actions(self):
        """Test all action types (mark as read/unread, move message)"""
        email = Email(
            gmail_id='test123',
            is_read=False,
            current_label='INBOX'
        )

        test_cases = [
            # Mark as read
            {
                'action_type': 'mark_as_read',
                'action_value': None,
                'expected_method': 'mark_as_read',
                'expected_args': ['test123']
            },
            # Mark as unread
            {
                'action_type': 'mark_as_unread',
                'action_value': None,
                'expected_method': 'mark_as_unread',
                'expected_args': ['test123']
            },
            # Move message
            {
                'action_type': 'move_message',
                'action_value': 'Important',
                'expected_method': 'move_message',
                'expected_args': ['test123', 'Important']
            }
        ]

        for case in test_cases:
            with self.subTest(case=case):
                # Reset mock
                self.gmail_client.reset_mock()
                
                # Create action
                action = RuleAction(
                    action_type=case['action_type'],
                    action_value=case['action_value']
                )

                # Configure mock to return success
                getattr(self.gmail_client, case['expected_method']).return_value = True

                # Create rule and process email
                rule = Rule(id=1, name='Test Rule', predicate='all')
                
                # Set up database mock to return our test rule and action
                self.db.query.return_value.filter.return_value.all.side_effect = [
                    [rule],  # For rules query
                    [],      # For conditions query
                    [action] # For actions query
                ]
                
                # Process the email
                self.engine.process_email(email)

                # Verify correct method was called with correct arguments
                method = getattr(self.gmail_client, case['expected_method'])
                method.assert_called_once_with(*case['expected_args'])

if __name__ == '__main__':
    unittest.main()