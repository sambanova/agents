# Connector Implementation Lessons Learned

## Date: January 16, 2025

## Overview
This document captures key learnings from implementing OAuth-based connectors with MCP (Model Context Protocol) integration, specifically from our work with Google, Atlassian, PayPal, and Notion integrations.

## Key Architectural Decisions

### 1. MCP vs Direct API Implementation
- **Finding**: While MCP provides a standardized protocol for AI tool integration, most providers' MCP servers are either not production-ready or designed for single-user subprocess models
- **Solution**: Implement direct REST API integration as the primary approach for multi-user SaaS applications
- **Examples**: 
  - Atlassian: MCP server had OAuth discovery issues, implemented direct API
  - PayPal: MCP server only supports subprocess/proxy model, not direct HTTP; implemented full direct API with 12 tools
  - Notion: Skipped MCP entirely based on learnings, went straight to direct API implementation

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

### Critical Lessons Learned
1. **MCP Architecture Incompatibility**: PayPal's MCP server is designed for subprocess/proxy usage via npm package `@paypal/mcp`, not direct HTTP
2. **OAuth Scope vs App Permissions**: App permissions in Dashboard don't automatically grant API access - specific OAuth scopes must be added
3. **Token Caching Issue**: Changes to app features take 9 hours to propagate or require token refresh
4. **API Response Limitations**: List endpoints return minimal data; full details require individual item fetches

### OAuth Setup (Completed)
PayPal uses Connect with PayPal OAuth flow:

1. **Explicit Scopes Required**: Despite app permissions, must explicitly request scopes like `https://uri.paypal.com/services/invoicing`
2. **Multi-User Support**: Uses OAuth Authorization Code flow where each user authorizes their own PayPal account
3. **Sandbox Environment**: Always use sandbox (`https://api-m.sandbox.paypal.com`) for testing
4. **Token Management**: Access tokens expire in 9 hours; refresh tokens supported

### Direct API Implementation
Implemented 12 tools covering:
- **Products API**: CreateProduct, ListProducts, ShowProductDetails
- **Invoicing API**: CreateInvoice, ListInvoices, GetInvoice, SendInvoice, SendInvoiceReminder, CancelSentInvoice
- **Disputes API**: ListDisputes, GetDispute, AcceptDisputeClaim

### Key Differences from Other Providers
- **MCP Failure**: First case where MCP was completely unusable due to architecture mismatch
- **Scope Requirements**: Most restrictive - requires exact URI-based scopes
- **Data Minimalism**: List APIs return less data than other providers

### Environment Variables Required
```bash
PAYPAL_CLIENT_ID=your_app_client_id        # From PayPal Developer Dashboard
PAYPAL_CLIENT_SECRET=your_app_secret       # From PayPal Developer Dashboard  
PAYPAL_OAUTH_REDIRECT_URI=http://localhost:8000/api/connectors/paypal/callback
```

### Testing Checklist
- [x] OAuth authorization flow with sandbox account
- [x] Direct API implementation for all tools
- [x] Products API functionality
- [x] Invoicing API with proper scope configuration
- [x] Multi-user isolation (User A can't access User B's PayPal)

## Notion Connector Implementation

### Strategic Decision
Based on PayPal and Atlassian experiences, we went straight to direct API implementation without attempting MCP integration.

### OAuth Implementation Details
Notion uses a simplified OAuth 2.0 flow:

1. **No Refresh Tokens**: Access tokens don't expire unless revoked
2. **No Traditional Scopes**: Permissions are managed through Notion's UI during authorization
3. **HTTP Basic Auth for Token Exchange**: Client credentials must be base64 encoded
4. **Workspace Context**: Returns workspace information during token exchange

### Direct API Implementation
Implemented 9 comprehensive tools:
- **Search & Discovery**: Search, ListDatabases
- **Database Operations**: QueryDatabase, CreateDatabase
- **Page Operations**: CreatePage, GetPage, UpdatePage
- **Content Management**: GetBlocks, AppendBlocks

### Key Characteristics
- **Token Simplicity**: No refresh mechanism needed - tokens persist indefinitely
- **Rich Metadata**: Token exchange returns workspace details, bot ID, and owner info
- **Block-Based Content**: All content is structured as blocks with various types
- **Property System**: Flexible property types for database entries

### Environment Variables Required
```bash
NOTION_CLIENT_ID=your_oauth_client_id      # From Notion Integration page
NOTION_CLIENT_SECRET=your_oauth_secret     # From Notion Integration page
NOTION_OAUTH_REDIRECT_URI=http://localhost:8000/api/connectors/notion/callback
```

### Implementation Highlights
- **No PKCE Required**: Unlike Atlassian, Notion doesn't require PKCE
- **Owner Parameter**: Must include `owner=user` in authorization URL
- **API Versioning**: Uses Notion-Version header (currently 2022-06-28)
- **Pagination Built-in**: All list endpoints support pagination

## Metrics and Improvements

### Before Optimization
- Token refresh: 9 times per tool load
- Tool loading delay: ~8 seconds
- API calls: O(n) where n = number of tools

### After Optimization
- Token refresh: 1 time per tool load (if needed)
- Tool loading delay: <1 second
- API calls: O(1) for batch operations

## Connector Implementation Summary

### Current Connectors Status
| Provider | OAuth | Direct API | MCP Support | Token Refresh | Production Ready |
|----------|--------|------------|-------------|---------------|------------------|
| Google   | ✅     | ✅         | ❌          | ✅            | ✅               |
| Atlassian| ✅     | ✅         | ⚠️ (Issues)  | ✅            | ✅               |
| PayPal   | ✅     | ✅         | ❌ (Arch)    | ✅            | ✅               |
| Notion   | ✅     | ✅         | ❌ (Skip)    | N/A           | ✅               |

### Key Technical Insights
1. **MCP is not ready for multi-user SaaS**: Designed for single-user subprocess models
2. **Direct API is more reliable**: Better error handling, debugging, and control
3. **OAuth implementations vary wildly**: Each provider has unique requirements
4. **Token management is critical**: Poor refresh logic can cause significant delays

## Future Considerations

1. **Implement token refresh prediction** - Refresh before expiry to avoid delays
2. **Add connector health monitoring** - Track OAuth success rates
3. **Create connector testing framework** - Automated tests for OAuth flows
4. **Standardize error codes** - Consistent error handling across connectors
5. **Implement circuit breaker pattern** - Prevent cascading failures
6. **Consider GraphQL for Notion** - May provide more efficient data fetching
7. **Add webhook support** - Real-time updates for supported providers

## Conclusion

The key to successful connector implementation is flexibility and defensive programming. After implementing four major connectors, it's clear that:

1. **MCP is aspirational, not practical** for production multi-user applications
2. **Direct API implementation should be the default** approach
3. **Each provider requires deep understanding** of their specific OAuth quirks
4. **Performance optimization is crucial** - batch operations and smart token management
5. **Documentation and error messages matter** - Users need clear guidance when connections fail

Always assume external services may fail or change, and design systems that can adapt gracefully. The promise of MCP standardization remains unfulfilled, making robust direct API implementations the cornerstone of reliable integrations.