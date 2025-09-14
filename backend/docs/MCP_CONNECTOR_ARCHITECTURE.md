# MCP-Based Connector Architecture

## Overview

This document outlines the hybrid architecture for supporting both direct OAuth connectors and MCP (Model Context Protocol) based connectors via SSE (Server-Sent Events).

## Architecture Design

```
┌─────────────────────────────────────────────────────────┐
│                     Frontend (Vue.js)                    │
│                   Settings > Connected Apps              │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│                   Backend API Layer                      │
│                 /connectors endpoints                    │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│              Connector Manager (Unified)                 │
│  ┌──────────────────────┬────────────────────────────┐  │
│  │  Direct Connectors   │    MCP Connectors (New)    │  │
│  │  - Google            │    - Atlassian (Jira)      │  │
│  │  - Microsoft         │    - Atlassian (Confluence)│  │
│  │  - Slack             │    - GitHub                │  │
│  └──────────────────────┴────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                 │                        │
                 ▼                        ▼
    ┌─────────────────────┐   ┌─────────────────────────┐
    │   Direct OAuth API   │   │    MCP Server (SSE)     │
    │   - Immediate calls  │   │   - Remote execution    │
    │   - Token refresh    │   │   - OAuth via MCP       │
    └─────────────────────┘   └─────────────────────────┘
```

## Implementation Plan

### Phase 1: MCP Infrastructure

#### 1. Create MCP Base Connector
```python
# src/agents/connectors/core/mcp_connector.py
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import asyncio
import aiohttp
from aiohttp_sse_client import client as sse_client
import structlog

logger = structlog.get_logger(__name__)

class MCPConnector(BaseOAuthConnector):
    """
    Base class for MCP-based connectors
    Handles SSE communication and OAuth through MCP protocol
    """
    
    def __init__(self, config: MCPConfig, redis_storage: RedisStorage):
        super().__init__(config, redis_storage)
        self.mcp_server_url = config.mcp_server_url
        self.sse_client = None
        self.oauth_config = {
            "authorization_server": config.oauth_authorization_server,
            "resource_server": config.oauth_resource_server,
            "client_id": config.client_id,
            "redirect_uri": config.redirect_uri,
            "scopes": config.scopes,
            "use_pkce": True  # Required by MCP spec
        }
    
    async def connect_sse(self, user_id: str) -> None:
        """Establish SSE connection to MCP server"""
        token = await self.get_user_token(user_id)
        if not token:
            raise ValueError("No token available for MCP connection")
        
        headers = {
            "Authorization": f"Bearer {token.access_token}",
            "Accept": "text/event-stream"
        }
        
        async with sse_client.EventSource(
            self.mcp_server_url + "/sse",
            headers=headers
        ) as event_source:
            self.sse_client = event_source
            async for event in event_source:
                await self.handle_sse_event(event, user_id)
    
    async def handle_sse_event(self, event: Any, user_id: str) -> None:
        """Handle incoming SSE events from MCP server"""
        if event.type == "tool_response":
            # Handle tool execution response
            await self.process_tool_response(event.data, user_id)
        elif event.type == "oauth_required":
            # Handle OAuth re-authentication request
            await self.handle_oauth_refresh(event.data, user_id)
        elif event.type == "error":
            logger.error("MCP server error", error=event.data, user_id=user_id)
    
    async def execute_tool(self, user_id: str, tool_id: str, params: Dict[str, Any]) -> Any:
        """Execute a tool via MCP protocol"""
        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_id,
                "arguments": params
            },
            "id": f"{user_id}_{tool_id}_{asyncio.get_event_loop().time()}"
        }
        
        # Send request via HTTP POST
        async with aiohttp.ClientSession() as session:
            token = await self.get_user_token(user_id)
            headers = {
                "Authorization": f"Bearer {token.access_token}",
                "Content-Type": "application/json"
            }
            
            async with session.post(
                self.mcp_server_url + "/execute",
                json=request,
                headers=headers
            ) as response:
                return await response.json()
    
    async def get_authorization_url(self, user_id: str, state: Optional[str] = None, **kwargs) -> Tuple[str, str]:
        """
        Generate OAuth URL following MCP OAuth 2.1 spec
        """
        # MCP requires PKCE
        code_verifier = generate_token(48)
        code_challenge = create_s256_code_challenge(code_verifier)
        
        params = {
            "client_id": self.oauth_config["client_id"],
            "redirect_uri": self.oauth_config["redirect_uri"],
            "response_type": "code",
            "scope": " ".join(self.oauth_config["scopes"]),
            "state": state or secrets.token_urlsafe(32),
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            # MCP spec: Resource indicators (RFC 8707)
            "resource": self.oauth_config["resource_server"]
        }
        
        # Store state with code_verifier
        await self.store_oauth_state(state, user_id, code_verifier)
        
        auth_url = f"{self.oauth_config['authorization_server']}/authorize?" + urlencode(params)
        return auth_url, state
```

