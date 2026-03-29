# app/services/groq_service.py
import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

def _get_groq_client():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GROQ_API_KEY. Please set it in your .env file.")
    return Groq(api_key=api_key)


def _build_comprehensive_prompt(ticket_context: dict, catalog: dict | None) -> str:
    """Build the three-section prompt for comprehensive E2E flow generation."""

    # Section 1 — Role and rules
    section1 = """You are an expert QA engineer generating a Postman test suite for end-to-end API testing.

🔥 CRITICAL PRIORITY ORDER (FOLLOW THIS EXACTLY):

PRIORITY 1 - JIRA COMMENTS (ABSOLUTE HIGHEST PRIORITY):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ JIRA comments are THE MOST RELIABLE source - they contain ACTUAL dev testing data
✅ Look for cURL commands, endpoints, request/response examples in comments
✅ If you find a cURL command, EXTRACT everything from it:
   - HTTP method (GET, POST, PUT, DELETE, etc.)
   - Full endpoint path (e.g., /api/v3/cmp/template)
   - Headers (Authorization, Content-Type, etc.)
   - Request body (JSON payload)
   - Any path/query parameters

Example cURL extraction:
```
curl -X POST https://api.example.com/api/v3/cmp/template \
  -H "Authorization: Bearer {{token}}" \
  -H "Content-Type: application/json" \
  -d '{"name":"My Template","description":"Test"}'
```
→ Extract: POST /api/v3/cmp/template, Authorization header, Content-Type header, request body

✅ If comments show response examples, use them to understand the response schema
✅ If comments mention "Dev Testing", "Test Case", "cURL", use that info FIRST
✅ For endpoints found in comments: set "inferred": false, NO warnings needed
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PRIORITY 2 - API CATALOG (SECONDARY SOURCE):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Use the API catalog ONLY if endpoints are NOT in comments
- Search catalog for endpoints matching the feature domain
- Use exact path, method, parameters from catalog
- For catalog endpoints: set "inferred": false, NO warnings needed
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PRIORITY 3 - COMMON PREREQUISITE ENDPOINTS (NO WARNINGS NEEDED):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
These are standard endpoints that exist in almost all APIs - use them without warnings:
- POST /auth/login (authentication)
- POST /auth/token (token generation)
- GET /users/me (current user info)
- GET /user/profile (user profile)
- POST /auth/refresh (token refresh)

For these common endpoints: set "inferred": false, NO warnings needed
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PRIORITY 4 - TICKET DESCRIPTION (TERTIARY SOURCE):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Use ticket description ONLY if endpoints are NOT in comments or catalog
- Look for endpoint mentions, API paths, or technical details
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PRIORITY 5 - LOGICAL REST PATTERNS (NO WARNINGS NEEDED):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
If you find a CREATE endpoint in catalog/comments, the following are LOGICAL patterns:
- POST /api/v3/resource → GET /api/v3/resource/{{id}} (read by ID)
- POST /api/v3/resource → PUT /api/v3/resource/{{id}} (update by ID)
- POST /api/v3/resource → DELETE /api/v3/resource/{{id}} (delete by ID)
- POST /api/v3/resource → GET /api/v3/resource (list all)

Example: If catalog has POST /api/v3/cmp/template:
✅ GET /api/v3/cmp/template/{{templateId}} → inferred: false, NO warning (logical REST)
✅ DELETE /api/v3/cmp/template/{{templateId}} → inferred: false, NO warning (logical REST)
✅ PUT /api/v3/cmp/template/{{templateId}} → inferred: false, NO warning (logical REST)

These are STANDARD REST patterns - do NOT mark as inferred, do NOT add warnings
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PRIORITY 6 - COMPREHENSIVE TEST COVERAGE:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Generate DETAILED test cases for each endpoint (aim for 15-25 tests per feature):

1. POSITIVE (3-5 tests): happy path, optional fields, min/max values
2. NEGATIVE - MISSING FIELDS (test 3-5 KEY required fields, not every field)
3. NEGATIVE - INVALID TYPES (test 3-5 KEY fields): string→number, etc.
4. NEGATIVE - INVALID VALUES: empty, null, too long, out of range
5. EDGE CASES: boundary values, unicode, duplicates
6. SECURITY: no auth (401), invalid auth (401), unauthorized (403)
7. CRUD: GET by ID, list, update (PUT/PATCH), delete

⚠️  For large request bodies: Focus on KEY/REQUIRED fields only, not every field!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PRIORITY 7 - INFERENCE (LAST RESORT):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- ONLY infer endpoints if NOT in comments, catalog, common list, OR logical REST pattern
- For truly inferred endpoints: set "inferred": true, ADD warning
- Example of truly inferred: POST /api/v3/unknown/endpoint (not in catalog, not REST pattern)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CRITICAL RULES:
1. ALWAYS check comments FIRST before checking catalog
2. If endpoint is in comments → use it, set inferred=false, NO warning
3. If endpoint is in catalog → use it, set inferred=false, NO warning
4. If endpoint is a common prerequisite → use it, set inferred=false, NO warning
5. If endpoint is a logical REST pattern → use it, set inferred=false, NO warning
6. ONLY add warnings for endpoints that are truly unknown (not in any of the above)
7. Use ONLY pm.collectionVariables.set/get in test scripts, NEVER pm.environment
8. Always use {{baseUrl}} as the host variable
9. Extract variables from responses and wire them to subsequent requests
10. 🔥 GENERATE COMPREHENSIVE TEST COVERAGE - aim for 20-40 test cases, not 5-10!
11. 🔥 Test EACH validation rule separately - one test per field validation
12. 🔥 Include positive, negative, edge, and security test cases"""

    # Section 2 — API Catalog (CONCISE to stay within token limits)
    if catalog and catalog.get("endpoints"):
        # Group endpoints by path prefix
        endpoints_by_domain = {}
        for ep in catalog["endpoints"]:
            path = ep.get("path", "")
            parts = [p for p in path.split("/") if p and p != "api"]
            domain = parts[0] if parts else "other"
            if domain not in endpoints_by_domain:
                endpoints_by_domain[domain] = []
            endpoints_by_domain[domain].append(ep)
        
        # Build MINIMAL catalog (only method + path, no schemas)
        catalog_lines = ["\nAPI CATALOG:"]
        catalog_lines.append("=" * 50)
        
        for domain, endpoints in sorted(endpoints_by_domain.items()):
            catalog_lines.append(f"\n[{domain.upper()}]:")
            # Limit to first 5 endpoints per domain
            for ep in endpoints[:5]:
                method = ep.get("method", "GET")
                path = ep.get("path", "")
                catalog_lines.append(f"  {method:6} {path}")
            
            if len(endpoints) > 5:
                catalog_lines.append(f"  ... +{len(endpoints) - 5} more")
        
        catalog_lines.append("=" * 50)
        catalog_text = "\n".join(catalog_lines)
        
        # Final safety truncation
        if len(catalog_text) > 3000:
            catalog_text = catalog_text[:3000] + "\n... (truncated)"
        
        section2 = catalog_text
    else:
        section2 = "\nNo API catalog."

    # Section 3 — Ticket context (comments FIRST and MOST PROMINENT)
    ticket_id = ticket_context.get("id", "UNKNOWN")
    summary = ticket_context.get("summary", "")
    description = ticket_context.get("description", "")
    subtasks = ticket_context.get("subtasks", [])
    comments = ticket_context.get("comments", [])

    # Aggressive truncation for large descriptions (to stay within token limits)
    # For tickets with very large request bodies, we need to be more aggressive
    if len(description) > 1500:
        description = description[:1500] + "\n... (description truncated for brevity)"

    # Comments section (ABSOLUTE HIGHEST PRIORITY)
    comments_section = ""
    if comments:
        lines = ["\n" + "=" * 60]
        lines.append("🔥 JIRA COMMENTS - READ THIS FIRST 🔥")
        lines.append("=" * 60)
        lines.append("⚠️  Extract endpoints from cURL commands in comments")
        lines.append("=" * 60)
        
        for idx, comment in enumerate(comments[:3], 1):  # Limit to first 3 comments
            author = comment.get("author", "Unknown")
            body = comment.get("body", "")
            
            # Aggressive truncation for long comments (especially cURL with large bodies)
            if len(body) > 400:
                body = body[:400] + "... (truncated)"
            
            lines.append(f"\n📝 Comment #{idx} by {author}:")
            lines.append("-" * 60)
            
            # Highlight cURL commands
            if "curl" in body.lower():
                lines.append("🔥 CONTAINS cURL - EXTRACT ENDPOINT!")
            
            lines.append(body)
            lines.append("-" * 60)
        
        if len(comments) > 3:
            lines.append(f"\n... and {len(comments) - 3} more comments")
        
        lines.append("\n" + "=" * 60)
        comments_section = "\n".join(lines)

    subtask_lines = ""
    if subtasks:
        lines = ["\nSubtasks:"]
        for sub in subtasks[:3]:  # Limit to first 3 subtasks
            sub_desc = sub.get('description', '')
            if len(sub_desc) > 200:
                sub_desc = sub_desc[:200] + "..."
            lines.append(
                f"  - {sub.get('id', '')}: {sub.get('summary', '')} — {sub_desc}"
            )
        if len(subtasks) > 3:
            lines.append(f"  ... and {len(subtasks) - 3} more subtasks")
        subtask_lines = "\n".join(lines)

    section3 = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TICKET INFORMATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Ticket ID: {ticket_id}
