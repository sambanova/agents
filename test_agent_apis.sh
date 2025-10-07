#!/bin/bash

# Test script for Agent v2 APIs
# Your API Key
API_KEY="API_KEY"
BASE_URL="http://localhost:8000/api/agent"

echo "======================================"
echo "Testing Agent v2 APIs"
echo "======================================"
echo ""

# Test 1: Financial Analysis (text only, no artifacts)
echo "Test 1: Financial Analysis - Apple Stock"
echo "Expected: JSON analysis of AAPL"
echo "--------------------------------------"
curl -X POST "${BASE_URL}/financialanalysis" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Analyze Apple stock (AAPL)"
  }' | jq '{status, result: (.result | fromjson | {ticker, company_name, market_cap}), artifacts}'

echo -e "\n\n"

# Test 2: Main Agent - Create a chart (completion + artifact)
echo "Test 2: Main Agent - Sales Chart with Analysis"
echo "Expected: Text explanation + chart artifact"
echo "--------------------------------------"
RESPONSE=$(curl -s -X POST "${BASE_URL}/mainagent" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Create a line chart showing quarterly revenue growth: Q1: $1M, Q2: $1.5M, Q3: $2.1M, Q4: $2.8M. Save as revenue_growth.png. Then analyze the trend and provide insights."
  }')

echo "$RESPONSE" | jq '{
  status,
  result: .result[:200] + "...",
  artifacts: .artifacts,
  artifact_count: (.artifacts | length)
}'

# Download the chart
FILE_ID=$(echo "$RESPONSE" | jq -r '.artifacts[0]')
if [ "$FILE_ID" != "null" ]; then
  echo "Downloading chart: $FILE_ID"
  curl -s -X GET "${BASE_URL}/files/${FILE_ID}" \
    -H "Authorization: Bearer ${API_KEY}" \
    --output /tmp/revenue_growth.png
  echo "Chart saved to: /tmp/revenue_growth.png"
  file /tmp/revenue_growth.png
fi

echo -e "\n\n"

# Test 3: Main Agent - Data Analysis with Multiple Artifacts
echo "Test 3: Main Agent - Comprehensive Analysis with Multiple Charts"
echo "Expected: Analysis text + multiple chart artifacts"
echo "--------------------------------------"
RESPONSE=$(curl -s -X POST "${BASE_URL}/mainagent" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Analyze this sales data and create visualizations: Product A sold 100, 120, 150, 180 units over 4 months. Product B sold 80, 90, 95, 110 units. Create: 1) A line chart comparing both products (comparison.png), 2) A bar chart showing total sales per product (totals.png). Provide insights on which product is growing faster."
  }')

echo "$RESPONSE" | jq '{
  status,
  result: .result[:300] + "...",
  artifacts: .artifacts,
  artifact_count: (.artifacts | length)
}'

# Download all artifacts
ARTIFACTS=$(echo "$RESPONSE" | jq -r '.artifacts[]')
COUNT=1
for FILE_ID in $ARTIFACTS; do
  echo "Downloading artifact $COUNT: $FILE_ID"
  curl -s -X GET "${BASE_URL}/files/${FILE_ID}" \
    -H "Authorization: Bearer ${API_KEY}" \
    --output "/tmp/artifact_${COUNT}.png"
  echo "Saved to: /tmp/artifact_${COUNT}.png"
  file "/tmp/artifact_${COUNT}.png"
  COUNT=$((COUNT + 1))
done

echo -e "\n\n"

# Test 4: Main Agent - Code Generation (text + code file)
echo "Test 4: Main Agent - Python Script Generation"
echo "Expected: Explanation + Python script artifact"
echo "--------------------------------------"
RESPONSE=$(curl -s -X POST "${BASE_URL}/mainagent" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Create a Python script that calculates fibonacci numbers up to n=10 and prints them. Save it as fibonacci.py. Explain how the code works."
  }')

echo "$RESPONSE" | jq '{
  status,
  result: .result[:200] + "...",
  artifacts: .artifacts
}'

FILE_ID=$(echo "$RESPONSE" | jq -r '.artifacts[0]')
if [ "$FILE_ID" != "null" ]; then
  echo "Downloading script: $FILE_ID"
  curl -s -X GET "${BASE_URL}/files/${FILE_ID}" \
    -H "Authorization: Bearer ${API_KEY}" \
    --output /tmp/fibonacci.py
  echo "Script saved to: /tmp/fibonacci.py"
  echo "--- Script Content ---"
  cat /tmp/fibonacci.py