#### 2. Create Atlassian MCP Connector
```python
# src/agents/connectors/providers/atlassian/atlassian_mcp_connector.py
class AtlassianMCPConnector(MCPConnector):
    """
    Atlassian connector using MCP protocol
    Supports both Jira and Confluence through unified OAuth
    """
    
    def _get_metadata(self) -> ConnectorMetadata:
        return ConnectorMetadata(
            provider_id="atlassian",
            name="Atlassian (Jira & Confluence)",
            description="Connect to Jira and Confluence via MCP",
            icon_url="https://www.atlassian.com/favicon.ico",
            oauth_version=OAuthVersion.OAUTH2_0,
            connector_type=ConnectorType.MCP,  # New field
            available_tools=[
                # Jira Tools
                ConnectorTool(
                    id="jira_create_issue",
                    name="Create Jira Issue",
                    description="Create a new issue in Jira",
                    parameters_schema={
                        "type": "object",
                        "properties": {
                            "project": {"type": "string"},
                            "summary": {"type": "string"},
                            "description": {"type": "string"},
                            "issue_type": {"type": "string", "enum": ["Bug", "Task", "Story"]},
                            "priority": {"type": "string", "enum": ["Highest", "High", "Medium", "Low", "Lowest"]}
                        },
                        "required": ["project", "summary", "issue_type"]
                    }
                ),
                ConnectorTool(
                    id="jira_search_issues",
                    name="Search Jira Issues",
                    description="Search for issues using JQL",
                    parameters_schema={
                        "type": "object",
                        "properties": {
                            "jql": {"type": "string", "description": "JQL query"},
                            "max_results": {"type": "integer", "default": 10}
                        },
                        "required": ["jql"]
                    }
                ),
                ConnectorTool(
                    id="jira_update_issue",
                    name="Update Jira Issue",
                    description="Update an existing Jira issue",
                    parameters_schema={
                        "type": "object",
                        "properties": {
                            "issue_key": {"type": "string"},
                            "fields": {"type": "object"}
                        },
                        "required": ["issue_key", "fields"]
                    }
                ),
                # Confluence Tools
                ConnectorTool(
                    id="confluence_create_page",
                    name="Create Confluence Page",
                    description="Create a new page in Confluence",
                    parameters_schema={
                        "type": "object",
                        "properties": {
                            "space": {"type": "string"},
                            "title": {"type": "string"},
                            "content": {"type": "string"},
                            "parent_id": {"type": "string", "description": "Optional parent page ID"}
                        },
                        "required": ["space", "title", "content"]
                    }
                ),
                ConnectorTool(
                    id="confluence_search",
                    name="Search Confluence",
                    description="Search for pages and content in Confluence",
                    parameters_schema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "space": {"type": "string", "description": "Optional space key"},
                            "max_results": {"type": "integer", "default": 10}
                        },
                        "required": ["query"]
                    }
                ),
                ConnectorTool(
                    id="confluence_get_page",
                    name="Get Confluence Page",
                    description="Retrieve content of a Confluence page",
                    parameters_schema={
                        "type": "object",
                        "properties": {
                            "page_id": {"type": "string"}
                        },
                        "required": ["page_id"]
                    }
                )
            ]
        )
    
    async def create_langchain_tools(self, user_id: str, tool_ids: List[str]) -> List[BaseTool]:
        """Create LangChain tools that communicate via MCP"""
        from .atlassian_mcp_tools import create_atlassian_mcp_tools
        
        token = await self.get_user_token(user_id, auto_refresh=True)
        if not token:
            return []
        
        # For MCP connectors, tools are thin wrappers that send requests via MCP
        return create_atlassian_mcp_tools(
            mcp_connector=self,
            user_id=user_id,
            tool_ids=tool_ids,
            access_token=token.access_token
        )
```