Summary: {summary}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{comments_section}{subtask_lines}

Ticket Description:
{description}"""

    # Output format instruction with examples
    output_format = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXAMPLE: COMPREHENSIVE TEST COVERAGE (20-40 tests per feature)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

For POST /api/v3/cmp/template, generate:

POSITIVE (5-7 tests): happy path, optional fields, min/max values, special chars
NEGATIVE - MISSING FIELDS (1 test per required field): templateName, templateTypeId, etc.
NEGATIVE - INVALID TYPES (1 test per field): string→number, number→string, etc.
NEGATIVE - INVALID VALUES: empty, null, too long, out of range, invalid enum
EDGE CASES: boundary values, empty arrays, unicode, duplicates
SECURITY: no auth (401), invalid auth (401), unauthorized (403)
READ: GET by ID (200), invalid ID (404), no auth (401), list all, pagination
UPDATE: PUT full (200), PATCH partial (200), invalid ID (404), no auth (401)
DELETE: valid (200), invalid ID (404), no auth (401)

TOTAL: 30-40 comprehensive tests for ONE feature!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHEN TO SET "inferred" AND ADD WARNINGS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ Endpoint found in JIRA comments (cURL, dev testing):
   → inferred: false
   → NO warning needed

✅ Endpoint found in API catalog:
   → inferred: false
   → NO warning needed

✅ Common prerequisite endpoint (/auth/login, /users/me, etc.):
   → inferred: false
   → NO warning needed

✅ Logical REST endpoint derived from catalog endpoint:
   Example: Catalog has POST /api/v3/cmp/template
   → GET /api/v3/cmp/template/{{id}} is a STANDARD REST pattern (read by ID)
   → DELETE /api/v3/cmp/template/{{id}} is a STANDARD REST pattern (delete by ID)
   → PUT /api/v3/cmp/template/{{id}} is a STANDARD REST pattern (update by ID)
   → inferred: false for ALL of these
   → NO warnings needed

✅ Negative test cases using same endpoint:
   Example: Catalog has POST /api/v3/cmp/template
   → POST /api/v3/cmp/template with missing fields is a NEGATIVE TEST
   → Same endpoint, just testing error cases
   → inferred: false
   → NO warning needed

❌ Endpoint NOT in comments, NOT in catalog, NOT common, NOT logical REST:
   Example: POST /api/v3/unknown/resource (not in catalog, not derived from anything)
   → inferred: true
   → ADD warning: "Endpoint /api/v3/unknown/resource is inferred as it was not found in JIRA comments or API catalog"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REQUIRED OUTPUT FORMAT (JSON only, no markdown, no explanation)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CRITICAL INSTRUCTIONS:
1. Output ONLY raw JSON - NO markdown code blocks (```json), NO explanations
2. Start your response with { and end with }
3. Do NOT add any text before or after the JSON
4. Ensure all JSON is valid and properly closed

EXACT FORMAT:
{
  "flow_steps": [
    {
      "step": 1,
      "id": "unique_step_id",
      "title": "Descriptive title of what this step does",
      "role": "prerequisite" | "primary" | "teardown",
      "type": "positive" | "negative" | "edge",
      "method": "GET" | "POST" | "PUT" | "PATCH" | "DELETE",
      "endpoint": "/exact/path/from/comments/or/catalog",
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
  "warnings": []
}

NOW GENERATE THE E2E FLOW (JSON ONLY, NO MARKDOWN):"""

    return section1 + section2 + section3 + output_format


