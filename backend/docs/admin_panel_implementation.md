# Admin Panel for LLM Provider Configuration

## Overview
This implementation adds a dynamic admin panel that allows users to switch between different LLM providers (SambaNova, Fireworks AI, Together AI) and configure specific models for different tasks/agents in the system.

## Key Features

### 1. Environment Variable Control
- **`SHOW_ADMIN_PANEL=true/false`** - Controls admin panel visibility
- When `false` (default): System uses default SambaNova configuration
- When `true`: Admin panel is accessible and users can configure providers

### 2. Dynamic Provider Support
- **SambaNova** (default)
- **Fireworks AI**
- **Together AI**

### 3. No API Keys in Environment
- API keys are passed dynamically from frontend
- Each user provides their own API keys
- Keys are not stored in environment variables for security

## Architecture

### Backend Components

#### 1. Configuration Manager (`backend/src/agents/config/llm_config_manager.py`)
- Manages LLM provider configurations
- Supports user-specific overrides
- Default configurations for all tasks/agents
- No API key storage - keys passed at runtime

#### 2. LLM Provider Utility (`backend/src/agents/utils/llm_provider.py`)
- Unified interface for multiple providers
- Dynamic provider selection
- Handles API key injection
- Support for both LangChain and CrewAI

#### 3. Admin API Routes (`backend/src/agents/api/routers/admin.py`)
- `/admin/status` - Check if admin panel is enabled
- `/admin/config` - Get/update configuration
- `/admin/providers` - List available providers
- `/admin/models/{provider}` - List models for a provider
- `/admin/tasks` - List configurable tasks
- `/admin/test-connection` - Test provider connectivity

### Frontend Components

#### Admin Panel Vue Component
- Located in: `frontend/sales-agent-crew/src/components/AdminPanel.vue`
- Features:
  - Provider selection
  - API key management (with visibility toggle)
  - Task-specific model configuration
  - Connection testing
  - Configuration persistence

### Updated Agents

#### 1. Data Science Subgraph (`data_science_subgraph.py`)
```python
# Automatically uses config system when admin panel is enabled
if CONFIG_SYSTEM_AVAILABLE and admin_enabled and user_id:
    # Use configured providers
else:
    # Use default SambaNova
```

#### 2. Enhanced Agent (`enhanced_agent.py`)
- Backward compatible
- Checks for admin panel status
- Falls back to default when disabled

#### 3. Financial Analysis Crew
- Supports dynamic provider switching
- Maintains backward compatibility

## Configuration Structure

### Default Task Models
```yaml
task_models:
  main_agent:
    provider: sambanova
    model: DeepSeek-V3-0324
  data_science_agent:
    provider: sambanova
    model: DeepSeek-V3-0324
  vision_agent:
    provider: sambanova
    model: Llama-4-Maverick-17B-128E-Instruct
  # ... more tasks
```

### Provider Models
- **SambaNova**: DeepSeek V3, Llama 3.3, Llama 4 Maverick, GPT OSS 120B
- **Fireworks**: Llama 3.3, DeepSeek V3/R1, Qwen 2.5
- **Together**: Llama 3.3, DeepSeek V3/R1, Qwen 2.5

## Usage

### 1. Enable Admin Panel
```bash
export SHOW_ADMIN_PANEL=true
```

### 2. Access Admin Panel
- Navigate to Settings in the frontend
- Admin Panel tab will be visible
- Enter API keys for desired providers

### 3. Configure Models
- Select default provider
- Configure specific models for each task
- Test connections
- Save configuration

### 4. Runtime Behavior
- When admin panel is **enabled**: Uses user-configured providers
- When admin panel is **disabled**: Uses default SambaNova configuration
- API keys are passed with each request from frontend

## Security Considerations

1. **No API Keys in Environment**: Keys are user-specific and passed dynamically
2. **User Isolation**: Each user's configuration is separate
3. **Default Fallback**: System always falls back to SambaNova if configuration fails
4. **Admin Panel Access**: Controlled by environment variable

## Backward Compatibility

The implementation maintains full backward compatibility:
- Existing code continues to work unchanged
- Admin panel is opt-in via environment variable
- Default behavior remains SambaNova-only
- Gradual migration path for existing deployments

## Testing

### Test Scenarios
1. **Admin Panel Disabled**: Verify default SambaNova configuration
2. **Admin Panel Enabled**: Test provider switching
3. **API Key Validation**: Test connection endpoint
4. **Model Selection**: Verify task-specific models
5. **Fallback Behavior**: Test with invalid configurations

### Example Test
```bash
# Enable admin panel
export SHOW_ADMIN_PANEL=true

# Start backend
python -m agents.api.main

# Frontend will show admin panel in settings
# Configure providers and test
```

## Future Enhancements

1. **Model Discovery**: Auto-discover available models from providers
2. **Cost Tracking**: Track usage and costs per provider
3. **Performance Metrics**: Compare provider response times
4. **Bulk Configuration**: Import/export configurations
5. **Team Settings**: Share configurations across team members