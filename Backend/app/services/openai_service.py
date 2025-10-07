# app/services/openai_service.py
from openai import OpenAI
import os

client = OpenAI(api_key=os.getenv("GOOGLE_API_KEY"))

def generate_test_skeleton(ticket_data: dict) -> str:
    prompt = f"""
    Generate API test skeletons based on the following Jira ticket details:

    {ticket_data}
    """
    
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=300
    )
    
    return response.choices[0].message.content
