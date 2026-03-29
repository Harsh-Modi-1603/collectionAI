import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai
from dotenv import load_dotenv
import json

from app import config
from app.services import swagger_service, jira_service, groq_service, postman_service
from app.services.jira_service import JiraAuthError, JiraNotFoundError
from app.models import MultiTicketRequest, MultiTicketResponse, ChatRefineRequest, ChatRefineResponse

# Load API key
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    swagger_service.load_catalog(config.SWAGGER_URL)

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
    # Truncate very long descriptions to keep response times reasonable
    if len(description) > 3000:
        description = description[:3000] + "\n... (truncated for brevity)"

    prompt = f"""
You are an expert QA engineer. 
Generate a **Postman Collection v2.1 JSON** for API test cases based on this ticket.

Summary: {summary}
Description: {description}

### Rules:
- First, analyze the ticket and **determine the correct HTTP method** (POST, GET, PUT, DELETE, PATCH, etc.).
- Decide the **endpoint path** based on the summary/description (e.g., /api/users, /api/orders/{{id}}, etc.).
- Always use `{{{{baseUrl}}}}` as the host (no hardcoded domains).
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
- IMPORTANT: In all test scripts, use ONLY `pm.collectionVariables.set(...)` and `pm.collectionVariables.get(...)` to store and retrieve variables. NEVER use `pm.environment.set(...)` or `pm.environment.get(...)`.
- Do NOT include any explanatory comments, warnings, or notes outside the JSON. Return pure JSON only.

### Output:
Return only valid JSON following the Postman collection v2.1 schema. No markdown, no explanation, no warnings — just the JSON.
    """

    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(prompt)

    try:
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("```json")[-1].split("```")[0].strip()
        return text
    except Exception as e:
        raise HTTPException(status_code=500, detail="Unable to process AI response. Please try again.")

# API route

@app.post("/generate")
async def generate_collection(ticket: Ticket):
    try:
        collection_json_str = generate_postman_collection(ticket.summary, ticket.description)
        # Convert the string into an actual JSON object
        collection_json = json.loads(collection_json_str)
        return {"postman_collection": collection_json}
    except Exception as e:
        err = str(e)
        if "429" in err or "quota" in err.lower():
            raise HTTPException(status_code=429, detail="AI quota exceeded. Please try again later or upgrade your Gemini API plan.")
        raise HTTPException(status_code=500, detail=str(e))



@app.post("/generate-from-tickets", response_model=MultiTicketResponse)
async def generate_from_tickets(request: MultiTicketRequest):
    warnings: list[str] = []
    suites: list[dict] = []
    processed_ids: list[str] = []
    failed_ids: list[str] = []

    catalog = swagger_service.get_catalog()

    for ticket_id in request.ticket_ids:
        try:
            ticket_context = jira_service.fetch_ticket_with_subtasks(ticket_id)
        except JiraAuthError as e:
            raise HTTPException(status_code=401, detail=str(e))
        except JiraNotFoundError:
            warnings.append(f"Ticket '{ticket_id}' not found in JIRA — skipped.")
            failed_ids.append(ticket_id)
            continue
        except Exception as e:
            warnings.append(f"Failed to fetch ticket '{ticket_id}': {e} — skipped.")
            failed_ids.append(ticket_id)
            continue

        try:
            llm_result = groq_service.generate_test_cases_comprehensive(ticket_context, catalog)
        except Exception as e:
            warnings.append(f"LLM generation failed for '{ticket_id}': {e} — skipped.")
            failed_ids.append(ticket_id)
            continue

        warnings.extend(llm_result.get("warnings", []))
        flow_steps = llm_result.get("flow_steps", [])

        suite = postman_service.build_test_suite(ticket_context, flow_steps)
        suites.append(suite)
        processed_ids.append(ticket_id)

    if not suites:
        raise HTTPException(
            status_code=400,
            detail=f"All submitted ticket IDs failed to process: {', '.join(failed_ids)}",
        )

    collection = postman_service.assemble_collection(
        suites=suites,
        collection_name=request.collection_name,
        ticket_ids=processed_ids,
    )

    return MultiTicketResponse(postman_collection=collection, warnings=warnings)


