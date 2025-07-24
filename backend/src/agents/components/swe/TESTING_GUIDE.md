# SWE Agent Testing Guide 🧪

Complete guide for testing the SWE (Software Engineering) agents with GitHub workflows and Daytona integration.

## 🚀 Quick Start

### Prerequisites
- Daytona API key (`DAYTONA_API_KEY`)
- SambaNova API key (`SAMBANOVA_API_KEY`) 
- Redis running locally or connection string
- GitHub repository access (for real testing)

### Test the Integration

```bash
cd backend
source .venv/bin/activate
cd src
python agents/components/swe/test_integration.py
```

## 🔧 Integration with Main Agent

### 1. Add to WebSocket Manager

In your `websocket_manager.py`, add the SWE subgraph to your config:

```python
from agents.components.swe.swe_subgraph import get_swe_subgraph_config

# In your config creation:
"swe_agent": get_swe_subgraph_config(
    user_id=user_id,
    sambanova_api_key=api_keys.sambanova_key,
    redis_storage=self.message_storage,
    daytona_manager=daytona_manager,
),
```

### 2. Usage in Chat

Users can now trigger the SWE agent with:

```
<subgraph>swe_agent</subgraph>
<subgraph_input>
Add user authentication to the login form with email validation and password strength requirements
</subgraph_input>
```

## 📋 Testing Scenarios

### A. GitHub Issue Workflows

#### **Scenario 1: Feature Implementation**
```
**Issue:** Add dark mode toggle to settings page

**Requirements:**
- Add toggle switch in settings
- Store preference in localStorage
- Apply theme across all components
- Add smooth transitions

**Expected SWE Agent Actions:**
1. Analyze existing theme structure
2. Identify components that need updates
3. Create implementation plan
4. Generate code changes
5. Test in Daytona sandbox
```

#### **Scenario 2: Bug Fix**
```
**Issue:** Memory leak in dashboard component

**Description:**
Users report browser slowdown after 10+ minutes on dashboard.
Suspected memory leak in real-time data updates.

**Expected SWE Agent Actions:**
1. Analyze dashboard component code
2. Identify potential memory leaks
3. Review event listeners and subscriptions
4. Propose cleanup solutions
5. Test memory usage improvements
```

### B. Pull Request Review Workflows

#### **Scenario 1: Security Review**
```
**PR:** Payment processing refactor

**Changes:**
- Updated payment validation
- Added encryption for sensitive data
- Modified API endpoints

**SWE Agent Review Focus:**
- Security vulnerabilities
- Input validation
- Error handling
- PCI compliance considerations
```

#### **Scenario 2: Performance Review**
```
**PR:** Database query optimization

**Changes:**
- Refactored N+1 queries
- Added database indexing
- Implemented query caching

**SWE Agent Review Focus:**
- Query efficiency
- Index usage
- Caching strategy
- Performance benchmarks
```

### C. Codebase Analysis Workflows

#### **Scenario 1: Technical Debt Assessment**
```
**Request:** Analyze and prioritize technical debt

**SWE Agent Actions:**
1. Scan codebase for code smells
2. Identify duplication patterns
3. Analyze test coverage gaps
4. Prioritize refactoring opportunities
5. Generate improvement roadmap
```

#### **Scenario 2: Migration Planning**
```
**Request:** Plan React class components to hooks migration

**SWE Agent Actions:**
1. Identify all class components
2. Analyze component complexity
3. Determine migration order
4. Generate migration plan
5. Create example conversions
```

## 🧪 Real-World Testing Steps

### Step 1: Environment Setup

```bash
# 1. Clone a test repository
git clone https://github.com/your-org/test-project.git
cd test-project

# 2. Set environment variables
export SAMBANOVA_API_KEY="your_key_here"
export DAYTONA_API_KEY="your_key_here"  
export REDIS_URL="redis://localhost:6379"

# 3. Start your application
cd samba-co-pilot/backend
source .venv/bin/activate
uvicorn src.agents.api.main:app --reload
```

### Step 2: Test via Frontend

