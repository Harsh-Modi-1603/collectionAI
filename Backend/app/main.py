import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai
from dotenv import load_dotenv
import json

from app import config
from app.services import swagger_service, jira_service, gemini_service, postman_service
from app.services.jira_service import JiraAuthError, JiraNotFoundError
from app.models import MultiTicketRequest, MultiTicketResponse

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
        err = str(e)
        if "429" in err or "quota" in err.lower():
            raise HTTPException(status_code=429, detail="AI quota exceeded. Please try again later or upgrade your Gemini API plan.")
        raise HTTPException(status_code=500, detail=str(e))



# health check
@app.get("/")
async def root():
    return {"message": "API is running! Use POST /generate to generate Postman collections."}


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
            llm_result = gemini_service.generate_test_cases_comprehensive(ticket_context, catalog)
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

