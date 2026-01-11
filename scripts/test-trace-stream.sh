#!/bin/bash
# Test script for trace streaming functionality
# This demonstrates how traces flow through the system in real-time

set -e

API_URL="${API_URL:-http://localhost:8000}"
TOKEN="${TRUSTMODEL_TOKEN:-}"

if [ -z "$TOKEN" ]; then
    echo "Getting auth token..."
    TOKEN=$(curl -s -X POST "$API_URL/auth/login" \
        -H "Content-Type: application/json" \
        -d '{"email": "test@trustmodel.dev", "password": "testpass123"}' | jq -r '.access_token')

    if [ "$TOKEN" = "null" ] || [ -z "$TOKEN" ]; then
        echo "Failed to get token. Creating user..."
        curl -s -X POST "$API_URL/auth/register" \
            -H "Content-Type: application/json" \
            -d '{"email": "test@trustmodel.dev", "password": "testpass123", "full_name": "Test User", "organization_name": "Test Org"}' > /dev/null

        TOKEN=$(curl -s -X POST "$API_URL/auth/login" \
            -H "Content-Type: application/json" \
            -d '{"email": "test@trustmodel.dev", "password": "testpass123"}' | jq -r '.access_token')
    fi
fi

echo "Token: ${TOKEN:0:20}..."

# Create a test agent
echo ""
echo "Creating test agent..."
AGENT_RESPONSE=$(curl -s -X POST "$API_URL/v1/agents" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
        "name": "trace-test-agent",
        "agent_type": "coding",
        "description": "Agent for testing trace streaming"
    }')

AGENT_ID=$(echo "$AGENT_RESPONSE" | jq -r '.id')
echo "Agent ID: $AGENT_ID"

if [ "$AGENT_ID" = "null" ]; then
    echo "Agent creation failed. Checking if agent exists..."
    AGENT_ID=$(curl -s -H "Authorization: Bearer $TOKEN" "$API_URL/v1/agents" | jq -r '.items[] | select(.name=="trace-test-agent") | .id' | head -1)
    echo "Found existing agent: $AGENT_ID"
fi

# Send some test traces
echo ""
echo "Sending test traces..."
echo "Open the Terminal page in the frontend to see live updates!"
echo ""

for i in 1 2 3; do
    echo "Sending trace batch $i..."
    curl -s -X POST "$API_URL/v1/traces/ingest" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d "{
            \"agent_id\": \"$AGENT_ID\",
            \"spans\": [
                {
                    \"span_type\": \"agent\",
                    \"name\": \"Task $i: Processing request\",
                    \"status\": \"running\",
                    \"attributes\": {\"task_number\": $i}
                },
                {
                    \"span_type\": \"llm\",
                    \"name\": \"LLM call: Generate response\",
                    \"status\": \"success\",
                    \"attributes\": {\"model\": \"claude-3\", \"tokens\": $(($RANDOM % 1000))}
                },
                {
                    \"span_type\": \"tool\",
                    \"name\": \"Tool: File write\",
                    \"status\": \"success\",
                    \"attributes\": {\"file\": \"output_$i.txt\"}
                }
            ],
            \"metadata\": {\"source\": \"test-script\", \"batch\": $i}
        }" | jq -r '.message'

    sleep 1
done

echo ""
echo "Done! Check the Terminal page's Live Traces panel."
echo ""
echo "To test with tm-trace wrapper:"
echo "  export TRUSTMODEL_TOKEN=$TOKEN"
echo "  ./scripts/tm-trace --agent $AGENT_ID echo 'Hello from traced command'"