@app.post("/chat")
async def chat(request: dict):
    """
    General chat endpoint for questions about the collection.
    Provides conversational responses without modifying the collection.
    """
    from groq import Groq
    
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    
    user_message = request.get("message", "")
    collection = request.get("collection")
    chat_history = request.get("history", [])
    
    if not user_message:
        raise HTTPException(status_code=400, detail="Message is required")
    
    # Build context from collection
    context = ""
    if collection:
        # Extract useful info from collection
        collection_name = collection.get("info", {}).get("name", "Unknown")
        items = collection.get("item", [])
        request_count = len(items)
        
        # Get endpoint list
        endpoints = []
        for item in items[:20]:  # Limit to first 20 for context
            req = item.get("request", {})
            method = req.get("method", "GET")
            url = req.get("url", {})
            if isinstance(url, dict):
                path = "/".join(url.get("path", []))
            else:
                path = str(url)
            endpoints.append(f"{method} {path}")
        
        context = f"""
Current Collection: {collection_name}
Total Requests: {request_count}
Sample Endpoints:
{chr(10).join(f"  - {ep}" for ep in endpoints[:10])}
"""
    
    # Build conversation history
    messages = [
        {
            "role": "system",
            "content": f"""You are a friendly, conversational QA assistant helping users understand their Postman collections.

CRITICAL RULES:
1. Be warm, friendly, and conversational - talk like a helpful colleague, not a technical manual
2. Keep responses SHORT (2-3 paragraphs max, 4-5 sentences each)
3. Use simple, clear language - avoid jargon unless necessary
4. Format responses with proper paragraphs and line breaks for readability
5. When giving suggestions, use bullet points (•) not numbered lists
6. Don't use markdown headers (###) or code blocks unless showing actual code
7. Be encouraging and positive in tone

You help users:
• Understand what their collection does
• Explain endpoints in simple terms
• Suggest practical improvements
• Answer questions about API testing

{context}

Remember: Keep it SHORT, FRIENDLY, and EASY TO READ!"""
        }
    ]
    
    # Add chat history (last 10 messages for context)
    for msg in chat_history[-10:]:
        messages.append({
            "role": msg.get("role", "user"),
            "content": msg.get("content", "")
        })
    
    # Add current message
    messages.append({
        "role": "user",
        "content": user_message
    })
    
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.7,
            max_tokens=800,  # Shorter responses for chat
        )
        
        ai_response = response.choices[0].message.content.strip()
        
        return {
            "response": ai_response,
            "success": True
        }
        
    except Exception as e:
        error_msg = str(e)
        # Check for rate limit errors
        if "429" in error_msg or "rate_limit" in error_msg.lower():
            user_friendly_msg = "I'm taking a short break due to high usage. Please try again in a few minutes!"
        else:
            user_friendly_msg = "I'm having trouble responding right now. Please try again in a moment."
        
        # Return friendly error as a chat message instead of HTTP error
        return {
            "response": f"❌ {user_friendly_msg}",
            "success": False
        }


