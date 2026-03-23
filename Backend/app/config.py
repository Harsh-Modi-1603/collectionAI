from dotenv import load_dotenv
import os

load_dotenv()
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY    = os.getenv("GOOGLE_API_KEY")
SWAGGER_URL       = os.getenv("SWAGGER_URL")

# JIRA API Token (shared for all users)
JIRA_API_TOKEN    = os.getenv("JIRA_API_TOKEN")
JIRA_EMAIL        = os.getenv("JIRA_EMAIL")
JIRA_BASE_URL     = os.getenv("JIRA_BASE_URL")
