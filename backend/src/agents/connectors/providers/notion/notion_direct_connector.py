"""
Notion Direct API Tools Implementation

This module implements direct REST API calls to Notion without using MCP,
providing reliable multi-user support through OAuth tokens.
"""

import asyncio
import json
from typing import Any, Dict, List, Optional, Type, Union

import aiohttp
import structlog
from langchain.tools import BaseTool
from pydantic import BaseModel, Field, field_validator

# No need for additional imports - token storage handled by main connector

logger = structlog.get_logger(__name__)

NOTION_API_VERSION = "2022-06-28"


# Input schemas for each tool
class EmptyInput(BaseModel):
    """Empty input for tools that don't require parameters."""
    pass


class SearchInput(BaseModel):
    """Input for searching Notion."""
    query: str = Field(description="Search query")
    filter: Optional[str] = Field(None, description="Filter by object type: 'page' or 'database'")
    
    @field_validator('query', mode='before')
    @classmethod
    def clean_query(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if not v:
                raise ValueError("Search query cannot be empty")
        return v
    
    @field_validator('filter', mode='before')
    @classmethod
    def validate_filter(cls, v):
        if v and isinstance(v, str):
            v = v.lower().strip()
            if v not in ['page', 'database', '']:
                return None  # Invalid filter, ignore it
        return v


class QueryDatabaseInput(BaseModel):
    """Input for querying a database."""
    database_id: str = Field(description="Database ID to query")
    filter: Optional[Union[Dict[str, Any], str]] = Field(None, description="Filter conditions in Notion format")
    sorts: Optional[Union[List[Dict[str, Any]], str]] = Field(None, description="Sort conditions")
    page_size: Optional[int] = Field(10, description="Number of results (max 100)")
    
    @field_validator('filter', mode='before')
    @classmethod
    def parse_filter(cls, v):
        if isinstance(v, str):
            if not v or v == "{}":
                return None
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return None
        return v
    
    @field_validator('sorts', mode='before')
    @classmethod
    def parse_sorts(cls, v):
        if isinstance(v, str):
            if not v or v == "[]":
                return None
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return None
        return v


class CreatePageInput(BaseModel):
    """Input for creating a page."""
    parent_type: str = Field(description="Type of parent: 'database_id' or 'page_id'")
    parent_id: str = Field(description="ID of the parent database or page")
    title: str = Field(description="Page title")
    properties: Optional[Union[Dict[str, Any], str]] = Field(None, description="Database properties if parent is database")
    content: Optional[Union[List[Dict[str, Any]], str]] = Field(None, description="Initial page content blocks")
    
    @field_validator('properties', mode='before')
    @classmethod
    def parse_properties(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return {}
        return v
    
    @field_validator('content', mode='before')
    @classmethod
    def parse_content(cls, v):
        # Keep as string for now, will be converted to blocks in the tool
        return v


class GetPageInput(BaseModel):
    """Input for getting a page."""
    page_id: str = Field(description="Page ID")
    
    @field_validator('page_id', mode='before')
    @classmethod
    def clean_page_id(cls, v):
        if isinstance(v, str):
            # Remove any whitespace and handle UUID formatting
            v = v.strip().replace(' ', '').replace('-', '')
        return v


class UpdatePageInput(BaseModel):
    """Input for updating a page."""
    page_id: str = Field(description="Page ID to update")
    properties: Optional[Union[Dict[str, Any], str]] = Field(None, description="Properties to update")
    archived: Optional[bool] = Field(None, description="Whether to archive the page")
    
    @field_validator('properties', mode='before')
    @classmethod
    def parse_properties(cls, v):
        if isinstance(v, str):
            if not v or v == "{}":
                return None
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return None
        return v


class GetBlocksInput(BaseModel):
    """Input for getting page blocks."""
    page_id: str = Field(description="Page ID")
    
    @field_validator('page_id', mode='before')
    @classmethod
    def clean_page_id(cls, v):
        # Remove any whitespace and handle common formatting issues
        if isinstance(v, str):
            return v.strip().replace(' ', '')
        return v


class AppendBlocksInput(BaseModel):
    """Input for appending blocks."""
    page_id: str = Field(description="Page ID to append to")
    children: Union[List[Dict[str, Any]], str] = Field(description="Array of block objects to append")
    
    @field_validator('page_id', mode='before')
    @classmethod
    def clean_page_id(cls, v):
        if isinstance(v, str):
            return v.strip().replace(' ', '')
        return v
    
    @field_validator('children', mode='before')
    @classmethod
    def parse_children(cls, v):
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                return parsed if isinstance(parsed, list) else [parsed]
            except json.JSONDecodeError:
                # If not JSON, treat as plain text and create a paragraph block
                return [{
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{
                            "type": "text",
                            "text": {"content": v}
                        }]
                    }
                }]
        return v


