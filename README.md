# Gmail Rules Engine

A Python-based email automation system that processes Gmail messages based on customizable rules.

## Features

- Gmail API integration with OAuth authentication
- Rule-based email processing
- Customizable actions (mark as read/unread, move messages)
- SQLite database for email and rule storage
- Command-line interface

## Prerequisites

- Python 3.8 or higher
- Gmail account
- Google Cloud Project with Gmail API enabled

## Installation

1. Clone the repository:
```bash
git clone https://github.com/AshikBN/gmail-rules-engine.git
cd gmail-rules-engine
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up Google Cloud Project and OAuth credentials:
   - Go to Google Cloud Console
   - Create a new project
   - Enable Gmail API
   - Create OAuth 2.0 credentials
   - Download credentials and save it in the .env file as shown

4. Create `.env` file:

    #example env file

    ```
    # Database
    DATABASE_URL=sqlite:///gmail_rules.db

    # Gmail API
    GMAIL_USER_ID=me
    GMAIL_CLIENT_ID=xxx
    GMAIL_CLIENT_SECRET=xxx
    GMAIL_PROJECT_ID=xxx
    GMAIL_AUTH_URI=https://accounts.google.com/o/oauth2/auth
    GMAIL_TOKEN_URI=https://oauth2.googleapis.com/token
    GMAIL_AUTH_PROVIDER_CERT_URL=https://www.googleapis.com/oauth2/v1/certs
    GMAIL_TOKEN_FILE=.secrets/token.json

    # Application
    RULES_FILE=config/rules.json
    LOG_LEVEL=INFO
    ```

## Usage

1. Configure rules in `config/rules.json`
2. Run the script:
```bash
python src/main.py --days 2
```

## Rule Configuration

Rules are defined in JSON format. Example:
```json
{
  "rules": [
    {
      "name": "Interview Emails",
      "predicate": "all",
      "conditions": [
        {
          "field": "from",
          "predicate": "contains",
          "value": "example.com"
        },
        {
          "field": "subject",
          "predicate": "contains",
          "value": "Interview"
        }
      ],
      "actions": [
        {
          "type": "mark_as_read"
        },
        {
          "type": "move_message",
          "destination": "Inbox"
        }
      ]
    }
  ]
}
```

## Testing

Run tests with:
```bash
pytest
```


