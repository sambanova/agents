"""
SWE Agent Integration Patch for WebSocket Manager
Add this code to your websocket_manager.py to enable SWE capabilities
"""

# 1. ADD IMPORT at the top of websocket_manager.py
from agents.components.swe.swe_subgraph import get_swe_subgraph_config

# 2. ADD TO YOUR CONFIG CREATION (around line 650-750 in websocket_manager.py)
# Add this to your config["configurable"]["type==default/subgraphs"] dictionary:

swe_subgraph_config = {
    "swe_agent": get_swe_subgraph_config(
        user_id=user_id,
        sambanova_api_key=api_keys.sambanova_key,
        redis_storage=self.message_storage,
        daytona_manager=daytona_manager,  # Use existing daytona_manager
    ),
}

# Example of complete subgraph configuration:
config["configurable"]["type==default/subgraphs"] = {
    "financial_analysis": {
        "description": "This subgraph is used to analyze financial data...",
        "next_node": END,
        "graph": create_financial_analysis_graph(self.redis_client),
        "state_input_mapper": lambda x: [HumanMessage(content=x)],
        "state_output_mapper": lambda x: x[-1],
    },
    "deep_research": {
        "description": "This subgraph generates comprehensive research reports...",
        "next_node": END,
        "graph": create_deep_research_graph(...),
        "state_input_mapper": lambda x: {"topic": x},
        "state_output_mapper": lambda x: AIMessage(...),
    },
    "DaytonaCodeSandbox": {
        "description": "This subgraph executes Python code...",
        "next_node": "agent",
        "graph": create_code_execution_graph(...),
        "state_input_mapper": lambda x: {...},
        "state_output_mapper": lambda x: LiberalFunctionMessage(...),
    },
    # ADD THIS NEW SUBGRAPH:
    **swe_subgraph_config,
}

# 3. USAGE EXAMPLES FOR USERS

# Users can now trigger the SWE agent in chat like this:

example_usage = """
<subgraph>swe_agent</subgraph>
<subgraph_input>
Add user authentication to the login form with the following requirements:
- Email validation
- Password strength requirements  
- Error handling for invalid credentials
- Loading states during authentication

Files that need to be modified:
- src/components/LoginForm.tsx
- src/utils/validation.ts
- src/hooks/useAuth.ts

Please analyze the current codebase and create an implementation plan.
</subgraph_input>
"""

github_issue_example = """
<subgraph>swe_agent</subgraph>
<subgraph_input>
GitHub Issue #123: Memory leak in dashboard component

Description: Users report browser slowdown after 10+ minutes on dashboard.
We suspect a memory leak in the real-time data updates.

Please:
1. Analyze the dashboard component for memory leaks
2. Identify problematic event listeners or subscriptions
3. Propose cleanup solutions
4. Test the fixes in the sandbox

Affected files: src/components/Dashboard.tsx, src/hooks/useRealTimeData.ts
</subgraph_input>
"""

pr_review_example = """
<subgraph>swe_agent</subgraph>
<subgraph_input>
Please review this pull request:

PR: Payment processing refactor #456
Files changed:
- src/services/PaymentService.ts
- src/components/CheckoutForm.tsx  
- tests/payment.test.ts

Focus on:
- Security vulnerabilities
- Error handling patterns
- Code quality improvements
- Performance considerations

Provide specific recommendations for each concern.
</subgraph_input>
"""

print("🎯 Integration patch ready!")
print("Copy the import and subgraph config to your websocket_manager.py")
print("Users can then use the SWE agent with the examples above.") 