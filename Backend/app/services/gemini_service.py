# app/services/gemini_service.py
import google.generativeai as genai
import os
import json

# Configure Gemini with API key
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise RuntimeError("Missing GOOGLE_API_KEY. Please set it in your .env file.")
genai.configure(api_key=api_key)

def generate_test_cases(ticket: dict):
    description = ticket.get("description", "")
    if not description:
        return None

    prompt = f"""
You are a QA assistant. Generate detailed API test cases in JSON format based only on this Jira ticket:

Summary: {ticket.get("summary", "Untitled")}
Description: {description}

Do not ask the user for endpoint or HTTP method. Determine the method (GET, POST, PUT, DELETE) from the test cases themselves.

Format output strictly as JSON with this structure:
[
  {{
    "id": "TC-01",
    "title": "Meaningful test case title",
    "steps": ["Step 1", "Step 2"],
    "expected_result": "Expected result",
    "method": "GET/POST/PUT/DELETE",
    "endpoint": "/api/path"
  }}
]
    """

    try:
        model = genai.GenerativeModel("gemini-2.5-pro") 
        response = model.generate_content(prompt)
        text = response.text.strip()

        # Handle triple-backtick JSON wrapper
        if text.startswith("```"):
            text = text.strip("```").replace("json", "").strip()

        return json.loads(text)

    except Exception as e:
        print(f"❌ Error calling Gemini: {e}")
        return None
