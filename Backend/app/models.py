# app/models.py
from pydantic import BaseModel

class JiraTicket(BaseModel):
    summary: str
    description: str
    endpoint: str = None
    method: str = None
    parameters: dict = None
    expected_behavior: str = None

class PostmanRequest(BaseModel):
    api_description: str
