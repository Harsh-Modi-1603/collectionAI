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

from pydantic import Field
from typing import Optional

class MultiTicketRequest(BaseModel):
    ticket_ids: list[str] = Field(..., min_length=1, max_length=20)
    collection_name: Optional[str] = None

class MultiTicketResponse(BaseModel):
    postman_collection: dict
    warnings: list[str] = []


class ChatRefineRequest(BaseModel):
    existing_collection: dict
    user_message: str


class ChatRefineResponse(BaseModel):
    refined_collection: dict
    message: str
