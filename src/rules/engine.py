"""
Rules engine for processing emails based on configured rules
"""
from datetime import datetime, timedelta
import json
import logging

from src.database.models import Email, ProcessedEmail, Rule, RuleCondition, RuleAction
from src.gmail.client import GmailClient

logger = logging.getLogger(__name__)

class RulesEngine:
    """Engine for processing emails based on rules"""

    def __init__(self, db, gmail_client: GmailClient):
        self.db = db
        self.gmail_client = gmail_client

    def process_email(self, email: Email) -> None:
        """Process a single email against all active rules"""
        # Get all active rules with their conditions and actions
        rules = self.db.query(Rule).filter(Rule.active == True).all()
        
        logger.info(f"Processing email: {email.subject} (From: {email.from_address})")
        
        for rule in rules:
            # Check if email was processed and get previous identifier
            was_processed, prev_identifier = self._is_already_processed(email.gmail_id, rule.identifier)
            
            if was_processed:
                logger.debug(f"Email already processed with rule identifier {rule.identifier}, skipping...")
                continue
                
            if prev_identifier:
                logger.debug(f"Email previously processed with different identifier {prev_identifier}, will process with new identifier {rule.identifier}...")
            # Get conditions and actions for this rule
            conditions = self.db.query(RuleCondition).filter(RuleCondition.rule_id == rule.id).all()
            actions = self.db.query(RuleAction).filter(RuleAction.rule_id == rule.id).all()
            
            # Process the email if it matches the conditions
            logger.debug(f"\nChecking rule: {rule.name}")
            logger.debug(f"Rule predicate: {rule.predicate}")
            
            # Check if rule conditions match
            logger.debug("\nEvaluating rule conditions:")
            match = self._evaluate_rule(rule, conditions, email)
            logger.debug(f"Rule conditions matched: {match}")
            if match:
                logger.debug("Rule conditions matched! Executing actions...")
                logger.debug(f"Found {len(actions)} actions to execute")
                
                # Execute rule actions
                for action in actions:
                    logger.debug(f"Executing action: {action.action_type}")
                    success = False
                    
                    if action.action_type == 'mark_as_read':
                        success = self.gmail_client.mark_as_read(email.gmail_id)
                        if success:
                            email.is_read = True
                            
                    elif action.action_type == 'mark_as_unread':
                        logger.debug(f"Attempting to mark email {email.gmail_id} as unread")
                        success = self.gmail_client.mark_as_unread(email.gmail_id)
                        logger.debug(f"mark_as_unread result: {success}")
                        if success:
                            email.is_read = False
                            logger.debug("Updated email.is_read to False")
                        else:
                            logger.error("Failed to mark email as unread")
                            
                    elif action.action_type == 'move_message':
                        success = self.gmail_client.move_message(email.gmail_id, action.action_value)
                        if success:
                            email.current_label = action.action_value
                            
                    if success:
                        logger.debug(f"Action {action.action_type} succeeded")
                        self.db.commit()
                    else:
                        logger.error(f"Action {action.action_type} failed")
                
                # Only mark as processed if all actions succeeded
                if success:
                    self._mark_as_processed(email.gmail_id, rule.identifier)
                    logger.debug(f"Successfully processed email with rule {rule.name}")
                else:
                    logger.error(f"Failed to process email with rule {rule.name}")
            else:
                logger.debug("Rule conditions did not match")

    def _evaluate_rule(self, rule: Rule, conditions: list[RuleCondition], email: Email) -> bool:
        """Evaluate if an email matches a rule's conditions"""
        if not conditions:
            logger.debug("No conditions to evaluate")
            return False
            
        results = []
        for condition in conditions:
            result = self._evaluate_condition(condition, email)
            logger.debug(f"Condition: {condition.field} {condition.predicate} '{condition.value}' -> {result}")
            results.append(result)
        
        logger.debug(f"All condition results: {results}")
        if rule.predicate == 'all':
            result = all(results)
            logger.debug(f"All conditions must match -> {result}")
            return result
        else:  # 'any'
            result = any(results)
            logger.debug(f"Any condition must match -> {result}")
            return result

    def _evaluate_condition(self, condition: RuleCondition, email: Email) -> bool:
        """Evaluate a single condition against an email"""
        if condition.field == 'from':
            return self._evaluate_string_condition(condition, email.from_address)
        elif condition.field == 'subject':
            return self._evaluate_string_condition(condition, email.subject or '')
        elif condition.field == 'message':
            return self._evaluate_string_condition(condition, email.content or '')
        elif condition.field == 'received_date':
            return self._evaluate_date_condition(condition, email.received_date)
        return False

    def _evaluate_string_condition(self, condition: RuleCondition, value: str) -> bool:
        """Evaluate a string-based condition"""
        logger.debug(f"\nString comparison for {condition.field}:")
        logger.debug(f"Predicate: {condition.predicate}")
        logger.debug(f"Expected : '{condition.value}'")
        logger.debug(f"Actual   : '{value}'")
        
        # For contains/not_contains, show what we're looking for
        if condition.predicate in ['contains', 'does_not_contain']:
            logger.debug(f"Looking for '{condition.value.lower()}' in '{value.lower()}'")
        elif condition.predicate in ['equals', 'does_not_equal']:
            logger.debug(f"Comparing '{condition.value.lower()}' == '{value.lower()}'")
        
        result = False
        if condition.predicate == 'contains':
            result = condition.value.lower() in value.lower()
            logger.debug(f"Contains check: '{condition.value.lower()}' in '{value.lower()}' -> {result}")
        elif condition.predicate == 'does_not_contain':
            result = condition.value.lower() not in value.lower()
            logger.debug(f"Not contains check: '{condition.value.lower()}' not in '{value.lower()}' -> {result}")
        elif condition.predicate == 'equals':
            result = condition.value.lower() == value.lower()
            logger.debug(f"Equals check: '{condition.value.lower()}' == '{value.lower()}' -> {result}")
        elif condition.predicate == 'does_not_equal':
            result = condition.value.lower() != value.lower()
            logger.debug(f"Not equals check: '{condition.value.lower()}' != '{value.lower()}' -> {result}")
        return result

    def _evaluate_date_condition(self, condition: RuleCondition, date: datetime) -> bool:
        """Evaluate a date-based condition"""
        try:
            value = int(condition.value)
            # Return False for negative or zero values
            if value <= 0:
                return False
                
            if condition.unit == 'months':
                delta = timedelta(days=value * 30)  # Approximate
            else:  # days
                delta = timedelta(days=value)
            
            if condition.predicate == 'less_than':
                return datetime.utcnow() - date < delta
            elif condition.predicate == 'greater_than':
                return datetime.utcnow() - date > delta
        except (ValueError, TypeError):
            return False
        return False

    def _is_already_processed(self, gmail_id: str, rule_identifier: str) -> tuple[bool, str]:
        """
        Check if an email was already processed by a rule and get the previous rule identifier
        Returns: (was_processed, previous_identifier)
        """
        # Get all processed records for this email
        processed_records = self.db.query(ProcessedEmail).filter(
            ProcessedEmail.gmail_id == gmail_id
        ).all()
        
        if not processed_records:
            return False, ""
            
        # Check if any record has the current identifier
        for record in processed_records:
            if record.rule_identifier == rule_identifier:
                logger.info(f"Found matching identifier {rule_identifier} for email {gmail_id}")
                return True, record.rule_identifier
            
        # No matching identifier found, allow processing
        # Return the most recent identifier for logging
        latest_record = max(processed_records, key=lambda r: r.processed_at)
        return False, latest_record.rule_identifier

    def _mark_as_processed(self, gmail_id: str, rule_identifier: str) -> None:
        """Mark an email as processed by a rule"""
        # Check if there's an existing record
        processed = self.db.query(ProcessedEmail).filter(
            ProcessedEmail.gmail_id == gmail_id,
            ProcessedEmail.rule_identifier == rule_identifier
        ).first()
        
        if processed:
            # Update existing record's timestamp
            processed.processed_at = datetime.utcnow()
            logger.debug(f"Updated processing timestamp for email {gmail_id} with rule {rule_identifier}")
        else:
            # Create new record
            processed = ProcessedEmail(gmail_id=gmail_id, rule_identifier=rule_identifier)
            self.db.add(processed)
            logger.debug(f"Marked email {gmail_id} as processed by rule {rule_identifier}")
            
        self.db.commit()