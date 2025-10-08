#!/bin/bash

# Comprehensive Test Script for OpenAI Responses API
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
TEST_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "======================================"
echo "Testing OpenAI Responses API"
echo "======================================"
echo "Base URL: $BASE_URL"
echo "API Key: ${API_KEY:0:8}..."
echo "Test Dir: $TEST_DIR"
echo ""

# Color output helpers
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_test() {
  echo -e "${YELLOW}$1${NC}"
}

print_success() {
  echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
  echo -e "${RED}✗ $1${NC}"
}

# Test 0: Health check
print_test "Test 0: Health Check"
echo "Expected: Healthy status"
echo "--------------------------------------"
curl -s -X GET "http://localhost:8000/api/health" | jq '.'
echo -e "\n\n"

# Test 1: List available tools
print_test "Test 1: List Available Tools"
echo "Expected: Array of tool definitions"
echo "--------------------------------------"
curl -s -X GET "${BASE_URL}/tools" \
  -H "Authorization: Bearer ${API_KEY}" | jq '.'
echo -e "\n\n"

# Test 2: Simple non-streaming request
print_test "Test 2: Simple Non-Streaming Request"
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

# Test 3: Model alias (gpt-4)
print_test "Test 3: Model Alias (gpt-4 -> mainagent)"
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

# Test 4: Financial Analysis (Production Test 1)
print_test "Test 4: Financial Analysis - Apple Stock"
echo "Expected: Comprehensive financial analysis"
echo "--------------------------------------"
curl -s -X POST "${BASE_URL}/responses" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mainagent",
    "input": "Please perform a financial analysis of Apple (AAPL). Include key metrics, recent performance, and competitive positioning.",
    "stream": false
  }' | jq '.'
echo -e "\n\n"

# Test 5: Chart Generation with Artifacts
print_test "Test 5: Chart Generation via Code Execution"
echo "Expected: Response with analysis and chart artifact"
echo "--------------------------------------"
RESPONSE=$(curl -s -X POST "${BASE_URL}/responses" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mainagent",
    "input": "Create a line chart showing quarterly revenue growth: Q1: $1M, Q2: $1.5M, Q3: $2.1M, Q4: $2.8M. Save as revenue_growth.png. Then analyze the trend briefly.",
    "stream": false
  }')

echo "$RESPONSE" | jq '.'

# Download artifact if present
ARTIFACTS=$(echo "$RESPONSE" | jq -r '.metadata.artifacts[]?' 2>/dev/null)
if [ ! -z "$ARTIFACTS" ]; then
  print_success "Found artifacts, downloading..."
  COUNT=1
  for FILE_ID in $ARTIFACTS; do
    echo "Downloading artifact $COUNT: $FILE_ID"
    curl -s -X GET "http://localhost:8000/api/agent/files/${FILE_ID}" \
      -H "Authorization: Bearer ${API_KEY}" \
      --output "/tmp/openai_test_artifact_${COUNT}.png"
    if [ -f "/tmp/openai_test_artifact_${COUNT}.png" ]; then
      print_success "Saved to: /tmp/openai_test_artifact_${COUNT}.png"
      file "/tmp/openai_test_artifact_${COUNT}.png"
    fi
    COUNT=$((COUNT + 1))
  done
fi
echo -e "\n\n"

# Test 6: Multiple Charts (Production Test 4 - Synthetic Data)
print_test "Test 6: Multiple Charts Generation"
echo "Expected: Analysis with multiple visualizations"
echo "--------------------------------------"
RESPONSE=$(curl -s -X POST "${BASE_URL}/responses" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mainagent",
    "input": "Generate synthetic sensor data for a manufacturing plant simulation: temperature (20-80°C), pressure (1-5 bar), vibration (0-10 mm/s) over 100 time points. Create visualizations: 1) Multi-line time series (sensors.png), 2) Correlation heatmap (correlation.png). Save data as sensors.csv.",
    "stream": false
  }')

echo "$RESPONSE" | jq '.'

ARTIFACTS=$(echo "$RESPONSE" | jq -r '.metadata.artifacts[]?' 2>/dev/null)
if [ ! -z "$ARTIFACTS" ]; then
  print_success "Found $(echo "$ARTIFACTS" | wc -w) artifacts"
fi
echo -e "\n\n"

# Test 7: HTML + PDF Report (Production Test 3)
print_test "Test 7: AI Industry Intelligence Report (HTML + PDF)"
echo "Expected: Comprehensive report with multiple artifacts"
echo "--------------------------------------"
RESPONSE=$(curl -s -X POST "${BASE_URL}/responses" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mainagent",
    "input": "Create a comprehensive AI Industry Intelligence Report covering: 1) Market size and growth projections, 2) Key players and competitive landscape, 3) Emerging trends and technologies, 4) Investment and M&A activity. Generate both HTML (ai_industry_report.html) and PDF (ai_industry_report.pdf) versions with professional styling, charts, and data tables.",
    "stream": false
  }')

