# app/services/gemini_service.py
import google.generativeai as genai
import os
import json
from dotenv import load_dotenv

load_dotenv()

def _configure_gemini():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GOOGLE_API_KEY. Please set it in your .env file.")
    genai.configure(api_key=api_key)

_configure_gemini()

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
        model = genai.GenerativeModel("gemini-2.5-flash") 
        response = model.generate_content(prompt)
        text = response.text.strip()

        # Extract JSON robustly — handles thinking tokens and markdown fences
        if "```" in text:
            parts = text.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                if part.startswith("{") or part.startswith("["):
                    text = part
                    break
        else:
            start = text.find("[") if "[" in text else text.find("{")
            if start != -1:
                text = text[start:]

        return json.loads(text)

    except Exception as e:
        print(f"❌ Error calling Gemini: {e}")
        return None


def _build_comprehensive_prompt(ticket_context: dict, catalog: dict | None) -> str:
    """Build the three-section prompt for comprehensive E2E flow generation."""

    # Section 1 — Role and rules
    section1 = """You are an expert QA engineer generating a Postman test suite for end-to-end API testing.

CRITICAL INSTRUCTIONS - READ CAREFULLY:

1. API CATALOG USAGE (HIGHEST PRIORITY):
   - The API Catalog below contains ALL available endpoints in the system
   - You MUST use ONLY endpoints that exist in the catalog
   - Search the catalog thoroughly for endpoints matching the feature domain
   - Match endpoints by path keywords (e.g., for "campaign" feature, look for paths containing /campaign, /campaigns)
   - Use the exact path, method, parameters, and request body schema from the catalog
   - If you cannot find a matching endpoint in the catalog, set "inferred": true and explain in warnings
   - NEVER invent endpoints that don't exist in the catalog unless absolutely necessary

2. E2E FLOW CONSTRUCTION:
   - Analyze the ticket to understand the complete user journey
   - Identify ALL API calls needed to complete the journey from start to finish
   - For each primary API call, identify prerequisites:
     * Authentication/authorization (login, token generation)
     * Entity lookups (get user ID, get organization ID, etc.)
     * Setup/creation of dependent resources
   - Order steps logically: prerequisites → primary actions → verification → teardown
   - Each step must have a clear purpose in the E2E flow

3. VARIABLE EXTRACTION & WIRING:
   - For each API response that produces data needed by later steps, add variable_extractions
   - Use JSON path notation: "$.data.id", "$.token", "$.items[0].id"
   - Reference extracted variables in subsequent steps using {{variableName}}
   - Common patterns:
     * Login → extract authToken → use in Authorization header
     * Create entity → extract entityId → use in GET/UPDATE/DELETE
     * List entities → extract first item ID → use for detail operations
   - IMPORTANT: Use ONLY pm.collectionVariables.set/get in test scripts, NEVER pm.environment

4. TEST COVERAGE:
   - For each primary endpoint, generate:
     * 1 positive case (valid data, expect 200/201)
     * 1 negative case (invalid/missing data, expect 400/401/404)
   - Keep the total number of steps reasonable (aim for 5-10 steps for a complete E2E flow)
   - Ensure request bodies match the schema from the API catalog
   - Include realistic test data appropriate for the domain

5. HIGH-LEVEL FEATURE STORIES:
   - If the ticket describes a feature (not a specific API), infer the complete CRUD flow
   - Search the catalog for all related endpoints (CREATE, READ, UPDATE, DELETE, LIST)
   - Generate a realistic user journey demonstrating the feature
   - Example: "Save Campaign as Template" → 
     * Login → Create Campaign → Save as Template → List Templates → Load Template → Delete Template
   - Use actual endpoints from the catalog for each step

6. OUTPUT FORMAT:
   - Always use {{baseUrl}} as the host variable
   - Group steps by role: "prerequisite", "primary", "teardown"
   - Include test_script for each step asserting expected status code
   - Set inferred: false for catalog endpoints, true for inferred ones
   - Add warnings for any assumptions or missing catalog endpoints"""

    # Section 2 — API Catalog
    if catalog and catalog.get("endpoints"):
        import json as _json
        
        # Group endpoints by path prefix for easier navigation
        endpoints_by_domain = {}
        for ep in catalog["endpoints"]:
            path = ep.get("path", "")
            # Extract domain from path (e.g., /api/campaigns/... → campaigns)
            parts = [p for p in path.split("/") if p and p != "api"]
            domain = parts[0] if parts else "other"
            if domain not in endpoints_by_domain:
                endpoints_by_domain[domain] = []
            endpoints_by_domain[domain].append(ep)
        
        # Build a structured catalog view
        catalog_lines = ["\nAPI CATALOG - Available Endpoints (USE THESE EXACTLY AS SHOWN):"]
        catalog_lines.append("=" * 80)
        
        for domain, endpoints in sorted(endpoints_by_domain.items()):
            catalog_lines.append(f"\n[{domain.upper()}] Domain:")
            for ep in endpoints:
                method = ep.get("method", "GET")
                path = ep.get("path", "")
                summary = ep.get("summary", "")
                catalog_lines.append(f"  {method:6} {path}")
                if summary:
                    catalog_lines.append(f"         Summary: {summary}")
                
                # Show request body schema if present
                req_body = ep.get("request_body")
                if req_body and isinstance(req_body, dict):
                    content = req_body.get("content", {})
                    json_schema = content.get("application/json", {}).get("schema", {})
                    if json_schema:
                        props = json_schema.get("properties", {})
                        required = json_schema.get("required", [])
                        if props:
                            catalog_lines.append(f"         Request Body:")
                            for prop_name, prop_schema in props.items():
                                prop_type = prop_schema.get("type", "any")
                                req_marker = " (required)" if prop_name in required else ""
                                catalog_lines.append(f"           - {prop_name}: {prop_type}{req_marker}")
                
                # Show parameters if present
                params = ep.get("parameters", [])
                if params:
                    catalog_lines.append(f"         Parameters:")
                    for param in params:
                        if isinstance(param, dict):
                            param_name = param.get("name", "")
                            param_in = param.get("in", "")
                            param_required = " (required)" if param.get("required") else ""
                            catalog_lines.append(f"           - {param_name} ({param_in}){param_required}")
        
        catalog_lines.append("\n" + "=" * 80)
        catalog_text = "\n".join(catalog_lines)
        
        # Truncate if too long (keep within token limits)
        if len(catalog_text) > 12000:
            catalog_text = catalog_text[:12000] + "\n... (catalog truncated, showing first 12000 chars)"
        
        section2 = catalog_text
    else:
        section2 = "\nNo API catalog available — you must infer endpoints from ticket context."

    # Section 3 — Ticket context (subtasks first, then parent, per Req 6.8)
    ticket_id = ticket_context.get("id", "UNKNOWN")
    summary = ticket_context.get("summary", "")
    description = ticket_context.get("description", "")
    subtasks = ticket_context.get("subtasks", [])

    subtask_lines = ""
    if subtasks:
        lines = []
        for sub in subtasks:
            lines.append(
                f"  - {sub.get('id', '')}: {sub.get('summary', '')} — {sub.get('description', '')}"
            )
        subtask_lines = "\nSubtasks (higher-priority context — use explicit API details from here first):\n" + "\n".join(lines)

    section3 = f"""
Ticket: {ticket_id}
Summary: {summary}{subtask_lines}

Parent Description:
{description}"""

    # Output format instruction with examples
    output_format = """
EXAMPLE E2E FLOW STRUCTURE:

Step 1 (prerequisite): POST /auth/login
  → Extract authToken from response
  → Use in all subsequent requests

Step 2 (prerequisite): GET /users/me
  → Extract userId from response
  → Use in campaign creation

Step 3 (primary): POST /campaigns
  → Use {{authToken}} in Authorization header
  → Use {{userId}} in request body
  → Extract campaignId from response

Step 4 (primary): GET /campaigns/{{campaignId}}
  → Verify campaign was created

Step 5 (negative): POST /campaigns with missing required field
  → Expect 400 Bad Request

Step 6 (teardown): DELETE /campaigns/{{campaignId}}
  → Clean up test data

REQUIRED OUTPUT FORMAT (JSON only, no markdown, no explanation):
{
  "flow_steps": [
    {
      "step": 1,
      "id": "unique_step_id",
      "title": "Descriptive title of what this step does",
      "role": "prerequisite" | "primary" | "teardown",
      "type": "positive" | "negative" | "edge",
      "method": "GET" | "POST" | "PUT" | "PATCH" | "DELETE",
      "endpoint": "/exact/path/from/catalog",
      "request_body": {"field": "value"} | null,
      "expected_status": 200,
      "inferred": false,
      "variable_extractions": [
        {"variable": "variableName", "json_path": "$.path.to.value"}
      ],
      "variable_usages": ["variableName"],
      "test_script": "pm.test('Status is 200', () => { pm.response.to.have.status(200); pm.collectionVariables.set('variableName', pm.response.json().path.to.value); });"
    }
  ],
  "warnings": ["Any assumptions or issues"]
}

NOW GENERATE THE E2E FLOW:"""

    return section1 + section2 + section3 + output_format


