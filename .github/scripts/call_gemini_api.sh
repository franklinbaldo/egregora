#!/bin/bash
set -euo pipefail

# Call Gemini API directly using curl with fallback models
# This is more reliable than depending on a GitHub Action that might not exist

API_KEY="${GEMINI_API_KEY:-}"
PROMPT_FILE="${1:-.github/tmp/prompt.txt}"
OUTPUT_FILE="${2:-.github/tmp/gemini_response.txt}"
METADATA_FILE="${3:-.github/tmp/gemini_metadata.json}"

if [[ -z "$API_KEY" ]]; then
    echo "Error: GEMINI_API_KEY not set" >&2
    exit 1
fi

if [[ ! -f "$PROMPT_FILE" ]]; then
    echo "Error: Prompt file not found: $PROMPT_FILE" >&2
    exit 1
fi

# Read prompt
PROMPT=$(cat "$PROMPT_FILE")

# Models to try in order
MODELS=(
    "gemini-3-pro-preview"
    "gemini-3-flash-preview"
    "gemini-2.0-pro-preview"
    "gemini-2.0-flash-preview"
    "gemini-1.5-pro-latest"
    "gemini-1.5-flash-latest"
)

echo "Attempting Gemini API calls with fallback models..." >&2

for MODEL in "${MODELS[@]}"; do
    echo "Trying model: $MODEL..." >&2

    # Prepare JSON payload
    PAYLOAD=$(jq -n \
        --arg prompt "$PROMPT" \
        '{
            contents: [{
                parts: [{
                    text: $prompt
                }]
            }]
        }')

    # Call Gemini API
    HTTP_CODE=$(curl -s -w "%{http_code}" -o ".github/tmp/response_temp.json" \
        -X POST \
        -H "Content-Type: application/json" \
        -d "$PAYLOAD" \
        "https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:generateContent?key=${API_KEY}")

    if [[ "$HTTP_CODE" == "200" ]]; then
        # Extract text from response
        if RESPONSE_TEXT=$(jq -r '.candidates[0].content.parts[0].text' .github/tmp/response_temp.json 2>/dev/null); then
            if [[ -n "$RESPONSE_TEXT" ]] && [[ "$RESPONSE_TEXT" != "null" ]]; then
                echo "✓ Success with $MODEL" >&2

                # Write response
                echo "$RESPONSE_TEXT" > "$OUTPUT_FILE"

                # Write metadata
                jq -n \
                    --arg outcome "success" \
                    --arg model "$MODEL" \
                    --arg response_length "${#RESPONSE_TEXT}" \
                    '{outcome: $outcome, model: $model, response_length: $response_length}' \
                    > "$METADATA_FILE"

                rm -f .github/tmp/response_temp.json
                exit 0
            fi
        fi
    fi

    echo "✗ Failed with $MODEL (HTTP $HTTP_CODE)" >&2
done

# All models failed
echo "All models failed" > "$OUTPUT_FILE"
jq -n \
    --arg outcome "failure" \
    --arg model "none" \
    --arg response_length "0" \
    '{outcome: $outcome, model: $model, response_length: $response_length}' \
    > "$METADATA_FILE"

echo "✗ All Gemini models failed" >&2
exit 1
