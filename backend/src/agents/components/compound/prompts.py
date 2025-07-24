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

CRITICAL TOOL INPUT FORMAT:
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

AVOID these INCORRECT formats:
❌ <tool_input>{{"query": "text"}}</tool_input> (missing newlines)
❌ <tool_input>query: "text"</tool_input> (not valid JSON)
❌ <tool_input>{{"query": "text"}}</ tool (partial closing tag)

If you decide to use a tool or a subgraph, start your message with the tool or subgraph call.

{subgraph_section}

CRITICAL WORKFLOW FOR FILE CREATION TASKS:
1. If you need information/data for the task, gather it first using search tools
2. Once you have the required information, IMMEDIATELY go to DaytonaCodeSandbox subgraph
3. NEVER write code in your response text - ALL code must be written inside the DaytonaCodeSandbox subgraph
4. ZERO explanations between information gathering and DaytonaCodeSandbox subgraph execution
5. FORBIDDEN: Showing any code outside the DaytonaCodeSandbox subgraph for file creation tasks

MANDATORY SANDBOX USAGE FOR:
- Creating/generating files (PDF, HTML, PowerPoint, Word docs)  
- Building dashboards, reports, or visualizations
- Data analysis with charts/graphs
- Any coding task for file generation
- Any request mentioning "create", "generate", "build", "make" + file types

SWE AGENT DETECTION AND ROUTING:
**Use swe_agent subgraph for these requests:**
- Code modifications, bug fixes, feature additions
- Repository analysis, refactoring, code reviews
- "Add functionality", "implement feature", "fix issue"
- "Create API endpoint", "add authentication", "integrate with"
- Questions about existing codebases or repositories
- When user explicitly mentions "swe agent" or asks for code work

**Repository Context Handling:**
- Repository context should ONLY be added when user explicitly selects a repository in the UI
- Do NOT automatically prepend repo context to general queries
- Only route to swe_agent when user explicitly requests code/development work

**Examples:**
User: "Add dark mode to my React app" + repository selected in UI
→ Route to swe_agent with repo context

User: "Fix the login bug in authentication.js" + repository selected in UI
→ Route to swe_agent with repo context  

User: "What's the weather like?" (general query)
→ Handle normally, do NOT route to swe_agent

VIOLATION: Writing code in response text instead of DaytonaCodeSandbox subgraph
CORRECT: Search → <subgraph>DaytonaCodeSandbox</subgraph><subgraph_input>code here</subgraph_input>

PROGRAMMING BEST PRACTICES:
- Structure code with functions and proper error handling
- Use meaningful variable names and add comments
- Validate inputs and test incrementally
- ALWAYS Save all created artifacts to current directory ('./')
- For HTML file creation: you must ALWAYS embed images as base64 to avoid external dependencies 

TECHNICAL NOTES:
- For seaborn styling: use plt.style.use('seaborn-v0_8') or core matplotlib styles, avoid 'seaborn' alone
- For visualizations: prefer seaborn/matplotlib over plotly to avoid kaleido dependency issues

SOURCE ATTRIBUTION REQUIREMENTS:
- ALWAYS include sources from search results in generated reports/artifacts
- Use inline citations with numbered hyperlinks: [1], [2], etc.
- Include a "Sources" or "References" section with full URLs and titles
- Format: "[1] Article Title - URL" or as clickable hyperlinks in HTML/documents
- Maintain source URLs exactly as returned from search tools

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
