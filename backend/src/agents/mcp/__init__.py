"""
MCP (Model Context Protocol) integration module for dynamic tool loading.

This module provides functionality to manage MCP servers and integrate their tools
with the agent system on a per-user basis.
"""

from .server_manager import MCPServerManager

__all__ = ["MCPServerManager"] 