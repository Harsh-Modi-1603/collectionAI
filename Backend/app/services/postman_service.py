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