echo "$RESPONSE" | jq '.'

ARTIFACTS=$(echo "$RESPONSE" | jq -r '.metadata.artifacts[]?' 2>/dev/null)
if [ ! -z "$ARTIFACTS" ]; then
  print_success "Found artifacts for report"
  COUNT=1
  for FILE_ID in $ARTIFACTS; do
    EXT="file"
    if [ $COUNT -eq 1 ]; then EXT="html"; fi
    if [ $COUNT -eq 2 ]; then EXT="pdf"; fi
    curl -s -X GET "http://localhost:8000/api/agent/files/${FILE_ID}" \
      -H "Authorization: Bearer ${API_KEY}" \
      --output "/tmp/ai_industry_report_${COUNT}.${EXT}"
    print_success "Saved artifact $COUNT to: /tmp/ai_industry_report_${COUNT}.${EXT}"
    COUNT=$((COUNT + 1))
  done
fi
echo -e "\n\n"

# Test 8: E-commerce Dashboard (Production Test 5)
print_test "Test 8: E-commerce Executive Dashboard"
echo "Expected: Interactive dashboard with visualizations"
echo "--------------------------------------"
curl -s -X POST "${BASE_URL}/responses" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mainagent",
    "input": "Create an executive dashboard for an e-commerce platform using sample data: Daily sales ($50k-$200k), conversion rates (2-5%), customer acquisition cost ($20-$80), avg order value ($45-$120) over 30 days. Generate: 1) Dashboard HTML with interactive charts (dashboard.html), 2) KPI summary PDF (kpi_summary.pdf), 3) Raw data export (metrics.csv).",
    "stream": false
  }' | jq '.'
echo -e "\n\n"

# Test 9: Strategic Market Research (Production Test 6)
print_test "Test 9: Market Research PowerPoint"
echo "Expected: PowerPoint presentation artifact"
echo "--------------------------------------"
curl -s -X POST "${BASE_URL}/responses" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mainagent",
    "input": "Conduct strategic market research on the cloud computing industry and create a PowerPoint presentation (cloud_market_research.pptx) with: 1) Executive summary slide, 2) Market size & growth (with charts), 3) Competitive analysis (AWS, Azure, GCP comparison table), 4) Customer segments and use cases, 5) Future outlook and recommendations. Use professional design and data visualizations.",
    "stream": false
  }' | jq '.'
echo -e "\n\n"

# Test 10: Streaming Request (SSE)
print_test "Test 10: Streaming Request (SSE)"
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
      json_data="${line#data: }"
      event_type=$(echo "$json_data" | jq -r '.event' 2>/dev/null)

      if [ "$event_type" == "response.created" ]; then
        print_success "[CREATED] Response started"
        echo "$json_data" | jq '.'
      elif [ "$event_type" == "response.output_text.delta" ]; then
        delta=$(echo "$json_data" | jq -r '.data.delta' 2>/dev/null)
        if [ ! -z "$delta" ] && [ "$delta" != "null" ]; then
          echo -n "$delta"
        fi
      elif [ "$event_type" == "response.completed" ]; then
        echo ""
        print_success "[COMPLETED] Response finished"
        echo "$json_data" | jq '.'
      fi
    fi
  done

echo -e "\n\n"

# Test 11: Structured Input Format
print_test "Test 11: Structured Input Format"
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
  }' | jq '.'
echo -e "\n\n"

# Test 12: Image Analysis with Vision (Production Test 2)
print_test "Test 12: Image Analysis with Vision"
echo "Expected: Analysis of image content"
echo "--------------------------------------"

# Check if test image exists
if [ -f "${TEST_DIR}/test_image.png" ]; then
  print_success "Found test image: ${TEST_DIR}/test_image.png"

  # Convert image to base64
  IMAGE_BASE64=$(base64 -i "${TEST_DIR}/test_image.png")

  curl -s -X POST "${BASE_URL}/responses" \
    -H "Authorization: Bearer ${API_KEY}" \
    -H "Content-Type: application/json" \
    -d "{
      \"model\": \"mainagent\",
      \"input\": [
        {\"type\": \"text\", \"text\": \"Please analyze this image in detail. Describe what you see, identify key elements, colors, composition, and any text or notable features. Provide a comprehensive analysis.\"},
        {\"type\": \"image\", \"source\": {\"type\": \"base64\", \"base64\": \"${IMAGE_BASE64}\"}}
      ],
      \"stream\": false
    }" | jq '.'
else
  print_error "Test image not found at ${TEST_DIR}/test_image.png"
  echo "Skipping vision test"