fi

echo -e "\n\n"

# Test 5: Main Agent - HTML + PDF Report (multiple artifacts)
echo "Test 5: Main Agent - Executive Report (HTML + PDF)"
echo "Expected: Explanation + HTML file + PDF file"
echo "--------------------------------------"
RESPONSE=$(curl -s -X POST "${BASE_URL}/mainagent" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Create a professional executive summary report about AI trends in 2024. Include 3 key trends. Save as both HTML (ai_trends.html) and PDF (ai_trends.pdf). Make it visually appealing."
  }')

echo "$RESPONSE" | jq '{
  status,
  result: .result[:200] + "...",
  artifacts: .artifacts,
  artifact_count: (.artifacts | length)
}'

# Download HTML
HTML_ID=$(echo "$RESPONSE" | jq -r '.artifacts[0]')
if [ "$HTML_ID" != "null" ]; then
  echo "Downloading HTML: $HTML_ID"
  curl -s -X GET "${BASE_URL}/files/${HTML_ID}" \
    -H "Authorization: Bearer ${API_KEY}" \
    --output /tmp/ai_trends.html
  echo "HTML saved to: /tmp/ai_trends.html"
  echo "Preview (first 500 chars):"
  head -c 500 /tmp/ai_trends.html
  echo ""
fi

# Download PDF
PDF_ID=$(echo "$RESPONSE" | jq -r '.artifacts[1]')
if [ "$PDF_ID" != "null" ]; then
  echo "Downloading PDF: $PDF_ID"
  curl -s -X GET "${BASE_URL}/files/${PDF_ID}" \
    -H "Authorization: Bearer ${API_KEY}" \
    --output /tmp/ai_trends.pdf
  echo "PDF saved to: /tmp/ai_trends.pdf"
  file /tmp/ai_trends.pdf
fi

echo -e "\n\n"

# Test 6: Coding Agent - Direct Code Execution
echo "Test 6: Coding Agent - Execute Python Code"
echo "Expected: Execution output + any generated files"
echo "--------------------------------------"
curl -s -X POST "${BASE_URL}/coding" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Run this code and explain the output",
    "code": "import numpy as np\nimport matplotlib.pyplot as plt\n\nx = np.linspace(0, 2*np.pi, 100)\ny = np.sin(x)\nplt.figure(figsize=(10, 6))\nplt.plot(x, y, label=\"sin(x)\", color=\"blue\")\nplt.title(\"Sine Wave\")\nplt.xlabel(\"x\")\nplt.ylabel(\"sin(x)\")\nplt.grid(True)\nplt.legend()\nplt.savefig(\"sine_wave.png\")\nprint(\"Sine wave chart created!\")"
  }' | jq '{
  status,
  result: .result[:300] + "...",
  artifacts: .artifacts
}'

echo -e "\n\n"

# Test 7: Main Agent Interactive - Multi-turn conversation
echo "Test 7: Main Agent Interactive - Multi-turn with Artifacts"
echo "Expected: Thread ID for follow-up questions"
echo "--------------------------------------"

# Step 1: Initial request
RESPONSE=$(curl -s -X POST "${BASE_URL}/mainagent/interactive" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Create a bar chart showing population by continent: Asia 4.7B, Africa 1.4B, Europe 750M, North America 600M, South America 430M, Oceania 45M. Save as population.png",
    "resume": false
  }')

THREAD_ID=$(echo "$RESPONSE" | jq -r '.thread_id')
echo "Thread ID: $THREAD_ID"
echo "$RESPONSE" | jq '{status, artifacts}'

# Step 2: Follow-up question using same thread
echo "Follow-up question in same thread..."
curl -s -X POST "${BASE_URL}/mainagent/interactive" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d "{
    \"prompt\": \"Now create a pie chart showing the percentage distribution and save as population_pie.png\",
    \"thread_id\": \"${THREAD_ID}\",
    \"resume\": true
  }" | jq '{
  status,
  result: .result[:200] + "...",
  artifacts: .artifacts
}'

echo -e "\n\n"
echo "======================================"
echo "All tests complete!"
echo "Check /tmp/ for downloaded artifacts"
echo "======================================"
