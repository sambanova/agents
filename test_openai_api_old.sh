#!/bin/bash

# Test script for OpenAI Compatible API
# Usage: ./test_openai_api.sh <API_KEY> [BASE_URL]
# Example: ./test_openai_api.sh your-api-key-here
# Example: ./test_openai_api.sh your-api-key-here https://api.example.com/api/v1

# Check if API key is provided
if [ -z "$1" ]; then
  echo "Error: API key is required"
  echo "Usage: $0 <API_KEY> [BASE_URL]"
  echo "Example: $0 your-api-key-here"
  echo "Example: $0 your-api-key-here https://api.example.com/api/v1"
  exit 1
fi

API_KEY="$1"
BASE_URL="${2:-http://localhost:8000/api/v1}"

echo "======================================"
echo "Testing OpenAI Compatible API"
echo "======================================"
echo "Base URL: $BASE_URL"
echo "API Key: ${API_KEY:0:8}..."
echo ""

# Test 1: Health check
echo "Test 0: Health Check"
echo "Expected: Healthy status"
echo "--------------------------------------"
curl -s -X GET "http://localhost:8000/api/health" | jq '.'
echo -e "\n\n"

# Test 2: List available tools
echo "Test 1: List Available Tools"
echo "Expected: Array of tool definitions"
echo "--------------------------------------"
curl -s -X GET "${BASE_URL}/tools" \
  -H "Authorization: Bearer ${API_KEY}" | jq '{
  tool_count: (. | length),
  tools: [.[] | {name: .function.name, description: (.function.description | .[0:80])}]
}'
echo -e "\n\n"

# Test 3: Simple non-streaming request
echo "Test 2: Simple Non-Streaming Request"
echo "Expected: Completed response with answer"
echo "--------------------------------------"
curl -s -X POST "${BASE_URL}/responses" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mainagent",
    "input": "What is 2 + 2? Be concise.",
    "stream": false
  }' | jq '.'
echo -e "\n\n"

# Test 4: Model alias (gpt-4)
echo "Test 3: Model Alias (gpt-4 -> mainagent)"
echo "Expected: Response using gpt-4 alias"
echo "--------------------------------------"
curl -s -X POST "${BASE_URL}/responses" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4",
    "input": "What is the capital of France? One word answer.",
    "stream": false
  }' | jq '.'
echo -e "\n\n"

# Test 5: Create a chart (code execution)
echo "Test 4: Chart Generation via Code Execution"
echo "Expected: Response with analysis and chart saved"
echo "--------------------------------------"
curl -s -X POST "${BASE_URL}/responses" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mainagent",
    "input": "Create a line chart showing quarterly revenue growth: Q1: $1M, Q2: $1.5M, Q3: $2.1M, Q4: $2.8M. Save as revenue_growth.png. Then analyze the trend briefly.",
    "stream": false
  }' | jq '.'
echo -e "\n\n"

# Test 6: Financial analysis request
echo "Test 5: Financial Analysis Request"
echo "Expected: Analysis of Apple stock"
echo "--------------------------------------"
curl -s -X POST "${BASE_URL}/responses" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mainagent",
    "input": "Analyze Apple stock (AAPL). Provide a brief summary of key metrics.",
    "stream": false
  }' | jq '.'
echo -e "\n\n"

# Test 7: Multiple charts request
echo "Test 6: Multiple Charts Generation"
echo "Expected: Analysis with multiple visualizations"
echo "--------------------------------------"
RESPONSE=$(curl -s -X POST "${BASE_URL}/responses" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mainagent",
    "input": "Analyze this sales data: Product A sold 100, 120, 150, 180 units over 4 months. Product B sold 80, 90, 95, 110 units. Create: 1) A line chart comparing both (comparison.png), 2) A bar chart showing totals (totals.png). Brief insights on growth.",
    "stream": false
  }')

echo "$RESPONSE" | jq '.'
  id,
  status,
  output_preview: [.output[] | {type, text: (.text[:300] + "...")}]
}'
echo -e "\n\n"

# Test 8: Python code generation
echo "Test 7: Python Script Generation"
echo "Expected: Explanation and code"
echo "--------------------------------------"
curl -s -X POST "${BASE_URL}/responses" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mainagent",
    "input": "Create a Python script that calculates fibonacci numbers up to n=10. Save it as fibonacci.py and explain how it works.",
    "stream": false
}'
echo -e "\n\n"

