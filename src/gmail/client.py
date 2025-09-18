"""
Gmail API client for email operations
"""
from datetime import datetime
from typing import Dict, List, Optional
import logging
import json

from googleapiclient.discovery import Resource
from googleapiclient.errors import HttpError

from src.database.models import Email

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
# Add console handler if not already added
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

class GmailClient:
    """Gmail API client for email operations"""
    
    def __init__(self, service: Resource):
        self.service = service
        self.user_id = 'me'

    def list_messages(self, query: str = None, max_results: int = None, page_token: str = None) -> Dict:
        """List messages in the user's mailbox"""
        try:
            request = self.service.users().messages().list(
                userId=self.user_id,
                q=query,
                maxResults=max_results,
                pageToken=page_token
            )
            
            response = request.execute()
            return {
                'messages': response.get('messages', []),
                'nextPageToken': response.get('nextPageToken')
            }
        except Exception as e:
            logger.error(f"Error listing messages: {e}")
            return {'messages': [], 'nextPageToken': None}

    def list_all_messages(self, query: str = None, max_total: int = None) -> List[Dict]:
        """List all messages, handling pagination"""
        messages = []
        page_token = None
        
        while True:
            remaining = max_total - len(messages) if max_total else None
            if remaining is not None and remaining <= 0:
                break
                
            response = self.list_messages(
                query=query,
                max_results=remaining,
                page_token=page_token
            )
            
            messages.extend(response['messages'])
            page_token = response.get('nextPageToken')
            
            logger.info(f"Fetched {len(messages)} messages so far...")
            
            if not page_token or (max_total and len(messages) >= max_total):
                break
        
        return messages

    def get_message(self, msg_id: str) -> Optional[Dict]:
        """Get a specific message by ID"""
        try:
            message = self.service.users().messages().get(
                userId=self.user_id,
                id=msg_id,
                format='full'
            ).execute()
            return message
        except Exception as e:
            logger.error(f"Error getting message {msg_id}: {e}")
            return None

    def mark_as_read(self, msg_id: str) -> bool:
        """Mark a message as read"""
        logger.debug(f"Attempting to mark message {msg_id} as read")
        try:
            # First get the current message to verify its state
            message = self.get_message(msg_id)
            if not message:
                logger.error("Failed to get message")
                return False
                
            current_labels = message.get('labelIds', [])
            logger.debug(f"Current labels before marking as read: {current_labels}")
            
            if 'UNREAD' not in current_labels:
                logger.debug("Message is already marked as read")
                return True
            
            result = self.service.users().messages().modify(
                userId=self.user_id,
                id=msg_id,
                body={'removeLabelIds': ['UNREAD']}
            ).execute()
            
            logger.debug(f"Mark as read API response: {json.dumps(result, indent=2)}")
            
            # Verify the change
            message = self.get_message(msg_id)
            new_labels = message.get('labelIds', [])
            logger.debug(f"Labels after marking as read: {new_labels}")
            
            success = 'UNREAD' not in new_labels
            logger.debug(f"Mark as read {'succeeded' if success else 'failed'}")
            return success
            
        except HttpError as e:
            logger.error(f"HTTP error marking message {msg_id} as read: {e.resp.status} - {e.content}")
            return False
        except Exception as e:
            logger.error(f"Failed to mark message {msg_id} as read: {e}")
            return False

    def mark_as_unread(self, msg_id: str) -> bool:
        """Mark a message as unread"""
        logger.debug(f"Attempting to mark message {msg_id} as unread")
        try:
            # First get the current message to verify its state
            message = self.get_message(msg_id)
            if not message:
                logger.error("Failed to get message")
                return False
                
            current_labels = message.get('labelIds', [])
            logger.debug(f"Current labels before marking as unread: {current_labels}")
            
            if 'UNREAD' in current_labels:
                logger.debug("Message is already marked as unread")
                return True
            
            # Try to add UNREAD label
            try:
                result = self.service.users().messages().modify(
                    userId=self.user_id,
                    id=msg_id,
                    body={'addLabelIds': ['UNREAD']}
                ).execute()
                logger.debug(f"Mark as unread API response: {json.dumps(result, indent=2)}")
            except Exception as e:
                logger.error(f"API call failed: {e}")
                return False
            
            # Verify the change
            message = self.get_message(msg_id)
            if not message:
                logger.error("Failed to get message after modification")
                return False
                
            new_labels = message.get('labelIds', [])
            logger.debug(f"Labels after marking as unread: {new_labels}")
            
            success = 'UNREAD' in new_labels
            logger.debug(f"Mark as unread {'succeeded' if success else 'failed'}")
            return success
            
        except HttpError as e:
            logger.error(f"HTTP error marking message {msg_id} as unread: {e.resp.status} - {e.content}")
            return False
        except Exception as e:
            logger.error(f"Failed to mark message {msg_id} as unread: {e}")
            return False

    def create_label(self, label_name: str) -> bool:
        """Create a new Gmail label"""
        try:
            logger.debug(f"Creating label {label_name}")
            
            # Check if label already exists
            existing_id = self.get_label_id(label_name)
            if existing_id:
                logger.debug(f"Label {label_name} already exists with ID {existing_id}")
                return True
            
            # Create new label
            label = {
                'name': label_name,
                'labelListVisibility': 'labelShow',
                'messageListVisibility': 'show'
            }
            result = self.service.users().labels().create(
                userId=self.user_id,
                body=label
            ).execute()
            
            logger.debug(f"Created label {label_name} with ID {result['id']}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating label {label_name}: {e}")
            return False
            
    def delete_label(self, label_name: str) -> bool:
        """Delete a Gmail label"""
        try:
            logger.debug(f"Deleting label {label_name}")
            
            # Get label ID
            label_id = self.get_label_id(label_name)
            if not label_id:
                logger.debug(f"Label {label_name} not found")
                return True
            
            # Delete label
            self.service.users().labels().delete(
                userId=self.user_id,
                id=label_id
            ).execute()
            
            logger.debug(f"Deleted label {label_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting label {label_name}: {e}")
            return False
            
    def modify_labels(self, msg_id: str, add_labels: list = None, remove_labels: list = None) -> bool:
        """Modify labels for a message - add and/or remove labels"""
        try:
            logger.debug(f"Modifying labels for message {msg_id}")
            logger.debug(f"Adding labels: {add_labels}")
            logger.debug(f"Removing labels: {remove_labels}")
            
            # Convert label names to IDs
            add_label_ids = []
            if add_labels:
                for label in add_labels:
                    label_id = self.get_label_id(label)
                    if label_id:
                        add_label_ids.append(label_id)
            
            remove_label_ids = []
            if remove_labels:
                for label in remove_labels:
                    label_id = self.get_label_id(label)
                    if label_id:
                        remove_label_ids.append(label_id)
            
            # Modify labels
            self.service.users().messages().modify(
                userId=self.user_id,
                id=msg_id,
                body={
                    'addLabelIds': add_label_ids,
                    'removeLabelIds': remove_label_ids
                }
            ).execute()
            
            logger.debug(f"Successfully modified labels for message {msg_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to modify labels for message {msg_id}: {e}")
            return False
            
    def get_label_id(self, label_name: str) -> str:
        """Get the ID of a Gmail label by name"""
        try:
            # List all labels
            results = self.service.users().labels().list(userId=self.user_id).execute()
            labels = results.get('labels', [])
            
            # Find the label by name
            for label in labels:
                if label['name'] == label_name:
                    logger.debug(f"Found label {label_name} with ID {label['id']}")
                    return label['id']
                    
            logger.error(f"Label {label_name} not found")
            return None
            
        except Exception as e:
            logger.error(f"Error getting label ID: {e}")
            return None

    def move_message(self, msg_id: str, destination: str) -> bool:
        """Move a message to a different label"""
        try:
            logger.debug(f"Moving message {msg_id} to {destination}")
            
            # Get current message to check its labels
            message = self.get_message(msg_id)
            if not message:
                logger.error("Failed to get message")
                return False

            current_labels = message.get('labelIds', [])
            logger.debug(f"Current labels before move: {current_labels}")
            
            # For built-in labels like STARRED, just add the label
            if destination.startswith(('STARRED', 'IMPORTANT', 'UNREAD')):
                add_labels = [destination]
                remove_labels = []
            else:
                # For custom labels, get the label ID
                label_id = self.get_label_id(destination)
                if not label_id:
                    logger.error(f"Could not find label ID for {destination}")
                    return False
                    
                remove_labels = ['INBOX', 'SPAM', 'TRASH']
                add_labels = [label_id]
            
            logger.debug(f"Adding labels: {add_labels}")
            logger.debug(f"Removing labels: {remove_labels}")
            
            # Modify the labels
            result = self.service.users().messages().modify(
                userId=self.user_id,
                id=msg_id,
                body={
                    'addLabelIds': add_labels,
                    'removeLabelIds': remove_labels
                }
            ).execute()
            
            logger.debug(f"Move message API response: {json.dumps(result, indent=2)}")
            
            # Verify the change
            message = self.get_message(msg_id)
            new_labels = message.get('labelIds', [])
            logger.debug(f"Labels after move: {new_labels}")
            
            # For custom labels, check if the label ID is in the new labels
            if destination.startswith(('STARRED', 'IMPORTANT', 'UNREAD')):
                success = destination in new_labels
            else:
                label_id = self.get_label_id(destination)
                success = label_id in new_labels
                
            logger.debug(f"Move {'succeeded' if success else 'failed'}")
            return success
            
        except HttpError as e:
            logger.error(f"HTTP error moving message {msg_id}: {e.resp.status} - {e.content}")
            return False
        except Exception as e:
            logger.error(f"Error moving message {msg_id}: {e}")
            return False

    def message_to_email(self, message: Dict) -> Email:
        """Convert a Gmail message to an Email model"""
        headers = {h['name']: h['value'] for h in message['payload']['headers']}
        
        # Parse the received date
        date_str = headers.get('Date')
        try:
            received_date = datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S %z')
        except:
            received_date = datetime.utcnow()

        return Email(
            gmail_id=message['id'],
            from_address=headers.get('From', ''),
            to_address=headers.get('To', ''),
            subject=headers.get('Subject', ''),
            content=self._get_message_content(message),
            received_date=received_date,
            is_read='UNREAD' not in message.get('labelIds', []),
            current_label='INBOX'  # Default to INBOX
        )

    def _get_message_content(self, message: Dict) -> str:
        """Extract the message content from the Gmail message"""
        if 'payload' not in message:
            return ''

        if 'body' in message['payload']:
            return message['payload']['body'].get('data', '')

        parts = message['payload'].get('parts', [])
        for part in parts:
            if part.get('mimeType') == 'text/plain':
                return part['body'].get('data', '')

        return ''