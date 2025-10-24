---
name: jules-api
description: Use Google's Jules API to create and manage asynchronous coding sessions. Invoke when the user asks to interact with Jules, create Jules sessions, check Jules task status, or manage Jules coding tasks.
---

# Jules API Integration

This skill enables interaction with Google's Jules API for programmatic creation and management of asynchronous coding tasks.

## Overview

The Jules API allows you to:
- Create coding sessions with specific prompts and repository context
- Monitor session progress through various states
- Send messages and feedback to active sessions
- Approve generated plans before execution
- Retrieve session outputs (pull requests, artifacts)

## Base Configuration

**Base URL**: `https://julius.googleapis.com`
**API Version**: v1alpha
**Authentication**: Google Cloud API authentication (user must configure)

## Core Operations

### 1. Create a Session

Create a new coding session with a prompt and repository context.

**Endpoint**: `POST /v1alpha/sessions`

**Request Body**:
```json
{
  "prompt": "Your coding task description",
  "sourceContext": {
    "githubRepository": {
      "owner": "username",
      "name": "repository",
      "branch": "main"
    }
  },
  "title": "Optional session title",
  "requirePlanApproval": false,
  "automationMode": "AUTO"
}
```

**Example using curl**:
```bash
curl -X POST https://julius.googleapis.com/v1alpha/sessions \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Add unit tests for authentication module",
    "sourceContext": {
      "githubRepository": {
        "owner": "myorg",
        "name": "myrepo",
        "branch": "main"
      }
    },
    "requirePlanApproval": true
  }'
```

### 2. Get Session Status

Retrieve details about a specific session.

**Endpoint**: `GET /v1alpha/sessions/{sessionId}`

**Example**:
```bash
curl https://julius.googleapis.com/v1alpha/sessions/abc123 \
  -H "Authorization: Bearer $(gcloud auth print-access-token)"
```

**Session States**:
- `QUEUED`: Session is waiting to start
- `PLANNING`: Generating execution plan
- `AWAITING_PLAN_APPROVAL`: Waiting for user approval
- `AWAITING_USER_FEEDBACK`: Needs user input
- `IN_PROGRESS`: Actively executing
- `PAUSED`: Temporarily stopped
- `COMPLETED`: Successfully finished
- `FAILED`: Encountered error

### 3. List All Sessions

Retrieve all sessions.

**Endpoint**: `GET /v1alpha/sessions`

**Example**:
```bash
curl https://julius.googleapis.com/v1alpha/sessions \
  -H "Authorization: Bearer $(gcloud auth print-access-token)"
```

### 4. Send Message to Session

Send user feedback or additional instructions to an active session.

**Endpoint**: `POST /v1alpha/sessions/{sessionId}:sendMessage`

**Request Body**:
```json
{
  "message": "Your message or feedback"
}
```

**Example**:
```bash
curl -X POST https://julius.googleapis.com/v1alpha/sessions/abc123:sendMessage \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  -d '{"message": "Please add more test coverage for edge cases"}'
```

### 5. Approve Plan

Approve a generated plan (when requirePlanApproval is true).

**Endpoint**: `POST /v1alpha/sessions/{sessionId}:approvePlan`

**Example**:
```bash
curl -X POST https://julius.googleapis.com/v1alpha/sessions/abc123:approvePlan \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json"
```

### 6. Get Session Activities

Retrieve activity logs for a session.

**Endpoint**: `GET /v1alpha/sessions/{sessionId}/activities`

**Example**:
```bash
curl https://julius.googleapis.com/v1alpha/sessions/abc123/activities \
  -H "Authorization: Bearer $(gcloud auth print-access-token)"
```

## Authentication Setup

The user must authenticate using Google Cloud:

```bash
# Install gcloud CLI
# https://cloud.google.com/sdk/docs/install

# Authenticate
gcloud auth login

# Set project
gcloud config set project YOUR_PROJECT_ID

# Get access token for API calls
gcloud auth print-access-token
```

## Python Example

```python
import requests
import subprocess

def get_access_token():
    result = subprocess.run(
        ['gcloud', 'auth', 'print-access-token'],
        capture_output=True,
        text=True
    )
    return result.stdout.strip()

def create_jules_session(prompt, owner, repo, branch='main'):
    url = 'https://julius.googleapis.com/v1alpha/sessions'
    headers = {
        'Authorization': f'Bearer {get_access_token()}',
        'Content-Type': 'application/json'
    }
    data = {
        'prompt': prompt,
        'sourceContext': {
            'githubRepository': {
                'owner': owner,
                'name': repo,
                'branch': branch
            }
        }
    }
    response = requests.post(url, headers=headers, json=data)
    return response.json()

def get_session_status(session_id):
    url = f'https://julius.googleapis.com/v1alpha/sessions/{session_id}'
    headers = {
        'Authorization': f'Bearer {get_access_token()}'
    }
    response = requests.get(url, headers=headers)
    return response.json()

# Usage
session = create_jules_session(
    prompt='Add error handling to API endpoints',
    owner='myorg',
    repo='myproject'
)
print(f"Created session: {session['id']}")

# Check status
status = get_session_status(session['id'])
print(f"Status: {status['state']}")
```

## Best Practices

1. **Use Descriptive Prompts**: Provide clear, specific instructions for the coding task
2. **Monitor State**: Poll session status to track progress
3. **Enable Plan Approval**: Set `requirePlanApproval: true` for sensitive operations
4. **Handle States**: Implement proper handling for AWAITING_USER_FEEDBACK and AWAITING_PLAN_APPROVAL states
5. **Check Outputs**: Review the `outputs` array for generated pull requests and artifacts

## Common Workflows

### Workflow 1: Simple Task
1. Create session with prompt
2. Poll status until COMPLETED or FAILED
3. Retrieve outputs (PRs)

### Workflow 2: Supervised Task
1. Create session with `requirePlanApproval: true`
2. Wait for AWAITING_PLAN_APPROVAL state
3. Review plan in activities
4. Call approvePlan
5. Monitor until completion

### Workflow 3: Interactive Task
1. Create session
2. Monitor for AWAITING_USER_FEEDBACK
3. Use sendMessage to provide feedback
4. Continue monitoring until completion

## Error Handling

Always check response status codes:
- `200 OK`: Success
- `400 Bad Request`: Invalid request parameters
- `401 Unauthorized`: Authentication failed
- `404 Not Found`: Session doesn't exist
- `403 Forbidden`: Insufficient permissions

## References

- Official Documentation: https://developers.google.com/jules/api/reference/rest
- Sessions API: https://developers.google.com/jules/api/reference/rest/v1alpha/sessions