1. **Open your frontend application**
2. **Start a new conversation**
3. **Use the SWE agent for real tasks:**

```
Hey, can you help me implement a feature request?

<subgraph>swe_agent</subgraph>
<subgraph_input>
I need to add a user profile settings page to my React app. 

Requirements:
- Form with name, email, avatar upload
- Save to localStorage and API
- Validation for all fields
- Loading states during save

Current structure:
- src/components/ (existing components)
- src/hooks/ (custom hooks)
- src/services/ (API calls)
- src/utils/ (utilities)

Please analyze the codebase and create an implementation plan.
</subgraph_input>
```

### Step 3: Advanced Testing

#### **Test with Real GitHub Issues**

1. **Connect to a real repository:**
```python
# In test_integration.py, modify to use real repo
repo_path = "./path/to/your/repo"
github_issue = """
Real issue copied from GitHub:
- Issue title
- Full description  
- Acceptance criteria
- Related files
"""
```

2. **Test code generation in Daytona:**
   - SWE agent will analyze your real codebase
   - Generate actual code changes
   - Test in sandbox before applying

#### **Test with Complex Scenarios**

```
<subgraph>swe_agent</subgraph>
<subgraph_input>
Multi-step refactoring task:

1. Convert all class components to functional components with hooks
2. Implement proper error boundaries
3. Add TypeScript strict mode compliance
4. Update all unit tests

Repository: ./my-react-app
Focus on: src/components/legacy/

Please create a detailed implementation plan and start with the most critical components.
</subgraph_input>
```

## 📊 Testing Checklist

### ✅ Basic Functionality
- [ ] SWE subgraph imports successfully
- [ ] Can create Daytona manager
- [ ] Can initialize agent with API keys
- [ ] Basic tool invocation works

### ✅ Code Analysis
- [ ] Can analyze codebase structure
- [ ] Can search for patterns in code
- [ ] Can read and understand files
- [ ] Can identify dependencies

### ✅ Implementation Planning
- [ ] Generates logical implementation plans
- [ ] Breaks down complex tasks
- [ ] Considers existing code patterns
- [ ] Identifies affected files

### ✅ Code Generation
- [ ] Generates syntactically correct code
- [ ] Follows existing code style
- [ ] Includes proper error handling
- [ ] Adds appropriate tests

### ✅ Daytona Integration
- [ ] Can execute code in sandbox
- [ ] Can run tests and validations
- [ ] Can install packages
- [ ] Can read/write files safely

## 🐛 Troubleshooting

### Common Issues

1. **Import Errors**
   ```bash
   # Make sure you're in the right environment
   cd backend
   source .venv/bin/activate
   cd src
   ```

2. **Missing Dependencies**
   ```bash
   # Reinstall if needed
   uv sync
   ```

3. **Daytona Connection Issues**
   ```bash
   # Check API key
   echo $DAYTONA_API_KEY
   # Test connection manually
   ```

4. **Redis Connection Issues**
   ```bash
   # Start Redis locally
   redis-server
   # Or use Docker
   docker run -d -p 6379:6379 redis:alpine
   ```

### Debug Mode

Add debug logging to see what's happening:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Run your test
python test_integration.py
```

## 🎯 Production Usage

### Best Practices

1. **Repository Access**
   - Clone repos to Daytona workspace
   - Use git integration for version control
   - Implement proper backup strategies

2. **Security**
   - Validate all code changes
   - Use sandboxed execution
   - Implement approval workflows

3. **Performance**
   - Cache analysis results
   - Limit scope for large codebases
   - Use incremental analysis

4. **Monitoring**
   - Track agent performance
   - Monitor Daytona resource usage
   - Log all code changes

## 🚀 Next Steps

1. **Test with your real codebase**
2. **Create custom prompts for your workflow**
3. **Integrate with CI/CD pipelines**
4. **Set up automated testing**
5. **Monitor and optimize performance**

---

**Happy Testing!** 🎉

For issues or questions, check the logs and ensure all environment variables are set correctly. 