# Jules API Reference

> Official API documentation for Google Jules (AI coding agent)
>
> **Source:** https://developers.google.com/jules/api/reference/rest
>
> **Last Updated:** 2026-01-28

---

## Overview

The Jules API allows programmatic interaction with Google's AI coding agent. Jules can analyze codebases, generate code, create pull requests, and execute development tasks autonomously.

**Base URL:** `https://jules.googleapis.com/v1alpha`

**Authentication:** API Key via `X-Goog-Api-Key` header

---

## Session Resource

A session represents "a contiguous amount of work within the same context" - a complete unit of work in Jules.

### Session Object

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Output only | Full resource identifier (format: `sessions/{session}`) |
| `id` | string | Output only | Session identifier matching the resource name suffix |
| `prompt` | string | **Required** | Initial prompt text describing the task |
| `sourceContext` | SourceContext | **Required** | Source specification with repository context |
| `title` | string | Optional | Session title; auto-generated if omitted |
| `requirePlanApproval` | boolean | Optional | When true, plans require explicit approval before execution |
| `automationMode` | AutomationMode | Optional | Automation level; defaults to `AUTOMATION_MODE_UNSPECIFIED` |
| `createTime` | Timestamp | Output only | RFC 3339 formatted creation timestamp |
| `updateTime` | Timestamp | Output only | RFC 3339 formatted last modification timestamp |
| `state` | State | Output only | Current session status |
| `url` | string | Output only | Web app URL for viewing the session |
| `outputs` | SessionOutput[] | Output only | Generated session results (PRs, etc.) |

### SourceContext Object

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `source` | string | **Required** | Source name reference (format: `sources/github/{owner}/{repo}`) |
| `githubRepoContext` | GitHubRepoContext | Optional | GitHub-specific configuration |

### GitHubRepoContext Object

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `startingBranch` | string | **Required** | Branch name to initialize session from |

### SessionOutput Object

| Field | Type | Description |
|-------|------|-------------|
| `pullRequest` | PullRequest | Generated pull request details |

### PullRequest Object

| Field | Type | Description |
|-------|------|-------------|
| `url` | string | Pull request URL |
| `title` | string | Pull request title |
| `description` | string | Pull request description |

---

## Enumerations

### State Enum

Session lifecycle states:

| State | Description |
|-------|-------------|
| `STATE_UNSPECIFIED` | The state is unspecified |
| `QUEUED` | The session is queued (waiting to start) |
| `PLANNING` | The agent is planning (analyzing task) |
| `AWAITING_PLAN_APPROVAL` | The agent is waiting for plan approval |
| `AWAITING_USER_FEEDBACK` | The agent is waiting for user feedback |
| `IN_PROGRESS` | The session is in progress (actively working) |
| `PAUSED` | The session is paused |
| `FAILED` | The session has failed |
| `COMPLETED` | The session has completed successfully |

### State Diagram

```
                    ┌──────────────┐
                    │   QUEUED     │ Session created, waiting to start
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │   PLANNING   │ Agent analyzing the task
                    └──────┬───────┘
                           │
              ┌────────────┴────────────┐
              │                         │
              ▼                         ▼
┌─────────────────────────┐   ┌─────────────────────────┐
│ AWAITING_PLAN_APPROVAL  │   │      IN_PROGRESS        │
│   (if approval needed)  │   │  (auto-approved path)   │
└───────────┬─────────────┘   └───────────┬─────────────┘
            │                             │
            └─────────────┬───────────────┘
                          │
              ┌───────────┴───────────┐
              │                       │
              ▼                       ▼
┌─────────────────────────┐   ┌──────────────┐
│ AWAITING_USER_FEEDBACK  │   │   PAUSED     │
│   (needs clarification) │   │              │
└───────────┬─────────────┘   └──────┬───────┘
            │                        │
            └─────────────┬──────────┘
                          │
              ┌───────────┴───────────┐
              │                       │
              ▼                       ▼
        ┌──────────┐           ┌──────────┐
        │ COMPLETED│           │  FAILED  │
        └──────────┘           └──────────┘
```

### AutomationMode Enum