class CreateDatabaseInput(BaseModel):
    """Input for creating a database."""
    parent_type: str = Field(description="Type of parent: 'page_id' (workspace not supported via API)")
    parent_id: str = Field(description="Parent page ID")
    title: str = Field(description="Database title")
    properties: Union[Dict[str, Any], str] = Field(description="Database schema properties")
    
    @field_validator('properties', mode='before')
    @classmethod
    def parse_properties(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                # Return a basic schema if parsing fails
                return {
                    "Name": {"title": {}},
                    "Status": {
                        "select": {
                            "options": [
                                {"name": "To Do", "color": "red"},
                                {"name": "In Progress", "color": "yellow"},
                                {"name": "Done", "color": "green"}
                            ]
                        }
                    }
                }
        return v


class NotionDirectConnector:
    """
    Direct API implementation for Notion.
    """
    
    def __init__(self, redis_storage):
        """Initialize the direct connector."""
        self.redis_storage = redis_storage
        self.config = None  # Will be set by the main connector
        self.parent_connector = None  # Will be set by the main connector
        self.api_base_url = "https://api.notion.com/v1"
    
    async def get_user_token(self, user_id: str, auto_refresh: bool = True):
        """Get user token through parent connector."""
        if self.parent_connector:
            return await self.parent_connector.get_user_token(user_id, auto_refresh)
        return None
    
    async def _make_api_request(
        self,
        method: str,
        endpoint: str,
        user_id: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make an authenticated API request to Notion.
        
        Args:
            method: HTTP method
            endpoint: API endpoint (without base URL)
            user_id: User ID for token retrieval
            data: Request body data
            params: Query parameters
            
        Returns:
            API response as dictionary
        """
        try:
            # Get user token
            token = await self.get_user_token(user_id, auto_refresh=False)
            if not token:
                return {"error": "No authentication found. Please connect your Notion account."}
            
            # Prepare request
            url = f"{self.api_base_url}{endpoint}"
            headers = {
                "Authorization": f"Bearer {token.access_token}",
                "Notion-Version": NOTION_API_VERSION,
                "Content-Type": "application/json"
            }
            
            # Make request
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=data,
                    params=params
                ) as response:
                    response_text = await response.text()
                    
                    if response.status == 200:
                        return json.loads(response_text) if response_text else {}
                    else:
                        logger.error(
                            "Notion API request failed",
                            status=response.status,
                            endpoint=endpoint,
                            response=response_text
                        )
                        return {"error": f"API request failed: {response_text}"}
                        
        except Exception as e:
            logger.error(
                "Failed to make Notion API request",
                endpoint=endpoint,
                error=str(e),
                exc_info=True
            )
            return {"error": str(e)}
    
    async def create_langchain_tools(self, user_id: str, tool_ids: Optional[List[str]] = None) -> List[BaseTool]:
        """
        Create LangChain tools for Notion.
        
        Args:
            user_id: User ID
            tool_ids: Optional list of tool IDs to create (None = all tools)
            
        Returns:
            List of LangChain tools
        """
        tools = []
        
        # Map of tool ID to tool class
        tool_map = {
            "notion_search": SearchTool,
            "notion_list_databases": ListDatabasesTool,
            "notion_query_database": QueryDatabaseTool,
            "notion_get_database_schema": GetDatabaseSchemaTool,
            "notion_create_page": CreatePageTool,
            "notion_get_page": GetPageTool,
            "notion_update_page": UpdatePageTool,
            "notion_get_blocks": GetBlocksTool,
            "notion_append_blocks": AppendBlocksTool,
            "notion_create_database": CreateDatabaseTool
        }
        
        # Filter tools if specific IDs provided
        if tool_ids:
            tool_map = {k: v for k, v in tool_map.items() if k in tool_ids}
        
        # Create tool instances
        for _, tool_class in tool_map.items():
            tool = tool_class(connector=self, user_id=user_id)
            tools.append(tool)
        
        logger.info(
            "Created Notion tools",
            user_id=user_id,
            num_tools=len(tools),
            tool_ids=list(tool_map.keys())
        )
        
        return tools


# Base class for Notion tools
class NotionDirectTool(BaseTool):
    """Base class for Notion direct API tools."""
    connector: NotionDirectConnector
    user_id: str
    
    class Config:
        arbitrary_types_allowed = True


# Tool implementations
class SearchTool(NotionDirectTool):
    """Search across Notion workspace."""
    name: str = "notion_search"
    description: str = "Search across all pages and databases in your Notion workspace"
    args_schema: Type[BaseModel] = SearchInput
    
    async def _arun(self, **kwargs) -> str:
        """Search Notion."""
        data = {
            "query": kwargs["query"]
        }
        
        if kwargs.get("filter"):
            data["filter"] = {"value": kwargs["filter"], "property": "object"}
        
        result = await self.connector._make_api_request(
            method="POST",
            endpoint="/search",
            user_id=self.user_id,
            data=data
        )
        
        if "error" in result:
            return f"Error searching: {result['error']}"
        
        results = result.get("results", [])
        if not results:
            return "No results found."
        
        output = f"Found {len(results)} results:\n\n"
        for item in results:
            obj_type = item.get("object", "unknown")
            title = "Untitled"
            
            if obj_type == "page":
                # Get page title
                props = item.get("properties", {})
                for prop in props.values():
                    if prop.get("type") == "title" and prop.get("title"):
                        title_parts = prop["title"]
                        if title_parts:
                            title = title_parts[0].get("plain_text", "Untitled")
                        break
            elif obj_type == "database":
                # Get database title
                title_parts = item.get("title", [])
                if title_parts:
                    title = title_parts[0].get("plain_text", "Untitled")
            
            output += f"- {obj_type.capitalize()}: {title}\n"
            output += f"  ID: {item.get('id', 'N/A')}\n"
            output += f"  URL: {item.get('url', 'N/A')}\n\n"
        
        return output
    
    def _run(self, **kwargs) -> str:
        """Sync version."""
        import asyncio
        return asyncio.run(self._arun(**kwargs))


class ListDatabasesTool(NotionDirectTool):
    """List all databases."""
    name: str = "notion_list_databases"
    description: str = "List all databases in your Notion workspace"
    args_schema: Type[BaseModel] = EmptyInput
    
    async def _arun(self, **kwargs) -> str:
        """List databases."""
        result = await self.connector._make_api_request(
            method="POST",
            endpoint="/search",
            user_id=self.user_id,
            data={"filter": {"value": "database", "property": "object"}}
        )
        
        if "error" in result:
            return f"Error listing databases: {result['error']}"
        
        databases = result.get("results", [])
        if not databases:
            return "No databases found."
        
        output = f"Found {len(databases)} databases:\n\n"
        for db in databases:
            title_parts = db.get("title", [])
            title = "Untitled"
            if title_parts:
                title = title_parts[0].get("plain_text", "Untitled")
            
            output += f"- {title}\n"
            output += f"  ID: {db.get('id', 'N/A')}\n"
            output += f"  URL: {db.get('url', 'N/A')}\n"
            output += f"  Created: {db.get('created_time', 'N/A')}\n\n"
        
        return output
    
    def _run(self, **kwargs) -> str:
        """Sync version."""
        import asyncio
        return asyncio.run(self._arun(**kwargs))


class QueryDatabaseTool(NotionDirectTool):
    """Query a database."""
    name: str = "notion_query_database"
    description: str = "Query a Notion database with filters and sorts"
    args_schema: Type[BaseModel] = QueryDatabaseInput
    
    async def _arun(self, **kwargs) -> str:
        """Query database."""
        data = {
            "page_size": min(kwargs.get("page_size", 10), 100)
        }
        
        if kwargs.get("filter"):
            data["filter"] = kwargs["filter"]
        
        if kwargs.get("sorts"):
            data["sorts"] = kwargs["sorts"]
        
        result = await self.connector._make_api_request(
            method="POST",
            endpoint=f"/databases/{kwargs['database_id']}/query",
            user_id=self.user_id,
            data=data
        )
        
        if "error" in result:
            return f"Error querying database: {result['error']}"
        
        pages = result.get("results", [])
        
        if not pages:
            return "No pages found in database."
        
        output = f"Found {len(pages)} pages:\n\n"
        
        for page in pages:
            # Extract title
            title = "Untitled"
            props = page.get("properties", {})
            for prop in props.values():
                if prop.get("type") == "title" and prop.get("title"):
                    title_parts = prop["title"]
                    if title_parts:
                        title = title_parts[0].get("plain_text", "Untitled")
                    break
            
            output += f"- {title}\n"
            output += f"  ID: {page.get('id', 'N/A')}\n"
            output += f"  URL: {page.get('url', 'N/A')}\n"
            output += f"  Created: {page.get('created_time', 'N/A')}\n\n"
        
        return output
    
    def _run(self, **kwargs) -> str:
        """Sync version."""
        import asyncio
        return asyncio.run(self._arun(**kwargs))


class CreatePageTool(NotionDirectTool):
    """Create a new page."""
    name: str = "notion_create_page"
    description: str = "Create a new page in a database or as a child of another page. For database pages, first use notion_get_database_schema to understand the property types."
    args_schema: Type[BaseModel] = CreatePageInput
    
    async def _arun(self, **kwargs) -> str:
        """Create page."""
        import json
        
        # Prepare parent
        parent = {kwargs["parent_type"]: kwargs["parent_id"]}
        
        # Prepare properties
        properties = kwargs.get("properties", {})
        
        # Handle properties if it's a JSON string
        if isinstance(properties, str):
            try:
                properties = json.loads(properties)
            except json.JSONDecodeError:
                # If JSON decode fails, treat as empty
                properties = {}
        
        # For regular pages (not in a database), handle title
        if kwargs["parent_type"] == "page_id" and kwargs.get("title"):
            # For regular pages, title goes in properties
            properties = {
                "title": {
                    "title": [{
                        "text": {
                            "content": kwargs["title"]
                        }
                    }]
                }
            }
        # For database pages, the LLM should provide properly formatted properties
        # based on the schema retrieved from notion_get_database_schema
        
        data = {
            "parent": parent,
            "properties": properties
        }
        
        # Add content blocks if provided
        content = kwargs.get("content")
        if content:
            # If content is a string, convert it to a paragraph block
            if isinstance(content, str):
                data["children"] = [{
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{
                            "type": "text",
                            "text": {
                                "content": content
                            }
                        }]
                    }
                }]
            elif isinstance(content, list):
                data["children"] = content
            # If content is a dict that looks like a single block, wrap it in a list
            elif isinstance(content, dict):
                data["children"] = [content]
        
        result = await self.connector._make_api_request(
            method="POST",
            endpoint="/pages",
            user_id=self.user_id,
            data=data
        )
        
        if "error" in result:
            return f"Error creating page: {result['error']}"
        
        return f"Page created successfully!\nID: {result.get('id', 'Unknown')}\nURL: {result.get('url', 'N/A')}"
    
    def _run(self, **kwargs) -> str:
        """Sync version."""
        import asyncio
        return asyncio.run(self._arun(**kwargs))


class GetPageTool(NotionDirectTool):
    """Get page details."""
    name: str = "notion_get_page"
    description: str = "Get a page's properties and metadata"
    args_schema: Type[BaseModel] = GetPageInput
    
    async def _arun(self, **kwargs) -> str:
        """Get page."""
        result = await self.connector._make_api_request(
            method="GET",
            endpoint=f"/pages/{kwargs['page_id']}",
            user_id=self.user_id
        )
        
        if "error" in result:
            return f"Error getting page: {result['error']}"
        
        # Extract title
        title = "Untitled"
        props = result.get("properties", {})
        for prop_name, prop in props.items():
            if prop.get("type") == "title" and prop.get("title"):
                title_parts = prop["title"]
                if title_parts:
                    title = title_parts[0].get("plain_text", "Untitled")
                break
        
        output = f"Page: {title}\n"
        output += f"ID: {result.get('id', 'N/A')}\n"
        output += f"URL: {result.get('url', 'N/A')}\n"
        output += f"Created: {result.get('created_time', 'N/A')}\n"
        output += f"Last edited: {result.get('last_edited_time', 'N/A')}\n"
        output += f"Archived: {result.get('archived', False)}\n\n"
        
        # Show properties
        if props:
            output += "Properties:\n"
            for prop_name, prop in props.items():
                prop_type = prop.get("type", "unknown")
                output += f"- {prop_name} ({prop_type}): "
                
                # Extract property value based on type
                if prop_type == "title" and prop.get("title"):
                    texts = [t.get("plain_text", "") for t in prop["title"]]
                    output += " ".join(texts)
                elif prop_type == "rich_text" and prop.get("rich_text"):
                    texts = [t.get("plain_text", "") for t in prop["rich_text"]]
                    output += " ".join(texts)
                elif prop_type == "number":
                    output += str(prop.get("number", ""))
                elif prop_type == "select" and prop.get("select"):
                    output += prop["select"].get("name", "")
                elif prop_type == "multi_select" and prop.get("multi_select"):
                    names = [s.get("name", "") for s in prop["multi_select"]]
                    output += ", ".join(names)
                elif prop_type == "date" and prop.get("date"):
                    output += prop["date"].get("start", "")
                elif prop_type == "status" and prop.get("status"):
                    output += prop["status"].get("name", "")
                elif prop_type == "checkbox":
                    output += str(prop.get("checkbox", False))
                elif prop_type == "url":
                    output += str(prop.get("url", ""))
                elif prop_type == "email":
                    output += str(prop.get("email", ""))
                elif prop_type == "phone_number":
                    output += str(prop.get("phone_number", ""))
                else:
                    output += "(complex value)"
                
                output += "\n"
        
        return output
    
    def _run(self, **kwargs) -> str:
        """Sync version."""
        import asyncio
        return asyncio.run(self._arun(**kwargs))


class UpdatePageTool(NotionDirectTool):
    """Update a page."""
    name: str = "notion_update_page"
    description: str = "Update a page's properties"
    args_schema: Type[BaseModel] = UpdatePageInput
    
    async def _arun(self, **kwargs) -> str:
        """Update page."""
        data = {}
        
        if kwargs.get("properties"):
            data["properties"] = kwargs["properties"]
        
        if kwargs.get("archived") is not None:
            data["archived"] = kwargs["archived"]
        
        if not data:
            return "No updates specified."
        
        result = await self.connector._make_api_request(
            method="PATCH",
            endpoint=f"/pages/{kwargs['page_id']}",
            user_id=self.user_id,
            data=data
        )
        
        if "error" in result:
            return f"Error updating page: {result['error']}"
        
        return f"Page updated successfully!\nID: {result.get('id', 'Unknown')}"
    
    def _run(self, **kwargs) -> str:
        """Sync version."""
        import asyncio
        return asyncio.run(self._arun(**kwargs))


class GetBlocksTool(NotionDirectTool):
    """Get page blocks."""
    name: str = "notion_get_blocks"
    description: str = "Get all blocks (content) from a page"
    args_schema: Type[BaseModel] = GetBlocksInput
    
    async def _arun(self, **kwargs) -> str:
        """Get blocks."""
        result = await self.connector._make_api_request(
            method="GET",
            endpoint=f"/blocks/{kwargs['page_id']}/children",
            user_id=self.user_id,
            params={"page_size": 100}
        )
        
        if "error" in result:
            return f"Error getting blocks: {result['error']}"
        
        blocks = result.get("results", [])
        if not blocks:
            return "No blocks found in page."
        
        output = f"Found {len(blocks)} blocks:\n\n"
        
        def format_block(block, indent=0):
            """Format a block for display."""
            prefix = "  " * indent
            block_type = block.get("type", "unknown")
            block_output = f"{prefix}- {block_type}: "
            
            # Extract text content based on block type
            if block_type in ["paragraph", "heading_1", "heading_2", "heading_3", "bulleted_list_item", "numbered_list_item", "to_do", "toggle", "quote", "callout"]:
                texts = block.get(block_type, {}).get("rich_text", [])
                content = " ".join([t.get("plain_text", "") for t in texts])
                block_output += content or "(empty)"
            elif block_type == "code":
                code_block = block.get("code", {})
                texts = code_block.get("rich_text", [])
                content = " ".join([t.get("plain_text", "") for t in texts])
                language = code_block.get("language", "plain")
                block_output += f"[{language}] {content}"
            elif block_type == "image":
                image = block.get("image", {})
                if image.get("type") == "external":
                    block_output += image.get("external", {}).get("url", "")
                else:
                    block_output += "(file)"
            elif block_type == "divider":
                block_output += "---"
            else:
                block_output += "(complex block)"
            
            return block_output + "\n"
        
        for block in blocks:
            output += format_block(block)
        
        return output
    
    def _run(self, **kwargs) -> str:
        """Sync version."""
        import asyncio
        return asyncio.run(self._arun(**kwargs))


class AppendBlocksTool(NotionDirectTool):
    """Append blocks to a page."""
    name: str = "notion_append_blocks"
    description: str = "Add new blocks to a page"
    args_schema: Type[BaseModel] = AppendBlocksInput
    
    async def _arun(self, **kwargs) -> str:
        """Append blocks."""
        data = {
            "children": kwargs["children"]
        }
        
        result = await self.connector._make_api_request(
            method="PATCH",
            endpoint=f"/blocks/{kwargs['page_id']}/children",
            user_id=self.user_id,
            data=data
        )
        
        if "error" in result:
            return f"Error appending blocks: {result['error']}"
        
        results = result.get("results", [])
        return f"Successfully appended {len(results)} blocks to the page."
    
    def _run(self, **kwargs) -> str:
        """Sync version."""
        import asyncio
        return asyncio.run(self._arun(**kwargs))


class GetDatabaseSchemaTool(NotionDirectTool):
    """Get database schema."""
    name: str = "notion_get_database_schema"
    description: str = "Get the schema of a database including all property names and types. Use this before creating pages to understand the database structure."
    
    class SchemaInput(BaseModel):
        """Input for getting database schema."""
        database_id: str = Field(description="Database ID")
    
    args_schema: Type[BaseModel] = SchemaInput
    
    async def _arun(self, **kwargs) -> str:
        """Get database schema."""
        result = await self.connector._make_api_request(
            method="GET",
            endpoint=f"/databases/{kwargs['database_id']}",
            user_id=self.user_id
        )
        
        if "error" in result:
            return f"Error getting database schema: {result['error']}"
        
        # Extract and format the schema information
        properties = result.get("properties", {})
        title = result.get("title", [])
        db_title = title[0].get("plain_text", "Untitled") if title else "Untitled"
        
        output = f"Database: {db_title}\n"
        output += f"ID: {result.get('id', 'N/A')}\n\n"
        output += "Properties Schema:\n"
        output += "-" * 50 + "\n"
        
        # Identify the title property
        title_property = None
        
        for prop_name, prop_config in properties.items():
            prop_type = prop_config.get("type", "unknown")
            prop_id = prop_config.get("id", "")
            
            output += f"\nProperty: {prop_name}\n"
            output += f"  Type: {prop_type}\n"
            output += f"  ID: {prop_id}\n"
            
            if prop_type == "title":
                title_property = prop_name
                output += "  (This is the TITLE property - required for all pages)\n"
            elif prop_type == "select":
                options = prop_config.get("select", {}).get("options", [])
                if options:
                    output += f"  Options: {', '.join([opt['name'] for opt in options])}\n"
            elif prop_type == "multi_select":
                options = prop_config.get("multi_select", {}).get("options", [])
                if options:
                    output += f"  Options: {', '.join([opt['name'] for opt in options])}\n"
            elif prop_type == "status":
                options = prop_config.get("status", {}).get("options", [])
                if options:
                    output += f"  Options: {', '.join([opt['name'] for opt in options])}\n"
                groups = prop_config.get("status", {}).get("groups", [])
                if groups:
                    output += f"  Groups: {', '.join([g['name'] for g in groups])}\n"
        
        output += "\n" + "=" * 50 + "\n"
        output += "IMPORTANT: When creating pages in this database:\n"
        output += f"1. The title property is '{title_property}' (type: title)\n"
        output += "2. Use the exact property names shown above\n"
        output += "3. Format properties according to their types:\n"
        output += "   - title/rich_text: {\"property_name\": {\"title/rich_text\": [{\"text\": {\"content\": \"value\"}}]}}\n"
        output += "   - select: {\"property_name\": {\"select\": {\"name\": \"option_name\"}}}\n"
        output += "   - multi_select: {\"property_name\": {\"multi_select\": [{\"name\": \"option1\"}, {\"name\": \"option2\"}]}}\n"
        output += "   - status: {\"property_name\": {\"status\": {\"name\": \"status_name\"}}}\n"
        output += "   - number: {\"property_name\": {\"number\": 123}}\n"
        output += "   - checkbox: {\"property_name\": {\"checkbox\": true/false}}\n"
        
        return output
    
    def _run(self, **kwargs) -> str:
        """Sync version."""
        import asyncio
        return asyncio.run(self._arun(**kwargs))


class CreateDatabaseTool(NotionDirectTool):
    """Create a database."""
    name: str = "notion_create_database"
    description: str = "Create a new database"
    args_schema: Type[BaseModel] = CreateDatabaseInput
    
    async def _arun(self, **kwargs) -> str:
        """Create database."""
        # Prepare parent - Notion expects page_id format
        # Workspace-level databases aren't directly supported via API
        # They need to be created as children of a page
        if kwargs["parent_type"] == "workspace":
            # Can't create workspace-level databases via API
            return "Error: Creating databases at workspace level is not supported via API. Please specify a page_id as parent."
        else:
            parent = {"page_id": kwargs.get("parent_id")}
        
        # Prepare title
        title = [{
            "type": "text",
            "text": {
                "content": kwargs["title"]
            }
        }]
        
        # Ensure properties has at least a title column
        properties = kwargs.get("properties", {})
        if not properties:
            # Create a basic schema with a title property
            properties = {
                "Name": {
                    "title": {}
                }
            }
        
        data = {
            "parent": parent,
            "title": title,
            "properties": properties
        }
        
        result = await self.connector._make_api_request(
            method="POST",
            endpoint="/databases",
            user_id=self.user_id,
            data=data
        )
        
        if "error" in result:
            return f"Error creating database: {result['error']}"
        
        return f"Database created successfully!\nID: {result.get('id', 'Unknown')}\nURL: {result.get('url', 'N/A')}"
    
    def _run(self, **kwargs) -> str:
        """Sync version."""
        import asyncio
        return asyncio.run(self._arun(**kwargs))