# Test 9: Structured input format
echo "Test 8: Structured Input Format"
echo "Expected: Response using array input format"
echo "--------------------------------------"
curl -s -X POST "${BASE_URL}/responses" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mainagent",
    "input": [
      {"type": "text", "text": "Count from 1 to 5."}
    ],
    "stream": false
echo -e "\n\n"

# Test 10: Metadata preservation
echo "Test 9: Metadata Preservation"
echo "Expected: Custom metadata in response"
echo "--------------------------------------"
curl -s -X POST "${BASE_URL}/responses" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mainagent",
    "input": "Hello, how are you?",
    "stream": false,
    "metadata": {
      "user_session": "test-session-123",
      "custom_field": "test-value"
    }
}'
echo -e "\n\n"

# Test 11: Streaming request
echo "Test 10: Streaming Request (SSE)"
echo "Expected: Stream of events (response.created, deltas, completed)"
echo "--------------------------------------"
echo "Starting stream..."

curl -s -N -X POST "${BASE_URL}/responses" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mainagent",
    "input": "Count from 1 to 3 and explain each number briefly.",
    "stream": true
  }' | while IFS= read -r line; do
    if [[ $line == data:* ]]; then
      # Extract and format the JSON data
      json_data="${line#data: }"
      event_type=$(echo "$json_data" | jq -r '.event' 2>/dev/null)

      if [ "$event_type" == "response.created" ]; then
        echo "✓ [CREATED] Response started"
        echo "$json_data" | jq '{event, data: {id: .data.id, status: .data.status}}'
      elif [ "$event_type" == "response.output_text.delta" ]; then
        # Print delta text inline
        delta=$(echo "$json_data" | jq -r '.data.delta' 2>/dev/null)
        if [ ! -z "$delta" ] && [ "$delta" != "null" ]; then
          echo -n "$delta"
        fi
      elif [ "$event_type" == "response.completed" ]; then
        echo ""
        echo "✓ [COMPLETED] Response finished"
        echo "$json_data" | jq '{event, data: {id: .data.id, status: .data.status}}'
      fi
    fi
  done

echo -e "\n\n"

# Test 12: Error handling - No auth
echo "Test 11: Error Handling - No Authorization"
echo "Expected: 401 error with OpenAI format"
echo "--------------------------------------"
curl -s -X POST "${BASE_URL}/responses" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mainagent",
    "input": "Hello",
    "stream": false
  }' | jq '.'
echo -e "\n\n"

# Test 13: Error handling - Invalid model
echo "Test 12: Error Handling - Invalid Model"
echo "Expected: 400 error with OpenAI format"
echo "--------------------------------------"
curl -s -X POST "${BASE_URL}/responses" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "invalid-model-xyz",
    "input": "Hello",
    "stream": false
  }' | jq '.'
echo -e "\n\n"

# Test 14: Deep research with auto-resume
echo "Test 13: Deep Research with Auto-Resume"
echo "Expected: Completed response (interrupts auto-approved)"
echo "Note: This may take 30-60 seconds"
echo "--------------------------------------"
curl -s -X POST "${BASE_URL}/responses" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mainagent",
    "input": "Do a quick research on quantum computing developments in 2024. Keep it brief.",
    "stream": false
  }' | jq '.'
echo -e "\n\n"

# Test 15: Comprehensive data analysis
echo "Test 14: Comprehensive Data Analysis"
echo "Expected: Multi-step analysis with insights"
echo "--------------------------------------"
curl -s -X POST "${BASE_URL}/responses" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mainagent",
    "input": "Create a comprehensive analysis of monthly sales: Jan $50k, Feb $55k, Mar $48k, Apr $62k, May $71k, Jun $68k. Include: 1) Line chart (sales_trend.png), 2) Statistical summary, 3) Growth analysis, 4) Recommendations.",
    "stream": false
}'
echo -e "\n\n"

echo "======================================"
echo "All tests complete!"
echo "======================================"
echo ""
echo "Summary:"
echo "- Base URL: $BASE_URL"
echo "- API Key: ${API_KEY:0:8}..."
echo "- Total tests: 15"
echo ""
echo "Check the output above for any errors."
echo "All responses should have 'status': 'completed' or streaming events."
echo ""