| Mode | Description |
|------|-------------|
| `AUTOMATION_MODE_UNSPECIFIED` | No automation (default) - manual mode |
| `MANUAL` | Same as unspecified - no automatic actions |
| `AUTO_CREATE_PR` | Automatically generate branches and pull requests |

---

## Endpoints

### sessions.create

Creates a new Jules session.

**HTTP Request:**
```
POST https://jules.googleapis.com/v1alpha/sessions
```

**Headers:**
```
Content-Type: application/json
X-Goog-Api-Key: {API_KEY}
```

**Request Body:**
```json
{
  "prompt": "Fix the bug in authentication module",
  "sourceContext": {
    "source": "sources/github/owner/repo",
    "githubRepoContext": {
      "startingBranch": "main"
    }
  },
  "title": "Fix auth bug",
  "automationMode": "AUTO_CREATE_PR",
  "requirePlanApproval": false
}
```

**Response:** Returns the created `Session` object.

---

### sessions.get

Retrieves a single session by ID.

**HTTP Request:**
```
GET https://jules.googleapis.com/v1alpha/sessions/{session_id}
```

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | Yes | Session identifier |

**Response:** Returns the `Session` object.

---

### sessions.list

Lists all sessions.

**HTTP Request:**
```
GET https://jules.googleapis.com/v1alpha/sessions
```

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `pageSize` | integer | 30 | Number of sessions to return (1-100) |
| `pageToken` | string | - | Pagination token from previous response |

**Response:**
```json
{
  "sessions": [
    { /* Session object */ }
  ],
  "nextPageToken": "token_for_next_page"
}
```

---

### sessions.sendMessage

Sends a message to an active session (for user feedback or clarification).

**HTTP Request:**
```
POST https://jules.googleapis.com/v1alpha/sessions/{session_id}:sendMessage
```

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | Yes | Session identifier |

**Request Body:**
```json
{
  "prompt": "Yes, please proceed with the suggested approach"
}
```

**Response:** Empty body on success.

---

### sessions.approvePlan

Approves a pending plan in a session (when `requirePlanApproval` is true).

**HTTP Request:**
```
POST https://jules.googleapis.com/v1alpha/sessions/{session_id}:approvePlan
```

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | Yes | Session identifier |

**Request Body:** Empty.

**Response:** Empty body on success.

---

## Activity Resource

Activities represent discrete units of work performed during a session.

### Activity Object

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Full resource identifier (`sessions/{session}/activities/{activity}`) |
| `id` | string | Unique activity identifier within session |
| `description` | string | Human-readable activity summary |
| `createTime` | Timestamp | RFC 3339 formatted creation timestamp |
| `originator` | string | Source entity: `"user"`, `"agent"`, or `"system"` |
| `artifacts` | Artifact[] | Array of outputs produced by the activity |

### Activity Types (Union Field)

| Type | Description |
|------|-------------|
| `agentMessaged` | Agent-posted communication |
| `userMessaged` | User-posted communication |
| `planGenerated` | Plan creation event |
| `planApproved` | Plan approval confirmation |
| `progressUpdated` | Work progress notification |
| `sessionCompleted` | Session finished successfully |
| `sessionFailed` | Session encountered failure |

### Artifact Types

| Type | Description |
|------|-------------|
| `changeSet` | Code modifications (Git patches) |
| `media` | Generated files (images, videos) |
| `bashOutput` | Command execution results |
| `text` | Text content/messages |

---

### activities.list

Lists all activities within a session.

**HTTP Request:**
```
GET https://jules.googleapis.com/v1alpha/sessions/{session_id}/activities
```

**Response:**
```json
{
  "activities": [
    {
      "name": "sessions/123/activities/456",
      "id": "456",
      "description": "Analyzed codebase structure",
      "createTime": "2024-01-15T10:30:00.000Z",
      "originator": "AGENT",
      "artifacts": []
    }
  ]
}
```

---

### activities.get

Retrieves a single activity by ID.

**HTTP Request:**
```
GET https://jules.googleapis.com/v1alpha/sessions/{session_id}/activities/{activity_id}
```

---

## Usage Examples

### Python Client Example