@app.post("/refine-collection", response_model=ChatRefineResponse)
async def refine_collection(request: ChatRefineRequest):
    """
    Chat-based refinement endpoint.
    User provides existing collection + refinement instructions.
    LLM modifies the collection based on instructions.
    """
    from groq import Groq
    
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    
    prompt = f"""You are an expert QA engineer. The user has a Postman collection and wants to refine it.

EXISTING COLLECTION:
{json.dumps(request.existing_collection, indent=2)}

USER INSTRUCTIONS:
{request.user_message}

TASK:
Modify the collection according to the user's instructions. You can:
- Add new requests
- Modify existing requests (change method, endpoint, body, headers, tests)
- Remove requests
- Reorder requests
- Update test scripts
- Add/modify variable extractions

IMPORTANT:
- Use ONLY pm.collectionVariables.set/get in test scripts, NEVER pm.environment
- Always use {{{{baseUrl}}}} as the host variable
- Return the COMPLETE modified collection as valid JSON
- No markdown, no explanations, just the JSON

OUTPUT:
Return the complete modified Postman collection v2.1 JSON."""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert QA engineer. You modify Postman collections based on user instructions. Always respond with valid JSON only."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3,  # Lower for more consistent JSON
            max_tokens=8000,
        )
        
        text = response.choices[0].message.content.strip()
        
        # Extract JSON
        if "```json" in text.lower():
            start_marker = text.lower().find("```json")
            if start_marker != -1:
                start = start_marker + 7
                end_marker = text.find("```", start)
                if end_marker != -1:
                    text = text[start:end_marker].strip()
        elif text.startswith("```"):
            text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
        
        # Find JSON start
        json_start = -1
        for i, char in enumerate(text):
            if char in ['{', '[']:
                json_start = i
                break
        if json_start > 0:
            text = text[json_start:]
        
        refined_collection = json.loads(text)
        
        return ChatRefineResponse(
            refined_collection=refined_collection,
            message="Collection refined successfully"
        )
        
    except Exception as e:
        error_msg = str(e)
        # Check for rate limit errors
        if "429" in error_msg or "rate_limit" in error_msg.lower():
            raise HTTPException(
                status_code=503,
                detail="The AI service is temporarily busy. Please try again in a few minutes."
            )
        # Check for JSON parsing errors
        elif "json" in error_msg.lower():
            raise HTTPException(
                status_code=500,
                detail="Unable to process your request. Please try rephrasing your instructions."
            )
        else:
            raise HTTPException(
                status_code=500,
                detail="Unable to refine collection at this time. Please try again later."
            )


@app.post("/add-tickets-to-collection")
async def add_tickets_to_collection(request: dict):
    """
    Add new tickets to an existing collection.
    Merges new ticket test cases into the existing collection.
    """
    existing_collection = request.get("existing_collection")
    new_ticket_ids = request.get("ticket_ids", [])
    
    if not existing_collection or not new_ticket_ids:
        raise HTTPException(status_code=400, detail="Missing existing_collection or ticket_ids")
    
    warnings: list[str] = []
    suites: list[dict] = []
    processed_ids: list[str] = []
    failed_ids: list[str] = []
    
    catalog = swagger_service.get_catalog()
    
    for ticket_id in new_ticket_ids:
        try:
            ticket_context = jira_service.fetch_ticket_with_subtasks(ticket_id)
        except JiraAuthError as e:
            raise HTTPException(status_code=401, detail=str(e))
        except JiraNotFoundError:
            warnings.append(f"Ticket '{ticket_id}' not found in JIRA — skipped.")
            failed_ids.append(ticket_id)
            continue
        except Exception as e:
            warnings.append(f"Failed to fetch ticket '{ticket_id}': {e} — skipped.")
            failed_ids.append(ticket_id)
            continue
        
        try:
            llm_result = groq_service.generate_test_cases_comprehensive(ticket_context, catalog)
        except Exception as e:
            warnings.append(f"LLM generation failed for '{ticket_id}': {e} — skipped.")
            failed_ids.append(ticket_id)
            continue
        
        warnings.extend(llm_result.get("warnings", []))
        flow_steps = llm_result.get("flow_steps", [])
        
        suite = postman_service.build_test_suite(ticket_context, flow_steps)
        suites.append(suite)
        processed_ids.append(ticket_id)
    
    # Merge new items into existing collection
    existing_items = existing_collection.get("item", [])
    for suite in suites:
        new_items = suite.get("item", [])
        existing_items.extend(new_items)
    
    existing_collection["item"] = existing_items
    
    # Update description
    existing_desc = existing_collection.get("info", {}).get("description", "")
    if processed_ids:
        new_desc = f"{existing_desc}, {', '.join(processed_ids)}" if existing_desc else f"Generated from tickets: {', '.join(processed_ids)}"
        existing_collection["info"]["description"] = new_desc
    
    return {
        "postman_collection": existing_collection,
        "warnings": warnings,
        "added_tickets": processed_ids
    }

