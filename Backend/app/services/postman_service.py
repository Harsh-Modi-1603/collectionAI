# app/services/postman_service.py
import json

def create_postman_collection(ticket: dict, test_cases: list):
    collection = {
        "info": {
            "name": f"API Tests - {ticket.get('summary', 'Ticket')}",
            "_postman_id": "auto-generated",
            "description": ticket.get("description", ""),
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
        },
        "item": []
    }

    for tc in test_cases:
        method = tc.get("method", "GET")
        endpoint = tc.get("endpoint", "/")
        test_item = {
            "name": tc.get("title", "Test Case"),
            "request": {
                "method": method,
                "header": [{"key": "Content-Type", "value": "application/json"}],
                "url": {
                    "raw": f"https://api.example.com{endpoint}",
                    "protocol": "https",
                    "host": ["api", "example", "com"],
                    "path": endpoint.strip("/").split("/")
                },
                "body": {
                    "mode": "raw",
                    "raw": json.dumps({"example": "data"})
                } if method.upper() != "GET" else None
            },
            "event": [
                {
                    "listen": "test",
                    "script": {
                        "type": "text/javascript",
                        "exec": [
                            f"pm.test('Status code is 2xx for {tc.get('title')}', function () {{",
                            "    pm.response.to.be.success;",
                            "});"
                        ]
                    }
                }
            ]
        }
        collection["item"].append(test_item)

    return collection


def _build_url(endpoint: str) -> dict:
    """Build a Postman URL object using {{baseUrl}} as the host."""
    raw = f"{{{{baseUrl}}}}{endpoint}"
    # Strip leading slash for path segments
    path_str = endpoint.lstrip("/")
    path_segments = path_str.split("/") if path_str else []
    return {
        "raw": raw,
        "host": ["{{baseUrl}}"],
        "path": path_segments,
    }


def _build_test_script(step: dict) -> list[str]:
    """
    Build the exec lines for a Postman test event script.
    Includes status assertion + pm.collectionVariables.set calls for variable extractions.
    """
    expected_status = step.get("expected_status", 200)
    title = step.get("title", "Test")
    lines = [
        f"pm.test('Status is {expected_status} — {title}', function () {{",
        f"    pm.response.to.have.status({expected_status});",
        "});",
    ]

    # Append any custom test_script content from the LLM (if different from above)
    llm_script = step.get("test_script", "").strip()
    if llm_script and f"have.status({expected_status})" not in llm_script:
        # Replace pm.environment with pm.collectionVariables
        llm_script = llm_script.replace("pm.environment.set", "pm.collectionVariables.set")
        llm_script = llm_script.replace("pm.environment.get", "pm.collectionVariables.get")
        lines.append(llm_script)

    # Variable extractions: pm.collectionVariables.set(name, jsonpath value)
    for extraction in step.get("variable_extractions", []):
        var_name = extraction.get("variable", "")
        json_path = extraction.get("json_path", "")
        if var_name and json_path:
            # Convert simple $.field to pm.response.json().field
            field = json_path.lstrip("$").lstrip(".")
            if field:
                lines.append(
                    f"pm.collectionVariables.set('{var_name}', pm.response.json().{field});"
                )
            else:
                lines.append(
                    f"pm.collectionVariables.set('{var_name}', pm.response.json());"
                )

    return lines


def _build_postman_item(step: dict) -> dict:
    """Convert a single flow_step dict into a Postman request item."""
    method = step.get("method", "GET").upper()
    endpoint = step.get("endpoint", "/")
    title = step.get("title", "Request")
    inferred = step.get("inferred", False)

    name = f"[Inferred] {title}" if inferred else title

    item: dict = {
        "name": name,
        "request": {
            "method": method,
            "header": [{"key": "Content-Type", "value": "application/json"}],
            "url": _build_url(endpoint),
        },
        "event": [
            {
                "listen": "test",
                "script": {
                    "type": "text/javascript",
                    "exec": _build_test_script(step),
                },
            }
        ],
    }

    # Add description note for inferred items
    if inferred:
        item["request"]["description"] = (
            "Endpoint not found in API Catalog — verify before running."
        )

    # Add request body for non-GET methods
    if method != "GET":
        request_body = step.get("request_body")
        if request_body:
            item["request"]["body"] = {
                "mode": "raw",
                "raw": json.dumps(request_body, indent=2),
            }
        else:
            item["request"]["body"] = {
                "mode": "raw",
                "raw": json.dumps({"example": "data"}),
            }

    return item


def build_test_suite(ticket_context: dict, flow_steps: list) -> dict:
    """
    Build a single Postman folder for one ticket from an ordered flow_steps list.
    Steps are sorted by ascending `step` number.
    Prerequisite steps appear before primary steps (enforced by step ordering from LLM).
    Returns: {"name": "<ticket_id> — <summary>", "item": [...]}
    """
    ticket_id = ticket_context.get("id", "TICKET")
    summary = ticket_context.get("summary", "")
    folder_name = f"{ticket_id} — {summary}" if summary else ticket_id

    # Sort by step number, then by role priority (prerequisite < primary < teardown)
    role_order = {"prerequisite": 0, "primary": 1, "teardown": 2}
    sorted_steps = sorted(
        flow_steps,
        key=lambda s: (s.get("step", 999), role_order.get(s.get("role", "primary"), 1)),
    )

    items = [_build_postman_item(step) for step in sorted_steps]

    return {"name": folder_name, "item": items}


def assemble_collection(suites: list[dict], collection_name: str | None, ticket_ids: list[str]) -> dict:
    """
    Merge multiple test suite folders into ONE unified collection.
    All requests from all tickets are merged into a single flat list (no folders per ticket).
    """
    name = collection_name if collection_name else (ticket_ids[0] if ticket_ids else "Collection")
    description = f"Generated from tickets: {', '.join(ticket_ids)}"

    # Merge all items from all suites into a single flat list
    all_items = []
    for suite in suites:
        items = suite.get("item", [])
        all_items.extend(items)

    return {
        "info": {
            "name": name,
            "description": description,
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "item": all_items,  # Flat list of all requests, no folders
    }
