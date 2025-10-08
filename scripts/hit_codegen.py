import json
import sys
import http.client

def main():
    payload = {
        "ticket_key": "SCRUM-34",
        "override_description": (
            "Create two FastAPI endpoints: 1) POST /api/v1/notes to insert a note "
            "{\"title\": string 1..120, \"body\": string 1..5000} into MongoDB collection \"notes\" "
            "with indexes (unique [\"title\",\"created_at\"(day)], index on created_at desc) returning 201 with {id}. "
            "2) GET /api/v1/notes/{id} to fetch by ObjectId with 404 when missing. Use Pydantic models, robust validation, "
            "error handling for Mongo failures, and unit tests. Return JSON with language, files[], code[], tests[], notes[]."
        ),
        "context": {"language": "python", "framework": "fastapi"},
        "post_mode": "none",
        "update_jira_description": False,
    }

    conn = http.client.HTTPConnection("localhost", 8000)
    body = json.dumps(payload)
    headers = {"Content-Type": "application/json"}
    conn.request("POST", "/api/v1/codegen/jira/generate", body=body, headers=headers)
    resp = conn.getresponse()
    data = resp.read().decode("utf-8", errors="ignore")
    print("STATUS:", resp.status)
    print("BODY:")
    print(data)
    return 0 if 200 <= resp.status < 300 else 1

if __name__ == "__main__":
    sys.exit(main())



