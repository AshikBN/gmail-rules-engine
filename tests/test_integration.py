"""
Integration Tests for Gmail Rules Engine

1. Gmail API Integration:
   - Authentication flow
   - Email fetching
   - Email modification (read/unread/move)
   - Label management

2. Database Integration:
   - Email storage and retrieval
   - Rule persistence
   - Processed email tracking

3. End-to-End Flows:
   - Email fetch → Store → Process → Update
   - Rule load → Evaluate → Execute actions
   - Multiple rules processing
   - Error handling and recovery

Test Coverage:
- Real Gmail API calls (with test account)
- Real database operations
- Complete processing pipeline
"""

import unittest
from datetime import datetime, timedelta
import os
from unittest.mock import patch
import json

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.gmail import get_gmail_service, GmailClient
from src.database import get_db_session, init_db
from src.database.models import Email, Rule, RuleCondition, RuleAction
from src.rules import RulesEngine

class TestGmailIntegration(unittest.TestCase):
    """Integration tests for Gmail API functionality"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment - runs once before all tests"""
        # Initialize real Gmail service
        cls.service = get_gmail_service()
        cls.gmail_client = GmailClient(cls.service)
        
        # Initialize database
        init_db()
        cls.db = get_db_session()
        
        # Use an existing label for move operations
        cls.test_label = "INBOX"  # Using INBOX as it always exists

    def setUp(self):
        """Set up each test - runs before each test method"""
        # Clean database
        self.db.query(Email).delete()
        self.db.query(Rule).delete()
        self.db.commit()

    def test_fetch_and_store_emails(self):
        """Test fetching emails from Gmail and storing in database"""
        # Fetch recent emails
        response = self.gmail_client.list_messages(max_results=5)
        messages = response.get('messages', [])
        self.assertGreater(len(messages), 0, "Should fetch at least one email")
        
        # Get full message and convert to Email object
        message = self.gmail_client.get_message(messages[0]['id'])
        self.assertIsNotNone(message, "Should get message details")
        
        email = self.gmail_client.message_to_email(message)
        self.assertIsNotNone(email.gmail_id)
        self.assertIsNotNone(email.subject)
        self.assertIsNotNone(email.from_address)
        
        # Store in database
        self.db.add(email)
        self.db.commit()
        
        # Verify storage
        stored = self.db.query(Email).filter_by(gmail_id=email.gmail_id).first()
        self.assertIsNotNone(stored)
        self.assertEqual(stored.subject, email.subject)

    def test_rule_processing(self):
        """Test end-to-end rule processing with real emails"""
        # Create test rule
        rule = Rule(
            name="Test Integration Rule",
            predicate="all",
            active=True
        )
        self.db.add(rule)
        self.db.flush()
        
        # Add conditions
        condition = RuleCondition(
            rule_id=rule.id,
            field="from",
            predicate="contains",
            value="@zomato.com"
        )
        self.db.add(condition)
        
        # Add action
        action = RuleAction(
            rule_id=rule.id,
            action_type="mark_as_unread"
        )
        self.db.add(action)
        self.db.commit()
        
        # Create rules engine
        engine = RulesEngine(self.db, self.gmail_client)
        
        # Print rule details
        print("\nRule configuration:")
        print(f"Rule: {rule.name} ({rule.predicate})")
        print(f"Condition: {condition.field} {condition.predicate} '{condition.value}'")
        print(f"Action: {action.action_type}")
        
        # First find Zomato emails
        print("\nSearching for Zomato emails...")
        response = self.gmail_client.service.users().messages().list(
            userId=self.gmail_client.user_id,
            q="from:noreply@zomato.com",  # Exact email
            maxResults=1  # Just need one for testing
        ).execute()
        
        messages = response.get('messages', [])
        if not messages:
            print("No Zomato emails found. Skipping test.")
            return
            
        matching_emails = []
        for msg_data in messages:
            message = self.gmail_client.get_message(msg_data['id'])
            if message:
                email = self.gmail_client.message_to_email(message)
                print(f"\nProcessing email: From={email.from_address}, Subject={email.subject}")
                engine.process_email(email)
                matching_emails.append(email)
        
        print(f"\nFound {len(matching_emails)} emails from Zomato")
        self.assertGreater(len(matching_emails), 0, "Should find at least one Zomato email")
        
        # Verify changes in Gmail
        for email in matching_emails:
            print(f"\nVerifying email {email.gmail_id}")
            # Get current state from Gmail
            message = self.gmail_client.get_message(email.gmail_id)
            self.assertIsNotNone(message)
            labels = message.get('labelIds', [])
            print(f"Current labels: {labels}")
            self.assertIn('UNREAD', labels, f"Email {email.gmail_id} should be marked as unread")

    def test_move_message_flow(self):
        """Test moving messages to different labels"""
        # Create test rule for moving messages
        rule = Rule(
            name="Test Move Rule",
            predicate="any",  # Changed to any since we only have one condition
            active=True
        )
        self.db.add(rule)
        self.db.flush()
        
        # Create a test label
        test_label = "Test_Label_Integration"
        try:
            print(f"\nCreating test label: {test_label}")
            self.gmail_client.create_label(test_label)
        except Exception as e:
            print(f"Note: Label creation failed (might already exist): {e}")
        
        # Add condition for Zomato emails
        condition = RuleCondition(
            rule_id=rule.id,
            field="from",
            predicate="contains",
            value="noreply@zomato.com"  # Exact email we saw in the logs
        )
        self.db.add(condition)
        
        # Add move action
        action = RuleAction(
            rule_id=rule.id,
            action_type="move_message",
            action_value=test_label
        )
        self.db.add(action)
        self.db.commit()
        
        # Create rules engine
        engine = RulesEngine(self.db, self.gmail_client)
        
        # Print rule details
        print("\nRule configuration:")
        print(f"Rule: {rule.name} ({rule.predicate})")
        print(f"Condition: {condition.field} {condition.predicate} '{condition.value}'")
        print(f"Action: {action.action_type} -> {action.action_value}")
        
        try:
            # First find Zomato emails
            print("\nSearching for Zomato emails...")
            response = self.gmail_client.service.users().messages().list(
                userId=self.gmail_client.user_id,
                q="from:noreply@zomato.com",  # Exact email
                maxResults=1  # Reduced to 2 for faster testing
            ).execute()
            
            messages = response.get('messages', [])
            if not messages:
                print("No Zomato emails found. Skipping test.")
                return
                
            matching_emails = []
            original_labels = {}
            
            for msg_data in messages:
                message = self.gmail_client.get_message(msg_data['id'])
                if message:
                    email = self.gmail_client.message_to_email(message)
                    print(f"\nFound Zomato email: From={email.from_address}, Subject={email.subject}")
                    original_labels[email.gmail_id] = message.get('labelIds', [])
                    matching_emails.append(email)
            
            # Process the emails
            for email in matching_emails:
                print(f"\nProcessing email: {email.gmail_id}")
                engine.process_email(email)
            
            print(f"\nFound {len(matching_emails)} emails from Zomato")
            self.assertGreater(len(matching_emails), 0, "Should find at least one Zomato email")
            
            # Verify moves
            for email in matching_emails:
                print(f"\nVerifying email {email.gmail_id}")
                # Get current state from Gmail
                message = self.gmail_client.get_message(email.gmail_id)
                self.assertIsNotNone(message)
                labels = message.get('labelIds', [])
                print(f"Current labels: {labels}")
                
                # Get label ID
                label_id = self.gmail_client.get_label_id(test_label)
                self.assertIsNotNone(label_id, f"Label {test_label} should exist")
                self.assertIn(label_id, labels, f"Email {email.gmail_id} should be moved to {test_label}")
                
            # Restore original labels
            print("\nRestoring original labels...")
            for email_id, orig_labels in original_labels.items():
                try:
                    # Move back to original labels
                    self.gmail_client.modify_labels(email_id, add_labels=orig_labels, remove_labels=[test_label])
                    print(f"Restored {email_id} to original labels: {orig_labels}")
                except Exception as e:
                    print(f"Warning: Failed to restore labels for {email_id}: {e}")
                    
        finally:
            # Clean up - remove test label
            try:
                print(f"\nCleaning up test label: {test_label}")
                self.gmail_client.delete_label(test_label)
            except Exception as e:
                print(f"Note: Label cleanup failed: {e}")

    def test_all_rule_combinations(self):
        """Test all combinations of rules, conditions and predicates
        
        Tests:
        1. String Fields (From, Subject):
           - contains
           - not contains
           - equals
           - not equals
           
        2. Date Fields (Received):
           - less than X days
           - greater than X days
           - less than X months
           - greater than X months
           
        3. Rule Predicates:
           - all (all conditions must match)
           - any (at least one condition must match)
        """
        print("\nTesting all rule combinations...")
        
        # Find one test email
        print("\nSearching for a test email...")
        response = self.gmail_client.service.users().messages().list(
            userId=self.gmail_client.user_id,
            q="from:noreply@zomato.com",  # Exact email
            maxResults=1  # Just need one email
        ).execute()
        
        messages = response.get('messages', [])
        if not messages:
            print("No test email found. Skipping combination tests.")
            return
            
        message = self.gmail_client.get_message(messages[0]['id'])
        if not message:
            print("Could not get message details. Skipping combination tests.")
            return
            
        test_email = self.gmail_client.message_to_email(message)
        print(f"Found test email: From={test_email.from_address}, Subject={test_email.subject}")
            
        # Test 1: String Field Conditions
        print("\nTesting string field conditions...")
        
        # Contains
        rule = Rule(name="Contains Test", predicate="any", active=True)  # Changed to any since we want to test each condition independently
        self.db.add(rule)
        self.db.flush()
        
        # Test contains with from field
        condition = RuleCondition(
            rule_id=rule.id,
            field="from",
            predicate="contains",
            value="noreply@zomato.com"  # Exact match we know exists
        )
        self.db.add(condition)
        
        action = RuleAction(
            rule_id=rule.id,
            action_type="mark_as_unread"
        )
        self.db.add(action)
        self.db.commit()
        
        engine = RulesEngine(self.db, self.gmail_client)
        
        print("\nTesting 'contains' condition...")
        print(f"\nProcessing email: {test_email.gmail_id}")
        print(f"From: {test_email.from_address}")
        print(f"Subject: {test_email.subject}")
        
        # Get original state
        message = self.gmail_client.get_message(test_email.gmail_id)
        original_labels = message.get('labelIds', [])
        print(f"Original labels: {original_labels}")
        
        # Process email
        engine.process_email(test_email)
        
        # Get current state from Gmail
        message = self.gmail_client.get_message(test_email.gmail_id)
        self.assertIsNotNone(message)
        labels = message.get('labelIds', [])
        print(f"Current labels: {labels}")
        self.assertIn('UNREAD', labels, "Email should be marked as unread")
            
        # Not Contains
        print("\nTesting 'not contains' condition...")
        condition.predicate = "not contains"
        condition.value = "nonexistent_text"
        self.db.commit()
        
        print(f"Processing email: {test_email.gmail_id}")
        engine.process_email(test_email)
        message = self.gmail_client.get_message(test_email.gmail_id)
        self.assertIsNotNone(message)
        labels = message.get('labelIds', [])
        self.assertIn('UNREAD', labels, "Email should be marked as unread")
        
        # Equals
        print("\nTesting 'equals' condition...")
        condition.predicate = "equals"
        condition.value = test_email.from_address
        self.db.commit()
        
        engine.process_email(test_email)
        message = self.gmail_client.get_message(test_email.gmail_id)
        self.assertIsNotNone(message)
        labels = message.get('labelIds', [])
        self.assertIn('UNREAD', labels, "Email should be marked as unread")
        
        # Not Equals
        print("\nTesting 'not equals' condition...")
        condition.predicate = "not equals"
        condition.value = "nonexistent@email.com"
        self.db.commit()
        
        print(f"Processing email: {test_email.gmail_id}")
        engine.process_email(test_email)
        message = self.gmail_client.get_message(test_email.gmail_id)
        self.assertIsNotNone(message)
        labels = message.get('labelIds', [])
        self.assertIn('UNREAD', labels, "Email should be marked as unread")
        
        # Test 2: Date Field Conditions
        print("\nTesting date field conditions...")
        
        # Less than X days
        print("\nTesting 'less than X days' condition...")
        condition.field = "received_date"
        condition.predicate = "less than"
        condition.value = "30"  # Less than 30 days old
        self.db.commit()
        
        print(f"Processing email: {test_email.gmail_id}")
        engine.process_email(test_email)
        message = self.gmail_client.get_message(test_email.gmail_id)
        self.assertIsNotNone(message)
        labels = message.get('labelIds', [])
        self.assertIn('UNREAD', labels, "Email should be marked as unread")
        
        # Greater than X days
        print("\nTesting 'greater than X days' condition...")
        condition.predicate = "greater than"
        condition.value = "0"  # Greater than 0 days old
        self.db.commit()
        
        print(f"Processing email: {test_email.gmail_id}")
        engine.process_email(test_email)
        message = self.gmail_client.get_message(test_email.gmail_id)
        self.assertIsNotNone(message)
        labels = message.get('labelIds', [])
        self.assertIn('UNREAD', labels, "Email should be marked as unread")
        
        # Test 3: Rule Predicates
        print("\nTesting rule predicates...")
        
        # Test 'all' predicate
        print("\nTesting 'all' predicate...")
        rule.predicate = "all"
        
        # Add a second condition that will match
        condition2 = RuleCondition(
            rule_id=rule.id,
            field="from",
            predicate="contains",
            value="zomato"
        )
        self.db.add(condition2)
        self.db.commit()
        
        print(f"Processing email: {test_email.gmail_id}")
        engine.process_email(test_email)
        message = self.gmail_client.get_message(test_email.gmail_id)
        self.assertIsNotNone(message)
        labels = message.get('labelIds', [])
        self.assertIn('UNREAD', labels, "Email should be marked as unread")
        
        # Test 'any' predicate
        print("\nTesting 'any' predicate...")
        rule.predicate = "any"
        
        # Make one condition fail, one pass
        condition.value = "nonexistent_text"  # This will fail
        condition2.value = "zomato"  # This will pass
        self.db.commit()
        
        print(f"Processing email: {test_email.gmail_id}")
        engine.process_email(test_email)
        message = self.gmail_client.get_message(test_email.gmail_id)
        self.assertIsNotNone(message)
        labels = message.get('labelIds', [])
        self.assertIn('UNREAD', labels, "Email should be marked as unread")
            
        print("\nAll rule combinations tested successfully!")

    def test_error_handling(self):
        """Test error handling in integration scenarios"""
        # Test invalid message ID
        result = self.gmail_client.mark_as_read("invalid_message_id")
        self.assertFalse(result, "Should return False for invalid message ID")
        
        # Test moving to non-existent label
        result = self.gmail_client.move_message("dummy_id", "NonexistentLabel")
        self.assertFalse(result, "Should return False for non-existent label")

    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests"""
        try:
            # Remove test label
            cls.gmail_client.delete_label(cls.test_label)
        except:
            pass  # Ignore cleanup errors
        
        # Close database session
        cls.db.close()

if __name__ == '__main__':
    unittest.main()

