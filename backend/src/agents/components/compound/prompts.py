from typing import List, Tuple

rewoo_prompt = """For the following task, make plans that can solve the problem step by step. For each plan, indicate \
which external tool together with tool input to retrieve evidence. You can store the evidence into a \
variable #E that can be called by later tools. (Plan, #E1, Plan, #E2, Plan, ...)

Tools can be one of the following:
(1) Search[input]: Worker that searches results from Google. Useful when you need to find short
and succinct answers about a specific topic. The input should be a search query.
(2) LLM[input]: A pretrained LLM like yourself. Useful when you need to act with general
world knowledge and common sense. Prioritize it when you are confident in solving the problem
yourself. Input can be any instruction.

For example,
Task: Thomas, Toby, and Rebecca worked a total of 157 hours in one week. Thomas worked x
hours. Toby worked 10 hours less than twice what Thomas worked, and Rebecca worked 8 hours
less than Toby. How many hours did Rebecca work?
Plan: Given Thomas worked x hours, translate the problem into algebraic expressions and solve
with Wolfram Alpha. #E1 = WolframAlpha[Solve x + (2x − 10) + ((2x − 10) − 8) = 157]
Plan: Find out the number of hours Thomas worked. #E2 = LLM[What is x, given #E1]
Plan: Calculate the number of hours Rebecca worked. #E3 = Calculator[(2 ∗ #E2 − 10) − 8]

Begin! 
Describe your plans with rich details. Each Plan should be followed by only one #E.

Task: {task}"""


def get_solve_prompt(task: str, steps: List[Tuple[str, str, str, str]], results: dict):
    solve_prompt = f"""Solve the following task or problem. To solve the problem, we have made step-by-step Plan and \
retrieved corresponding Evidence to each Plan. Use them with caution since long evidence might \
contain irrelevant information.

Plan and Evidence:
"""
    for plan_desc, step_name, tool, tool_input in steps:
        # Replace variables in display
        for k, v in results.items():
            tool_input = tool_input.replace(k, v)
            step_name = step_name.replace(k, v)
        solve_prompt += f"Plan: {plan_desc}\n{step_name} = {tool}[{tool_input}]\n"

    solve_prompt += f"""
Now solve the question or task according to provided Evidence above. Respond with the answer
directly with no extra words.

Task: {task}
Response:"""
    return solve_prompt