def generate_test_cases_comprehensive(ticket_context: dict, catalog: dict | None) -> dict:
    """
    Generate a comprehensive E2E flow with positive, negative, and edge case test steps.
    Returns {"flow_steps": [...], "warnings": [...]}
    Retries once on JSON parse failure; returns warning if still unparseable.
    """
    ticket_id = ticket_context.get("id", "UNKNOWN")
    prompt = _build_comprehensive_prompt(ticket_context, catalog)

    def _call_gemini() -> str:
        # Use gemini-2.5-flash (available and reliable)
        model = genai.GenerativeModel("gemini-2.5-flash")
        # Increase max output tokens to allow longer responses
        generation_config = genai.types.GenerationConfig(
            max_output_tokens=8192,
            temperature=0.7,
        )
        response = model.generate_content(prompt, generation_config=generation_config)
        text = response.text.strip()
        return text

    def _extract_json(text: str) -> str:
        """Extract the first valid JSON object from text, handling thinking tokens and markdown."""
        text = text.strip()
        
        # Handle markdown code fences
        if "```json" in text.lower():
            # Find the json block
            start_marker = text.lower().find("```json")
            if start_marker != -1:
                start = start_marker + 7  # len("```json")
                end_marker = text.find("```", start)
                if end_marker != -1:
                    text = text[start:end_marker].strip()
        elif text.startswith("```"):
            # Generic code fence
            text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
        
        # Remove any leading text before the JSON starts
        json_start = -1
        for i, char in enumerate(text):
            if char in ['{', '[']:
                json_start = i
                break
        
        if json_start > 0:
            text = text[json_start:]
        
        # Try to find the complete JSON object/array
        if text.startswith('{'):
            depth = 0
            in_string = False
            escape_next = False
            
            for i, ch in enumerate(text):
                if escape_next:
                    escape_next = False
                    continue
                if ch == '\\':
                    escape_next = True
                    continue
                if ch == '"' and not escape_next:
                    in_string = not in_string
                if not in_string:
                    if ch == '{':
                        depth += 1
                    elif ch == '}':
                        depth -= 1
                        if depth == 0:
                            return text[:i+1]
        elif text.startswith('['):
            depth = 0
            in_string = False
            escape_next = False
            
            for i, ch in enumerate(text):
                if escape_next:
                    escape_next = False
                    continue
                if ch == '\\':
                    escape_next = True
                    continue
                if ch == '"' and not escape_next:
                    in_string = not in_string
                if not in_string:
                    if ch == '[':
                        depth += 1
                    elif ch == ']':
                        depth -= 1
                        if depth == 0:
                            return text[:i+1]
        
        return text

    def _parse(text: str) -> dict | None:
        try:
            extracted = _extract_json(text)
            result = json.loads(extracted)
            return result
        except (json.JSONDecodeError, ValueError) as e:
            # Check if response was truncated
            if text and not (text.rstrip().endswith('}') or text.rstrip().endswith(']')):
                print(f"[DEBUG] Response appears truncated (doesn't end with }} or ])")
            print(f"[DEBUG] JSON parse error: {e}")
            return None

    try:
        text = _call_gemini()
        # Debug: log raw response for troubleshooting
        print(f"\n{'='*80}")
        print(f"[DEBUG] Raw LLM response for {ticket_id} (length: {len(text)} chars)")
        print(f"{'='*80}")
        print(text[:2000] if len(text) > 2000 else text)
        if len(text) > 2000:
            print(f"\n... (middle content omitted)")
            print(text[-500:])  # Show the end to see if it's complete
        print(f"{'='*80}\n")
        
        result = _parse(text)
        if result is None:
            # Retry once
            print(f"[DEBUG] First parse failed, retrying...")
            text = _call_gemini()
            print(f"[DEBUG] Retry response length: {len(text)} chars")
            print(f"[DEBUG] Retry response (first 1000 chars): {text[:1000]}")
            print(f"[DEBUG] Retry response (last 500 chars): {text[-500:]}")
            result = _parse(text)
        if result is None:
            print(f"[DEBUG] Second parse also failed.")
            extracted = _extract_json(text)
            print(f"[DEBUG] Extracted JSON length: {len(extracted)} chars")
            print(f"[DEBUG] Extracted JSON (first 500): {extracted[:500]}")
            print(f"[DEBUG] Extracted JSON (last 200): {extracted[-200:]}")
            return {
                "flow_steps": [],
                "warnings": [f"{ticket_id}: LLM returned unparseable JSON"],
            }
        # Ensure required keys exist
        result.setdefault("flow_steps", [])
        result.setdefault("warnings", [])
        print(f"[DEBUG] Successfully parsed {len(result.get('flow_steps', []))} flow steps")
        return result
    except Exception as e:
        print(f"[DEBUG] Exception during LLM call: {e}")
        import traceback
        traceback.print_exc()
        return {
            "flow_steps": [],
            "warnings": [f"{ticket_id}: LLM call failed — {e}"],
        }