#### 3. Create MCP Tool Wrappers
```python
# src/agents/connectors/providers/atlassian/atlassian_mcp_tools.py
from typing import List, Optional, Type
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

class MCPToolWrapper(BaseTool):
    """Base class for MCP-based tools"""
    
    mcp_connector: Any  # MCPConnector instance
    user_id: str
    tool_id: str
    
    async def _arun(self, **kwargs) -> str:
        """Execute tool via MCP protocol"""
        try:
            response = await self.mcp_connector.execute_tool(
                self.user_id,
                self.tool_id,
                kwargs
            )
            
            if response.get("error"):
                return f"Error: {response['error']['message']}"
            
            return response.get("result", "Tool executed successfully")
            
        except Exception as e:
            return f"Error executing MCP tool: {str(e)}"
    
    def _run(self, **kwargs) -> str:
        """Sync wrapper for async execution"""
        import asyncio
        return asyncio.run(self._arun(**kwargs))

class JiraCreateIssueInput(BaseModel):
    project: str = Field(description="Project key")
    summary: str = Field(description="Issue summary")
    description: str = Field(default="", description="Issue description")
    issue_type: str = Field(description="Issue type (Bug, Task, Story)")
    priority: str = Field(default="Medium", description="Priority level")

class JiraCreateIssueTool(MCPToolWrapper):
    name: str = "jira_create_issue"
    description: str = "Create a new issue in Jira"
    args_schema: Type[BaseModel] = JiraCreateIssueInput
    tool_id: str = "jira_create_issue"

# Similar for other tools...

def create_atlassian_mcp_tools(
    mcp_connector: Any,
    user_id: str,
    tool_ids: List[str],
    access_token: str
) -> List[BaseTool]:
    """Create MCP-wrapped tools for Atlassian"""
    tools = []
    
    tool_mapping = {
        'jira_create_issue': JiraCreateIssueTool,
        'jira_search_issues': JiraSearchIssuesTool,
        'jira_update_issue': JiraUpdateIssueTool,
        'confluence_create_page': ConfluenceCreatePageTool,
        'confluence_search': ConfluenceSearchTool,
        'confluence_get_page': ConfluenceGetPageTool,
    }
    
    for tool_id in tool_ids:
        if tool_id in tool_mapping:
            tool_class = tool_mapping[tool_id]
            tool = tool_class(
                mcp_connector=mcp_connector,
                user_id=user_id
            )
            tools.append(tool)
    
    return tools
```

### Phase 2: MCP Server Implementation