def generate_test_cases_comprehensive(ticket_context: dict, catalog: dict | None) -> dict:
    """
    Generate a comprehensive E2E flow with positive, negative, and edge case test steps using Groq.
    Returns {"flow_steps": [...], "warnings": [...]}
    Retries once on JSON parse failure; returns warning if still unparseable.
    """
    ticket_id = ticket_context.get("id", "UNKNOWN")
    prompt = _build_comprehensive_prompt(ticket_context, catalog)

    def _call_groq() -> str:
        client = _get_groq_client()
        # Use llama-3.3-70b-versatile (free model with 32K token limit for large prompts)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert QA engineer. Generate COMPREHENSIVE Postman test suites with EXTENSIVE coverage (MINIMUM 15-25 tests per feature). CRITICAL: For large request bodies, test KEY/REQUIRED fields only (3-5 fields), not every field. Include: 3-5 positive tests, 8-12 negative tests (missing fields, invalid types, invalid values), 2-3 edge cases, 2-3 security tests. Check JIRA comments FIRST for cURL. Set inferred=false for comments/catalog/common/REST patterns. CRITICAL: Respond ONLY with raw JSON - NO markdown, NO code blocks, NO explanations, NO text before or after. Start with { and end with }."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3,  # Lower temperature for more consistent, valid JSON output
            max_tokens=16000,  # Increased for llama-3.3-70b-versatile (supports up to 32K)
        )
        text = response.choices[0].message.content.strip()
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
            
            # Try aggressive JSON repair
            try:
                # Remove markdown code blocks
                cleaned = text.replace('```json', '').replace('```', '').strip()
                
                # Try to find JSON object or array
                start_obj = cleaned.find('{')
                start_arr = cleaned.find('[')
                
                if start_obj != -1 and (start_arr == -1 or start_obj < start_arr):
                    # Try to extract from first { to last }
                    end = cleaned.rfind('}')
                    if end != -1:
                        json_str = cleaned[start_obj:end+1]
                        result = json.loads(json_str)
                        print(f"[DEBUG] JSON repair successful (object extraction)")
                        return result
                elif start_arr != -1:
                    # Try to extract from first [ to last ]
                    end = cleaned.rfind(']')
                    if end != -1:
                        json_str = cleaned[start_arr:end+1]
                        result = json.loads(json_str)
                        print(f"[DEBUG] JSON repair successful (array extraction)")
                        return result
            except Exception as repair_error:
                print(f"[DEBUG] JSON repair also failed: {repair_error}")
            
            return None

    try:
        text = _call_groq()
        # Debug: log raw response for troubleshooting
        print(f"\n{'='*80}")
        print(f"[DEBUG] Raw Groq response for {ticket_id} (length: {len(text)} chars)")
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
            text = _call_groq()
            print(f"[DEBUG] Retry response length: {len(text)} chars")
            result = _parse(text)
        if result is None:
            print(f"[DEBUG] Second parse also failed.")
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
        print(f"[DEBUG] Exception during Groq call: {e}")
        import traceback
        traceback.print_exc()
        return {
            "flow_steps": [],
            "warnings": [f"{ticket_id}: LLM call failed — {e}"],
        }
