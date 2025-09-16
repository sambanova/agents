# Connector Implementation Lessons Learned

## Date: January 15, 2025

## Overview
This document captures key learnings from implementing OAuth-based connectors with MCP (Model Context Protocol) integration, specifically from our work with Atlassian and preparations for PayPal integration.

## Key Architectural Decisions

### 1. MCP vs Direct API Implementation
- **Finding**: While MCP provides a standardized protocol for AI tool integration, some providers' MCP servers may be in beta or have authentication issues
- **Solution**: Implement fallback to direct REST API when MCP fails
- **Example**: Atlassian MCP server had OAuth issues, so we implemented `atlassian_direct_connector.py` as a fallback

### 2. Token Refresh Optimization
- **Problem**: Aggressive token refreshing caused 8-second delays (9 refreshes for 9 tools)
- **Root Causes**:
  - Duplicate refresh logic in connector's `get_user_tools` method
  - Individual tool creation instead of batching
- **Solution**: 
  - Remove duplicate refresh logic - rely on base class `get_user_token(auto_refresh=True)`
  - Batch tool creation in `connector_manager.py` to call `create_langchain_tools` once with all tool IDs

### 3. OAuth Scope Management
- **Challenge**: Different API versions require different scopes
- **Example**: Confluence API v1 vs v2 migration required adding `read:page:confluence` scope
- **Best Practice**: Research and validate scopes before implementation, maintain a mapping of API versions to required scopes

## Implementation Patterns

### 1. Multi-Tenant Support
- **Requirement**: System must support multiple users with different instances
- **Solution**: Dynamic cloud_id/instance retrieval from OAuth accessible-resources endpoint
- **Anti-pattern**: Never hardcode instance URLs or tenant-specific information

### 2. Error Handling and Recovery
- **Pattern**: Implement graceful degradation when OAuth refresh fails
- **Implementation**:
  ```python
  # Mark refresh token as invalid to prevent retry loops
  if "refresh_token is invalid" in error_str:
      token.additional_data["refresh_invalid"] = True
      await self.store_user_token(token)
  ```

### 3. API Version Migration
- **Problem**: Deprecated API endpoints (e.g., Confluence v1 returning 410 Gone)
- **Solution**: Proactive migration to newer API versions with proper error handling
- **Example**: Migrated from `/rest/api/content` to `/wiki/api/v2/pages`

## Technical Discoveries

### 1. Atlassian-Specific Requirements
- **OAuth Flow**: Requires PKCE (code_verifier/code_challenge)
- **Token Rotation**: Uses rotating refresh tokens
- **Scope Format**: Mix of classic and granular scopes
- **Critical Scopes**:
  - `offline_access` - Required for refresh token support
  - `search:confluence` - Required for Confluence search API
  - `read:page:confluence` - Required for v2 API page operations

### 2. Performance Optimizations
- **Tool Creation Batching**: Reduced token operations from O(n) to O(1)
- **Token Caching**: Use `auto_refresh=False` internally to prevent recursion
- **Connector Caching**: Implement TTL-based caching for tool lists

### 3. Debugging Strategies
- **Extensive Logging**: Log token state, refresh attempts, and API responses
- **Token Inspection**: Decode JWT tokens to understand scope and expiry
- **Request Tracing**: Log full request/response for OAuth flows

## Best Practices for New Connector Implementation

### 1. Research Phase
- [ ] Verify OAuth 2.0 endpoints (authorize, token, revoke)
- [ ] Document all available scopes and their purposes
- [ ] Check for API version requirements
- [ ] Identify sandbox/test environments
- [ ] Confirm MCP server availability and stability

### 2. Implementation Phase
- [ ] Start with MCP integration if available
- [ ] Implement direct API fallback for critical functionality
- [ ] Use base class token refresh logic - don't duplicate
- [ ] Batch tool creation operations
- [ ] Add comprehensive error handling for OAuth failures

### 3. Testing Phase
- [ ] Test with sandbox/test accounts first
- [ ] Verify token refresh flow works correctly
- [ ] Test error scenarios (expired tokens, invalid refresh tokens)
- [ ] Monitor performance (especially during tool loading)
- [ ] Validate multi-tenant support

### 4. Documentation
- [ ] Document OAuth setup requirements
- [ ] List all required scopes with explanations
- [ ] Provide troubleshooting guide for common errors
- [ ] Include examples of successful API calls

## Common Pitfalls to Avoid

1. **Don't duplicate token refresh logic** - Use base class implementation
2. **Don't make individual API calls for batch operations** - Batch where possible
3. **Don't hardcode instance-specific values** - Use dynamic discovery
4. **Don't ignore API deprecation warnings** - Plan migrations early
5. **Don't assume MCP server stability** - Have fallback implementations
6. **Don't skip scope validation** - Verify scopes exist before adding them

## PayPal Connector Implementation

### OAuth Setup (Completed)
PayPal uses a different OAuth model than Google/Atlassian:

1. **No Explicit Scopes Required**: PayPal automatically assigns scopes based on app permissions in Developer Dashboard
2. **Multi-User Support**: Uses OAuth Authorization Code flow where each user authorizes their own PayPal account
3. **Sandbox First**: Always use sandbox environment (`https://mcp.sandbox.paypal.com`) for testing
4. **Client Credentials**: Required to identify your app, but don't grant access to any specific account

### Key Differences from Other Providers
- **Scopes**: Auto-assigned, not explicitly requested
- **MCP Server**: Supports both local (single merchant) and remote (multi-user OAuth) modes
- **Authentication**: Client ID/Secret identify the app; user authorization grants account access

### Environment Variables Required
```bash
PAYPAL_CLIENT_ID=your_app_client_id        # From PayPal Developer Dashboard
PAYPAL_CLIENT_SECRET=your_app_secret       # From PayPal Developer Dashboard  
PAYPAL_OAUTH_REDIRECT_URI=http://localhost:8000/api/connectors/paypal/callback
```

### Testing Checklist
- [ ] OAuth authorization flow with sandbox account
- [ ] Token refresh mechanism
- [ ] MCP server connection to sandbox endpoint
- [ ] Tool availability and execution
- [ ] Multi-user isolation (User A can't access User B's PayPal)

## Metrics and Improvements

### Before Optimization
- Token refresh: 9 times per tool load
- Tool loading delay: ~8 seconds
- API calls: O(n) where n = number of tools

### After Optimization
- Token refresh: 1 time per tool load (if needed)
- Tool loading delay: <1 second
- API calls: O(1) for batch operations

## Future Considerations

1. **Implement token refresh prediction** - Refresh before expiry to avoid delays
2. **Add connector health monitoring** - Track OAuth success rates
3. **Create connector testing framework** - Automated tests for OAuth flows
4. **Standardize error codes** - Consistent error handling across connectors
5. **Implement circuit breaker pattern** - Prevent cascading failures

## Conclusion

The key to successful connector implementation is flexibility and defensive programming. Always assume external services may fail or change, and design systems that can adapt gracefully. The MCP protocol provides excellent standardization when it works, but direct API implementation remains essential for production reliability.