```python
import httpx

class JulesClient:
    """Simple Jules API client."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://jules.googleapis.com/v1alpha"

    def _headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
        }

    def create_session(
        self,
        prompt: str,
        owner: str,
        repo: str,
        branch: str = "main",
        title: str | None = None,
        automation_mode: str = "AUTO_CREATE_PR",
        require_plan_approval: bool = False,
    ) -> dict:
        """Create a new Jules session."""
        data = {
            "prompt": prompt,
            "sourceContext": {
                "source": f"sources/github/{owner}/{repo}",
                "githubRepoContext": {"startingBranch": branch},
            },
            "automationMode": automation_mode,
            "requirePlanApproval": require_plan_approval,
        }
        if title:
            data["title"] = title

        response = httpx.post(
            f"{self.base_url}/sessions",
            headers=self._headers(),
            json=data,
        )
        response.raise_for_status()
        return response.json()

    def list_sessions(self) -> dict:
        """List all sessions."""
        response = httpx.get(
            f"{self.base_url}/sessions",
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

    def get_session(self, session_id: str) -> dict:
        """Get a specific session."""
        response = httpx.get(
            f"{self.base_url}/sessions/{session_id}",
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

    def send_message(self, session_id: str, message: str) -> None:
        """Send a message to a session."""
        response = httpx.post(
            f"{self.base_url}/sessions/{session_id}:sendMessage",
            headers=self._headers(),
            json={"prompt": message},
        )
        response.raise_for_status()

    def approve_plan(self, session_id: str) -> None:
        """Approve a session's plan."""
        response = httpx.post(
            f"{self.base_url}/sessions/{session_id}:approvePlan",
            headers=self._headers(),
        )
        response.raise_for_status()

    def get_activities(self, session_id: str) -> dict:
        """Get activities for a session."""
        response = httpx.get(
            f"{self.base_url}/sessions/{session_id}/activities",
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()
```

### Create Session Example

```python
import os

client = JulesClient(api_key=os.environ["JULES_API_KEY"])

# Create a session to fix a bug
session = client.create_session(
    prompt="Fix the authentication timeout issue in src/auth.py",
    owner="myorg",
    repo="myapp",
    branch="main",
    title="Fix auth timeout",
    automation_mode="AUTO_CREATE_PR",
    require_plan_approval=False,
)

print(f"Created session: {session['name']}")
print(f"Session URL: {session.get('url')}")
```

### Monitor Session Status

```python
import time

session_id = session["name"].split("/")[-1]

while True:
    session = client.get_session(session_id)
    state = session["state"]
    print(f"Session state: {state}")

    if state == "COMPLETED":
        print("Session completed!")
        for output in session.get("outputs", []):
            if pr := output.get("pullRequest"):
                print(f"PR created: {pr['url']}")
        break
    elif state == "FAILED":
        print("Session failed!")
        break
    elif state == "AWAITING_USER_FEEDBACK":
        # Get the question from activities
        activities = client.get_activities(session_id)
        # Send response
        client.send_message(session_id, "Please proceed with option A")
    elif state == "AWAITING_PLAN_APPROVAL":
        client.approve_plan(session_id)

    time.sleep(30)
```

---

## Error Handling

The API returns standard HTTP status codes:

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Bad Request - Invalid parameters |
| 401 | Unauthorized - Invalid or missing API key |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found - Session or resource not found |
| 429 | Too Many Requests - Rate limited |
| 500 | Internal Server Error |

---

## Rate Limits

Consult the official documentation for current rate limits. The API may return `429 Too Many Requests` when limits are exceeded.

---

## Best Practices

1. **Use `AUTO_CREATE_PR`** for automated workflows to get automatic PR creation
2. **Handle stuck sessions**: Sessions can get stuck in `QUEUED` or `PLANNING` due to capacity issues
3. **Monitor with polling**: Poll session status every 30-60 seconds
4. **Check `createTime` for staleness**: Sessions older than 1 hour in `QUEUED`/`PLANNING` are likely stuck
5. **Use `requirePlanApproval: false`** for fully automated workflows
6. **Include descriptive titles**: Makes sessions easier to identify in the UI

---

## Related Files

- **Scheduler Implementation:** `.team/repo/scheduler/stateless.py`
- **API Client:** `.team/repo/core/client.py`

---

## Changelog

- **2026-01-28**: Initial documentation created from official API reference
