#!/usr/bin/env python3
"""
Gmail Rules Engine - Main entry point
"""
import argparse
import json
import logging
import os
import sys
from pathlib import Path

# Add the parent directory to Python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import structlog
from dotenv import load_dotenv

from database import Email, Rule, RuleCondition, RuleAction, get_db_session, init_db
from gmail import GmailClient, get_gmail_service, get_user_email
from rules import RulesEngine, RulesConfig

# Configure logging
logging.basicConfig(level=logging.INFO)  # Only show important info
logger = structlog.get_logger()

# Disable debug logging for specific modules
logging.getLogger('googleapiclient.discovery').setLevel(logging.WARNING)
logging.getLogger('rules.engine').setLevel(logging.INFO)
logging.getLogger('gmail.client').setLevel(logging.INFO)

def load_rules(db) -> RulesConfig:
    """Load rules from configuration file and sync with database"""
    rules_file = os.getenv('RULES_FILE', 'config/rules.json')
    try:
        with open(rules_file, 'r') as f:
            rules_data = json.load(f)
        
        rules_config = RulesConfig(**rules_data)
        
        # Always recreate rules to ensure proper identifier management
        # Rule identifiers should change when:
        # 1. Rule conditions change (different matching logic)
        # 2. Rule actions change (different behavior)
        # 3. Rule predicate changes (all vs any)
        # This ensures that emails are reprocessed when rule logic changes
        
        # Clear existing rules
        db.query(RuleAction).delete()
        db.query(RuleCondition).delete()
        db.query(Rule).delete()
        db.commit()
        
        # Create new rules in database
        for rule_config in rules_config.rules:
            rule = Rule(
                identifier=rule_config.identifier,
                name=rule_config.name,
                predicate=rule_config.predicate,
                active=True
            )
            db.add(rule)
            db.flush()  # Get the rule ID
            
            # Add conditions
            for condition in rule_config.conditions:
                db_condition = RuleCondition(
                    rule_id=rule.id,
                    field=condition.field,
                    predicate=condition.predicate,
                    value=condition.value,
                    unit=condition.unit
                )
                db.add(db_condition)
            
            # Add actions
            for action in rule_config.actions:
                db_action = RuleAction(
                    rule_id=rule.id,
                    action_type=action.type,
                    action_value=action.destination if action.type == 'move_message' else None
                )
                db.add(db_action)
        
        db.commit()
        logger.info("Rules synced to database", count=len(rules_config.rules))
        return rules_config
        
    except Exception as e:
        logger.error("Error loading rules", error=str(e))
        raise

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Gmail Rules Engine')
    parser.add_argument('--max-emails', type=int, help='Maximum number of emails to process')
    parser.add_argument('--days', type=int, help='Process emails from last N days')
    return parser.parse_args()

def main():
    """Main entry point for the Gmail Rules Engine"""
    try:
        # Parse command line arguments
        args = parse_args()
        
        # Load environment variables
        load_dotenv()
        
        logger.info("Starting Gmail Rules Engine...")

        # Initialize database
        init_db()
        
        with get_db_session() as db:
            # Set up Gmail client
            service = get_gmail_service()
            user_email = get_user_email(service)
            if not user_email:
                logger.error("Failed to get user email")
                return

            logger.info("Authenticated with Gmail", user=user_email)
            gmail_client = GmailClient(service)

            # Load rules
            rules_config = load_rules(db)
            logger.info("Loaded rules", count=len(rules_config.rules))

            # Initialize rules engine
            rules_engine = RulesEngine(db, gmail_client)

            # Get list of messages
            logger.info("Fetching messages from Gmail...", max_emails=args.max_emails, days=args.days)
            query = f"newer_than:{args.days}d" if args.days else None
            messages = gmail_client.list_all_messages(query=query, max_total=args.max_emails)
            logger.info(f"Found {len(messages)} messages to process")

            # Process messages in batches
            BATCH_SIZE = 50
            for i in range(0, len(messages), BATCH_SIZE):
                batch = messages[i:i + BATCH_SIZE]
                logger.info(f"Processing batch {i//BATCH_SIZE + 1} ({len(batch)} messages)")
                
                # Step 1: Get all message IDs in this batch
                msg_ids = [msg['id'] for msg in batch]
                
                # Step 2: Find which emails already exist in DB
                existing_emails = {
                    email.gmail_id: email 
                    for email in db.query(Email).filter(Email.gmail_id.in_(msg_ids)).all()
                }
                
                # Step 3: Fetch missing emails from Gmail
                emails_to_process = []
                for msg_id in msg_ids:
                    if msg_id in existing_emails:
                        # Use stored version
                        emails_to_process.append(existing_emails[msg_id])
                        logger.info(f"Using stored email {msg_id}")
                    else:
                        # Fetch from Gmail
                        message = gmail_client.get_message(msg_id)
                        if not message:
                            logger.warning(f"Could not fetch message {msg_id}, skipping...")
                            continue
                            
                        email = gmail_client.message_to_email(message)
                        db.add(email)
                        emails_to_process.append(email)
                        logger.info(f"Fetched new email {msg_id}")
                
                # Step 4: Process all emails in batch through rules
                for email in emails_to_process:
                    logger.info("Processing email", subject=email.subject)
                    rules_engine.process_email(email)
                
                # Commit the batch
                db.commit()
                logger.info(f"Completed batch {i//BATCH_SIZE + 1}")

            logger.info("Email processing completed")
    except Exception as e:
        logger.error("Error processing emails", error=str(e))
        raise

if __name__ == "__main__":
    main()