#### MCP Server for Atlassian (Separate Service)
```python
# mcp-server/atlassian_mcp_server.py
from fastapi import FastAPI, Request, Header
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
import httpx
from typing import Optional

app = FastAPI()

class AtlassianMCPServer:
    """
    MCP server that bridges to Atlassian APIs
    Can be deployed as a separate microservice or serverless function
    """
    
    def __init__(self):
        self.clients = {}  # user_id -> Atlassian client
    
    async def get_atlassian_client(self, access_token: str) -> httpx.AsyncClient:
        """Get or create Atlassian API client"""
        # Implementation details...
        pass
    
    @app.post("/execute")
    async def execute_tool(
        request: Request,
        authorization: str = Header()
    ):
        """Execute MCP tool request"""
        body = await request.json()
        method = body.get("method")
        params = body.get("params", {})
        
        # Extract token from Authorization header
        token = authorization.replace("Bearer ", "")
        
        # Route to appropriate handler
        if method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            
            # Execute tool based on name
            if tool_name.startswith("jira_"):
                result = await execute_jira_tool(token, tool_name, tool_args)
            elif tool_name.startswith("confluence_"):
                result = await execute_confluence_tool(token, tool_name, tool_args)
            else:
                result = {"error": {"message": f"Unknown tool: {tool_name}"}}
            
            return {
                "jsonrpc": "2.0",
                "result": result,
                "id": body.get("id")
            }
    
    @app.get("/sse")
    async def sse_endpoint(
        request: Request,
        authorization: str = Header()
    ):
        """SSE endpoint for real-time updates"""
        async def event_generator():
            while True:
                # Send keepalive
                yield {
                    "event": "ping",
                    "data": {"timestamp": datetime.now().isoformat()}
                }
                await asyncio.sleep(30)
        
        return EventSourceResponse(event_generator())
    
    async def execute_jira_tool(token: str, tool_name: str, args: dict) -> dict:
        """Execute Jira API calls"""
        client = await get_atlassian_client(token)
        
        if tool_name == "jira_create_issue":
            # Call Jira API to create issue
            response = await client.post(
                f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3/issue",
                json={
                    "fields": {
                        "project": {"key": args["project"]},
                        "summary": args["summary"],
                        "description": args.get("description", ""),
                        "issuetype": {"name": args["issue_type"]},
                        "priority": {"name": args.get("priority", "Medium")}
                    }
                }
            )
            return response.json()
        
        # Handle other Jira tools...
```

## Advantages of MCP Architecture

1. **Scalability**: MCP servers can be deployed independently and scaled horizontally
2. **Security**: OAuth tokens are handled by MCP server, not exposed to client
3. **Flexibility**: Easy to add new connectors without modifying core backend
4. **Standardization**: Following MCP spec ensures compatibility with other MCP clients
5. **Real-time Updates**: SSE enables push notifications for long-running operations
6. **Reduced Complexity**: OAuth flow handled by MCP server, not our backend

## Migration Strategy

1. **Phase 1**: Implement MCP infrastructure alongside existing direct connectors
2. **Phase 2**: Deploy Atlassian MCP server and connector
3. **Phase 3**: Test thoroughly with both approaches running in parallel
4. **Phase 4**: Gradually migrate other connectors to MCP if beneficial
5. **Phase 5**: Optimize and standardize on best approach per connector type

## Decision Matrix: Direct vs MCP

| Factor | Direct OAuth | MCP-Based |
|--------|-------------|-----------|
| Implementation Speed | Faster initially | More setup required |
| Scalability | Limited by backend | Highly scalable |
| Real-time Updates | Polling required | SSE built-in |
| Token Management | Backend handles | MCP server handles |
| Deployment | Monolithic | Microservices |
| Best For | Simple integrations | Complex, high-volume |

## Recommendations

1. **Use Direct OAuth for**:
   - Simple connectors with few API calls
   - When you need full control over the flow
   - Quick prototypes

2. **Use MCP for**:
   - Complex connectors (Atlassian, GitHub, etc.)
   - When following industry standards is important
   - Connectors that need real-time updates
   - When you want to leverage existing MCP servers

## Next Steps

1. Implement MCP base infrastructure
2. Create Atlassian MCP connector
3. Deploy minimal MCP server for Atlassian
4. Test end-to-end flow
5. Document learnings and refine approach