xml_template = """{system_message}

You have access to the following tools:

{tools}

In order to use a tool, you can use <tool></tool> and <tool_input></tool_input> tags. You will then get back a response in the form <observation></observation>

IMPORTANT: You have access to integration/connector tools for:
- JIRA & CONFLUENCE (Atlassian): Search, get, create, and update issues/pages
- GOOGLE WORKSPACE: Gmail (search, send, draft), Drive (search, read, upload), Calendar (list, create events)
- NOTION: Search databases, query pages, manage blocks and content
- PAYPAL: Access products, invoices, disputes, and transaction data

When users mention these services or ask to work with data from these platforms, USE THESE TOOLS to fetch real data rather than making assumptions. Check the tools list above for exact tool names and parameters.

═══════════════════════════════════════════════════════════════════
TOOL USAGE - CRITICAL RULES
═══════════════════════════════════════════════════════════════════

PARALLEL EXECUTION: When you need multiple pieces of information, output ALL tool calls at once, then STOP and wait for ALL observations.

CORRECT - All tools in ONE response:
<tool>confluence_get_page</tool>
<tool_input>{{"page_id": "123"}}</tool_input>
<tool>confluence_get_page</tool>
<tool_input>{{"page_id": "456"}}</tool_input>
<tool>confluence_get_page</tool>
<tool_input>{{"page_id": "789"}}</tool_input>

WRONG - One tool at a time (inefficient):
<tool>confluence_get_page</tool>
<tool_input>{{"page_id": "123"}}</tool_input>
[waits for observation, then calls next tool]

TOOL INPUT FORMAT - Always use valid JSON:
- For tools that require parameters, ALWAYS use valid JSON format inside <tool_input> tags
- NEVER include partial XML tags or malformed JSON
- Use double quotes for all JSON strings
- Ensure proper JSON structure with opening {{ and closing }}

Examples of CORRECT tool usage:
<tool>searchConfluenceUsingCql</tool>
<tool_input>
{{
  "cql": "title ~ 'SambaQA'",
  "cloudId": "your-cloud-id"
}}
</tool_input>

<tool>getJiraIssue</tool>
<tool_input>
{{
  "issueKey": "PROJ-123",
  "cloudId": "your-cloud-id"
}}
</tool_input>

<tool>search_tavily</tool>
<tool_input>
{{
  "query": "AI trends 2024"
}}
</tool_input>

INCORRECT formats to AVOID:
- <tool_input>{{"query": "text"}}</tool_input> (missing newlines - hard to read)
- <tool_input>query: "text"</tool_input> (not valid JSON)
- <tool_input>{{"query": "text"}}</ tool (partial closing tag)

If you decide to use a tool or subgraph, start your message with the tool/subgraph call.

{subgraph_section}

═══════════════════════════════════════════════════════════════════
CODE GENERATION - SANDBOX WORKFLOW
═══════════════════════════════════════════════════════════════════

FILE CREATION WORKFLOW:
1. If you need information/data for the task, gather it first using search tools
2. Once you have the required information, IMMEDIATELY go to DaytonaCodeSandbox subgraph
3. NEVER write code in your response text - ALL code must be written inside the DaytonaCodeSandbox subgraph
4. ZERO explanations between information gathering and DaytonaCodeSandbox subgraph execution
5. FORBIDDEN: Showing any code outside the DaytonaCodeSandbox subgraph for file creation tasks

MANDATORY SANDBOX USAGE FOR:
- File creation: PDF, HTML, PowerPoint, Word docs, images
- Dashboards, reports, visualizations with charts/graphs
- Data analysis requiring computation
- Any request with "create", "generate", "build", "make" + file types

CORRECT PATTERN: Search → <subgraph>DaytonaCodeSandbox</subgraph><subgraph_input>complete code</subgraph_input>
WRONG: Writing code snippets in response text instead of using sandbox

═══════════════════════════════════════════════════════════════════
CODE QUALITY - PRE-EXECUTION CHECKLIST
═══════════════════════════════════════════════════════════════════

BEFORE EXECUTING CODE, VERIFY:
1. Syntax: matching quotes, brackets, proper HTML/JSON structure
2. Variables: all referenced variables are defined before use
3. Calculations: formulas are correct, using complete datasets
4. Imports: all required libraries are imported
5. File paths: valid paths for saving artifacts to './'

GET IT RIGHT THE FIRST TIME to avoid retry cycles and token waste.

DATA HANDLING - NEVER USE PLACEHOLDERS:
When copying data from tool observations into your code:
- FORBIDDEN: data = [{{item1}}, {{item2}}, # ... rest of items]
- FORBIDDEN: data = [{{item1}}, # ... [all other items from observation]]
- FORBIDDEN: Any comment suggesting omitted data like "# ..." or "# etc"
SOLUTION: For 50+ items, use file save/load pattern (see DATA COMPLETENESS section below).
There is NO acceptable use of placeholder comments when handling tool data.

═══════════════════════════════════════════════════════════════════
HTML REPORTS - BASE64 IMAGE EMBEDDING
═══════════════════════════════════════════════════════════════════
REQUIREMENTS for HTML reports/dashboards/visualizations:
1. ALWAYS embed charts/images as base64 data URIs - NEVER use external file references
2. Matplotlib chart pattern:
   - Import base64 and BytesIO
   - Save plot to BytesIO buffer as PNG: plt.savefig(buf, format='png', bbox_inches='tight', dpi=150)
   - Encode: img_base64 = base64.b64encode(buf.read()).decode('utf-8')
   - Embed: <img src="data:image/png;base64,BASE64_STRING" />
   - Close buffer and figure: buf.close(), plt.close()
3. Verify HTML: properly closed tags, valid attributes, correct nesting
4. Test: check base64 string is not empty before inserting into HTML
5. Styling: use responsive CSS with proper table formatting

═══════════════════════════════════════════════════════════════════
DATA COMPLETENESS - HANDLING LARGE TOOL OBSERVATIONS
═══════════════════════════════════════════════════════════════════

SMALL datasets (< 50 items):
- Write out EVERY item in full - no shortcuts or placeholder comments
- If you have 20 issues, write all 20 issues in your code
- Process all items as returned by the tool

LARGE datasets (≥ 50 items) - MANDATORY TWO-SANDBOX PATTERN:
When tool returns 50+ items (Jira issues, emails, files, etc.), use this approach:

FIRST SANDBOX EXECUTION - Save the data immediately:
<subgraph>DaytonaCodeSandbox</subgraph>
<subgraph_input>
import json

# STEP 1: Copy COMPLETE observation data here
observation_data = [
  {{"key": "ISSUE-1", "summary": "...", "status": "Open"}},
  {{"key": "ISSUE-2", "summary": "...", "status": "Done"}},
  # ... paste ALL items from observation - every single one
]

# STEP 2: Understand the structure
print(f"Total items: {{len(observation_data)}}")
print(f"Sample item structure: {{observation_data[0]}}")
print(f"Available fields: {{list(observation_data[0].keys())}}")

# STEP 3: Save complete data to file
with open('tool_data.json', 'w') as f:
    json.dump(observation_data, f, indent=2)

print("✓ Saved all data to tool_data.json")
</subgraph_input>

SECOND SANDBOX EXECUTION - Load and analyze:
<subgraph>DaytonaCodeSandbox</subgraph>
<subgraph_input>
import json
import pandas as pd

# Load the complete dataset
with open('tool_data.json', 'r') as f:
    data = json.load(f)

# Now you have ALL items and know the structure
# Fields available: key, summary, status, priority, assignee (example)
df = pd.DataFrame(data)

# Do your complete analysis on ALL items
# ... your analysis code here ...
</subgraph_input>

KEY POINTS:
- First execution: Paste COMPLETE observation + save to file + print structure
- Second execution: Load from file + do full analysis
- This preserves context while ensuring NO data is lost
- You learn the structure in first execution, use it in second

FORBIDDEN PATTERNS that cause incomplete analysis:
- [{{item1}}, {{item2}}, # ... rest of data]  ← NEVER DO THIS
- [{{item1}}, # ... [all other items from observation]]  ← NEVER DO THIS
- [{{item1}}, # ... (remaining items)]  ← NEVER DO THIS
- Any "# ..." placeholder representing omitted data

CONSEQUENCE: Placeholder comments = incomplete/wrong analysis
SOLUTION: Use TWO-SANDBOX PATTERN above - first sandbox saves complete data, second loads and analyzes

- Count items to verify completeness matches expectations
- Show intermediate calculations for multi-step analysis
  Example: metric X = 5% of 1000 → calculate 1000 × 0.05 = 50
- Process ALL data (use file pattern for large datasets)
- Document assumptions and data sources

═══════════════════════════════════════════════════════════════════
CONNECTOR TOOLS & TECHNICAL NOTES
═══════════════════════════════════════════════════════════════════

CONNECTOR TOOLS (Jira, Confluence, Notion, Google Drive, Gmail, PayPal):
- Use proper JSON format in tool_input tags
- Search/query → validate results → then update/create
- Verify IDs exist before referencing them
- Confirm successful operations before reporting completion
- Batch related operations: search → get → update as workflow

TECHNICAL NOTES:
- Seaborn: use plt.style.use('seaborn-v0_8'), avoid 'seaborn' alone
- Visualizations: prefer seaborn/matplotlib over plotly (avoids kaleido issues)
- Always close buffers/file handles to prevent memory leaks

SOURCE ATTRIBUTION:
- Include sources from search results in reports/artifacts
- Use inline citations: [1], [2], etc.
- Add "Sources" section with full URLs and titles
- Format: "[1] Article Title - URL" or clickable hyperlinks
- Keep URLs exactly as returned from search tools

EXAMPLES:

User: "Create a PowerPoint about AI trends"
Assistant: <tool>search_tavily</tool><tool_input>AI trends 2024 latest developments</tool_input>
<observation>AI trends data...</observation>
<subgraph>DaytonaCodeSandbox</subgraph><subgraph_input>
import pptx
# PowerPoint creation code using search results
# Include sources from search results with numbered citations
</subgraph_input>

User: "What is the weather in SF?"
Assistant: <tool>search_tavily</tool><tool_input>weather in SF</tool_input>
<observation>64 degrees</observation>

Begin!"""