fi
echo -e "\n\n"

# Test 13: Error Handling - No Authorization
print_test "Test 13: Error Handling - No Authorization"
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

# Test 14: Error Handling - Invalid Model
print_test "Test 14: Error Handling - Invalid Model"
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

# Test 15: Deep Research (Production Test 7)
print_test "Test 15: Deep Research with Auto-Resume"
echo "Expected: Comprehensive research report (auto-approves interrupts)"
echo "Note: This may take 60-120 seconds"
echo "--------------------------------------"
RESPONSE=$(curl -s -X POST "${BASE_URL}/responses" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mainagent",
    "input": "Write me a deep research report on SambaNova Systems: company background, technology stack, competitive advantages, recent developments, funding history, and market position in the AI accelerator space.",
    "stream": false
  }')

# Show full response
echo "$RESPONSE" | jq '.'

# Check if deep research was successful
OUTPUT_LENGTH=$(echo "$RESPONSE" | jq -r '.output[0].text' | wc -c)
if [ "$OUTPUT_LENGTH" -gt 5000 ]; then
  print_success "Deep research completed successfully (${OUTPUT_LENGTH} chars)"
else
  print_error "Deep research output too short (${OUTPUT_LENGTH} chars) - may not have triggered deep research subgraph"
fi
echo -e "\n\n"

# Test 16: Metadata Preservation
print_test "Test 16: Metadata Preservation"
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
  }' | jq '.'
echo -e "\n\n"

# Optional Test 17: Data Science EDA (Production Test 8 - OPTIONAL, LONGER)
read -p "Run optional longer test 17 (Data Science EDA)? This may take 2-5 minutes. [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
  print_test "Test 17: Data Science - Exploratory Data Analysis (OPTIONAL)"
  echo "Expected: Comprehensive EDA with visualizations"
  echo "Note: Requires Titanic dataset in test folder"
  echo "--------------------------------------"

  if [ -f "${TEST_DIR}/titanic.csv" ]; then
    curl -s -X POST "${BASE_URL}/responses" \
      -H "Authorization: Bearer ${API_KEY}" \
      -H "Content-Type: application/json" \
      -d '{
        "model": "mainagent",
        "input": "Perform comprehensive exploratory data analysis on the Titanic dataset (titanic.csv). Include: 1) Data quality assessment, 2) Univariate analysis with histograms, 3) Bivariate analysis (survival vs features), 4) Correlation analysis, 5) Missing value analysis, 6) Feature engineering suggestions. Generate visualizations and save as EDA_report.html with all charts embedded.",
        "stream": false
      }' | jq '.'
  else
    print_error "titanic.csv not found in ${TEST_DIR}"
    echo "Skipping EDA test"
  fi
  echo -e "\n\n"
fi

# Optional Test 18: Data Science Modeling (Production Test 9 - OPTIONAL, LONGER)
read -p "Run optional longer test 18 (Predictive Modeling)? This may take 3-7 minutes. [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
  print_test "Test 18: Data Science - Predictive Modeling (OPTIONAL)"
  echo "Expected: Complete ML pipeline with model artifacts"
  echo "Note: Requires customer churn dataset in test folder"
  echo "--------------------------------------"

  if [ -f "${TEST_DIR}/customer_churn.csv" ]; then
    curl -s -X POST "${BASE_URL}/responses" \
      -H "Authorization: Bearer ${API_KEY}" \
      -H "Content-Type: application/json" \
      -d '{
        "model": "mainagent",
        "input": "Build a complete machine learning pipeline for customer churn prediction using customer_churn.csv: 1) Data preprocessing and feature engineering, 2) Train multiple models (Logistic Regression, Random Forest, XGBoost), 3) Hyperparameter tuning, 4) Model evaluation with ROC curves and confusion matrices, 5) Feature importance analysis, 6) Generate prediction report (churn_model_report.pdf) with all metrics and visualizations. Save the best model as churn_model.pkl.",
        "stream": false
      }' | jq '.'
  else
    print_error "customer_churn.csv not found in ${TEST_DIR}"
    echo "Skipping modeling test"
  fi
  echo -e "\n\n"
fi

echo "======================================"
print_success "All tests complete!"
echo "======================================"
echo ""
echo "Summary:"
echo "- Base URL: $BASE_URL"
echo "- API Key: ${API_KEY:0:8}..."
echo "- Core tests: 16"
echo "- Optional tests: 2 (if run)"
echo ""
echo "Check /tmp/ for downloaded artifacts:"
ls -lh /tmp/openai_test_artifact_* /tmp/ai_industry_report_* 2>/dev/null || echo "  (no artifacts downloaded)"
echo ""
print_success "All responses should have 'status': 'completed' or streaming events."
echo ""
