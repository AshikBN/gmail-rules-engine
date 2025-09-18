from setuptools import setup, find_packages

setup(
    name="gmail-rules-engine",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        'google-auth-oauthlib==1.0.0',
        'google-auth-httplib2==0.1.0',
        'google-api-python-client==2.86.0',
        'SQLAlchemy==2.0.19',
        'alembic==1.11.1',
        'python-dateutil==2.8.2',
        'python-dotenv==1.0.0',
        'pydantic==2.6.1',
        'structlog==23.1.0',
    ],
)

