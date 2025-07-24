"""
Test integration script for SWE subgraph.
This demonstrates how to use the SWE agents with GitHub repositories.
"""

import asyncio
import os
from typing import Dict, Any

from agents.components.swe.swe_subgraph import get_swe_subgraph_config
from agents.components.datagen.tools.persistent_daytona import PersistentDaytonaManager
from agents.storage.redis_storage import RedisStorage
from agents.storage.redis_service import SecureRedisService
from agents.components.compound.xml_agent import get_xml_agent_executor
from agents.components.compound.data_types import LLMType
from langchain_core.messages import HumanMessage
import redis


async def test_swe_integration():
    """Test the SWE subgraph integration"""
    
    # Mock configuration (replace with real values for testing)
    user_id = "test_user_123"
    sambanova_api_key = os.getenv("SAMBANOVA_API_KEY", "your_api_key_here")
    
    # Initialize Redis storage (you might need to adjust this)
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    secure_redis_service = SecureRedisService.from_url(redis_url)
    redis_storage = RedisStorage(redis_client=secure_redis_service)
    
    # Create Daytona manager for SWE operations
    daytona_manager = PersistentDaytonaManager(
        user_id=user_id,
        redis_storage=redis_storage,
        snapshot="data-analysis:0.0.10",  # or "swe-agent:latest" if available
    )
    
    # Get SWE subgraph configuration
    swe_config = get_swe_subgraph_config(
        user_id=user_id,
        sambanova_api_key=sambanova_api_key,
        redis_storage=redis_storage,
        daytona_manager=daytona_manager,
    )
    
    print("✅ SWE subgraph configuration created successfully!")
    print(f"Description: {swe_config['description']}")
    
    return swe_config


async def test_swe_with_xml_agent():
    """Test SWE integration with the main XML agent"""
    
    user_id = "test_user_123"
    sambanova_api_key = os.getenv("SAMBANOVA_API_KEY", "your_api_key_here")
    
    # Initialize storage
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    secure_redis_service = SecureRedisService.from_url(redis_url)
    redis_storage = RedisStorage(redis_client=secure_redis_service)
    
    # Create Daytona manager
    daytona_manager = PersistentDaytonaManager(
        user_id=user_id,
        redis_storage=redis_storage,
        snapshot="data-analysis:0.0.10",
    )
    
    # Create XML agent with SWE subgraph
    subgraphs = {
        "swe_agent": get_swe_subgraph_config(
            user_id=user_id,
            sambanova_api_key=sambanova_api_key,
            redis_storage=redis_storage,
            daytona_manager=daytona_manager,
        )
    }
    
    # Create the main agent
    agent = get_xml_agent_executor(
        tools=[],  # Add any additional tools needed
        llm=lambda api_key: None,  # Will be created by the agent
        llm_type=LLMType.SN_DEEPSEEK_V3,
        system_message="You are a helpful assistant with software engineering capabilities.",
        subgraphs=subgraphs,
        user_id=user_id,
    )
    
    print("✅ XML agent with SWE subgraph created successfully!")
    return agent


async def simulate_github_issue_workflow():
    """Simulate handling a GitHub issue with the SWE agent"""
    
    # Example GitHub issue scenario
    github_issue = """
    **Issue:** Add user authentication to the login form
    
    **Description:** 
    The current login form doesn't have proper validation. We need to:
    1. Add email format validation
    2. Add password strength requirements  
    3. Add error handling for invalid credentials
    4. Add loading states during authentication
    
    **Files to modify:**
    - `src/components/LoginForm.tsx`
    - `src/utils/validation.ts`
    - `src/hooks/useAuth.ts`
    
    **Acceptance Criteria:**
    - Email must be valid format
    - Password must be at least 8 characters
    - Show appropriate error messages
    - Loading indicator during API calls
    """
    
    # This would be passed to the SWE agent
    swe_input = f"""
    <subgraph>swe_agent</subgraph>
    <subgraph_input>{github_issue}</subgraph_input>
    """
    
    print("🔄 GitHub Issue Workflow Simulation")
    print("="*50)
    print("Issue:", github_issue[:100] + "...")
    print("SWE Input:", swe_input[:100] + "...")
    print("\n✅ This would trigger the SWE agent to:")
    print("  1. Analyze the codebase structure")
    print("  2. Research existing authentication patterns")
    print("  3. Create implementation plan")
    print("  4. Generate code changes")
    print("  5. Execute tests in Daytona sandbox")
    
    return swe_input


async def simulate_pr_review_workflow():
    """Simulate handling a Pull Request review with the SWE agent"""
    
    pr_scenario = """
    **PR Review Request:** 
    Review and improve the payment processing module
    
    **Changes:**
    - Modified `src/services/PaymentService.ts`
    - Updated `src/components/CheckoutForm.tsx`
    - Added new tests in `tests/payment.test.ts`
    
    **Review Focus:**
    - Security vulnerabilities
    - Error handling
    - Code quality improvements
    - Performance optimizations
    """
    
    swe_input = f"""
    <subgraph>swe_agent</subgraph>
    <subgraph_input>
    Please review this PR and suggest improvements:
    {pr_scenario}
    
    Focus on security, error handling, and code quality.
    </subgraph_input>
    """
    
    print("🔍 PR Review Workflow Simulation")
    print("="*50)
    print("PR Scenario:", pr_scenario[:100] + "...")
    print("\n✅ This would trigger the SWE agent to:")
    print("  1. Analyze changed files")
    print("  2. Review code for security issues")
    print("  3. Check error handling patterns")
    print("  4. Suggest code improvements")
    print("  5. Run automated tests")
    
    return swe_input


def create_websocket_manager_integration():
    """
    Example of how to integrate SWE subgraph into your websocket manager.
    Add this to your websocket_manager.py config creation.
    """
    
    integration_code = '''
# In your websocket_manager.py, add this to the subgraph configuration:

"swe_agent": {
    "description": "Advanced software engineering agent that can analyze codebases, plan implementations, and automatically generate code changes. Use for: code implementation tasks, refactoring requests, feature additions, bug fixes, architectural changes, and any software development work that requires understanding existing code and making targeted modifications.",
    "next_node": "END",
    "graph": create_swe_graph(
        user_id=user_id,
        sambanova_api_key=api_keys.sambanova_key,
        redis_storage=self.message_storage,
        daytona_manager=daytona_manager,
    ),
    "state_input_mapper": swe_state_input_mapper,
    "state_output_mapper": swe_state_output_mapper,
},
'''
    
    print("📝 WebSocket Manager Integration Code:")
    print("="*50)
    print(integration_code)
    
    return integration_code


async def main():
    """Main test function"""
    print("🚀 SWE Subgraph Integration Testing")
    print("="*60)
    
    try:
        # Test 1: Basic integration
        print("\n1. Testing basic SWE subgraph configuration...")
        await test_swe_integration()
        
        # Test 2: XML agent integration
        print("\n2. Testing XML agent integration...")
        await test_swe_with_xml_agent()
        
        # Test 3: GitHub workflows
        print("\n3. Simulating GitHub Issue workflow...")
        await simulate_github_issue_workflow()
        
        print("\n4. Simulating PR Review workflow...")
        await simulate_pr_review_workflow()
        
        # Test 5: Integration guide
        print("\n5. WebSocket Manager integration:")
        create_websocket_manager_integration()
        
        print("\n🎉 All tests completed successfully!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main()) 