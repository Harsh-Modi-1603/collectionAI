"""
jira_service.py — Fetches JIRA ticket data using a shared API token from .env
"""
import requests
import base64
from app import config


class JiraAuthError(Exception):
    pass


class JiraNotFoundError(Exception):
    pass


def _extract_description(fields: dict) -> str:
    desc = fields.get("description")
    if not desc:
        return ""
    if isinstance(desc, dict):
        texts = []
        def _walk(node):
            if isinstance(node, dict):
                if node.get("type") == "text":
                    texts.append(node.get("text", ""))
                for child in node.get("content", []):
                    _walk(child)
            elif isinstance(node, list):
                for item in node:
                    _walk(item)
        _walk(desc)
        return " ".join(texts).strip()
    return str(desc).strip()


def _get_auth_header() -> dict:
    """Build Basic Auth header using credentials from config."""
    if not config.JIRA_EMAIL or not config.JIRA_API_TOKEN:
        raise JiraAuthError("JIRA credentials not configured in .env")
    
    credentials = f"{config.JIRA_EMAIL}:{config.JIRA_API_TOKEN}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return {
        "Authorization": f"Basic {encoded}",
        "Accept": "application/json"
    }


def fetch_ticket(ticket_id: str) -> dict:
    """Fetch a single JIRA ticket using shared API token from .env"""
    url = f"{config.JIRA_BASE_URL}/rest/api/3/issue/{ticket_id}"
    resp = requests.get(
        url,
        headers=_get_auth_header(),
        params={"fields": "summary,description,subtasks"},
        timeout=30
    )
    
    if resp.status_code in (401, 403):
        raise JiraAuthError("JIRA authentication failed. Check API token in .env")
    if resp.status_code == 404:
        raise JiraNotFoundError(f"JIRA ticket '{ticket_id}' not found.")
    resp.raise_for_status()
    
    fields = resp.json().get("fields", {})
    return {
        "id": ticket_id,
        "summary": fields.get("summary", ""),
        "description": _extract_description(fields),
        "raw_subtasks": fields.get("subtasks", []),
    }


def fetch_ticket_with_subtasks(ticket_id: str) -> dict:
    """Fetch a JIRA ticket with all its subtasks using shared API token"""
    ticket = fetch_ticket(ticket_id)
    subtasks = []
    
    for sub in ticket.get("raw_subtasks", []):
        sub_id = sub.get("key") or sub.get("id")
        if not sub_id:
            continue
        try:
            url = f"{config.JIRA_BASE_URL}/rest/api/3/issue/{sub_id}"
            resp = requests.get(
                url,
                headers=_get_auth_header(),
                params={"fields": "summary,description"},
                timeout=30
            )
            if resp.status_code != 200:
                continue
            sub_fields = resp.json().get("fields", {})
            subtasks.append({
                "id": sub_id,
                "summary": sub_fields.get("summary", ""),
                "description": _extract_description(sub_fields),
            })
        except Exception:
            continue
    
    return {
        "id": ticket["id"],
        "summary": ticket["summary"],
        "description": ticket["description"],
        "subtasks": subtasks,
    }
