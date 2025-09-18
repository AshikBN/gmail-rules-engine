"""
Gmail API integration package
"""
from .auth import get_gmail_service, get_user_email
from .client import GmailClient

__all__ = ['get_gmail_service', 'get_user_email', 'GmailClient']
