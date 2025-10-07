import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai
from dotenv import load_dotenv
import json

# Load API key
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

app = FastAPI()

# Allow CORS (for frontend or Postman testing)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request model
class Ticket(BaseModel):
    summary: str
    description: str

# Function to call Gemini
def generate_postman_collection(summary: str, description: str):
    prompt = f"""
You are an expert QA engineer. 
Generate a **Postman Collection v2.1 JSON** for API test cases based on this ticket.

Summary: {summary}
Description: {description}

### Rules:
- First, analyze the ticket and **determine the correct HTTP method** (POST, GET, PUT, DELETE, PATCH, etc.).
- Decide the **endpoint path** based on the summary/description (e.g., /api/users, /api/orders/{id}, etc.).
- Always use `{{baseUrl}}` as the host (no hardcoded domains).
- Place the endpoint under `"url": {{"raw": "{{{{baseUrl}}}}/api/..."}}, "host": ["{{{{baseUrl}}}}"], "path": [...]`.
- Use realistic request payloads instead of placeholders.
- Cover at least:
  - Success case with valid inputs (if applicable)
  - Missing required fields (one at a time)
  - Invalid formats
  - Empty or null values
  - Incorrect data types
  - For GET requests, cover invalid/unsupported query params, invalid IDs, etc.
  - For DELETE requests, cover valid deletion and invalid IDs.
- For each request, add Postman test scripts that check:
  - Correct **status code**
  - That response contains JSON (where applicable)

### Output:
Return only valid JSON following the Postman collection v2.1 schema.
    """

    model = genai.GenerativeModel("gemini-2.5-pro")
    response = model.generate_content(prompt)

    try:
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("```json")[-1].split("```")[0].strip()
        return text
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error parsing LLM response: {str(e)}")

# API route

@app.post("/generate")
async def generate_collection(ticket: Ticket):
    try:
        collection_json_str = generate_postman_collection(ticket.summary, ticket.description)
        # Convert the string into an actual JSON object
        collection_json = json.loads(collection_json_str)
        return {"postman_collection": collection_json}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))




