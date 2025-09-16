"""
PayPal Direct API Connector

This connector implements direct PayPal REST API calls for multi-user support.
Similar to the Atlassian direct connector, this bypasses MCP and directly calls PayPal APIs.
"""

import json
from typing import Any, Dict, List, Optional, Type
from datetime import datetime, timedelta
from decimal import Decimal

import httpx
import structlog
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from agents.connectors.providers.paypal.paypal_connector import PayPalConnector

logger = structlog.get_logger(__name__)


class PayPalDirectConnector(PayPalConnector):
    """
    PayPal direct API connector.
    
    This connector provides direct access to PayPal REST APIs without using MCP.
    It's designed for production use with multi-user support.
    """
    
    def __init__(self, redis_storage):
        """Initialize PayPal direct connector."""
        super().__init__(redis_storage)
        self.api_base_url = "https://api-m.sandbox.paypal.com" if self.is_sandbox else "https://api-m.paypal.com"
    
    async def _make_api_request(
        self,
        method: str,
        endpoint: str,
        user_id: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make a direct API request to PayPal.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE, PATCH)
            endpoint: API endpoint path (e.g., "/v1/catalogs/products")
            user_id: User ID for token retrieval
            data: Request body data
            params: Query parameters
        
        Returns:
            API response as dictionary
        """
        # Get user token
        token = await self.get_user_token(user_id, auto_refresh=True)
        if not token:
            return {"error": "No valid token found for user"}
        
        # Build full URL
        url = f"{self.api_base_url}{endpoint}"
        
        headers = {
            "Authorization": f"Bearer {token.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Prefer": "return=representation"  # Get full response
        }
        
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    json=data,
                    params=params,
                    headers=headers
                )
                
                # Log the request for debugging
                logger.debug(
                    "PayPal API request",
                    method=method,
                    url=url,
                    status_code=response.status_code
                )
                
                # Handle different response codes
                if response.status_code == 204:
                    # No content response
                    return {"success": True}
                elif response.status_code >= 200 and response.status_code < 300:
                    # Success response
                    if response.text:
                        return response.json()
                    else:
                        return {"success": True}
                else:
                    # Error response
                    error_data = {}
                    if response.text:
                        try:
                            error_data = response.json()
                        except:
                            error_data = {"message": response.text}
                    
                    logger.error(
                        "PayPal API error",
                        status_code=response.status_code,
                        error=error_data
                    )
                    
                    return {
                        "error": error_data.get("message", f"API request failed with status {response.status_code}"),
                        "details": error_data
                    }
                    
        except httpx.TimeoutException:
            logger.error("PayPal API timeout", endpoint=endpoint)
            return {"error": "Request timed out"}
        except Exception as e:
            logger.error("PayPal API request failed", endpoint=endpoint, error=str(e))
            return {"error": f"Request failed: {str(e)}"}
    
    async def create_langchain_tools(
        self,
        user_id: str,
        tool_ids: Optional[List[str]] = None
    ) -> List[BaseTool]:
        """Create LangChain tools for PayPal direct API."""
        # Get available tools
        available_tools = await self.get_user_tools(user_id)
        if not available_tools:
            logger.warning(f"No tools available for user {user_id}")
            return []
        
        # Filter tools if specific IDs requested
        if tool_ids:
            available_tools = [
                tool for tool in available_tools
                if tool.id in tool_ids
            ]
        
        # Create tool classes
        langchain_tools = []
        
        for tool in available_tools:
            tool_class = self._get_tool_class(tool.id)
            if tool_class:
                tool_instance = tool_class(
                    connector=self,
                    user_id=user_id
                )
                langchain_tools.append(tool_instance)
                logger.info(
                    f"Created PayPal direct tool: {tool.id}",
                    user_id=user_id
                )
        
        logger.info(
            f"Created PayPal direct tools",
            user_id=user_id,
            num_tools=len(langchain_tools)
        )
        
        return langchain_tools
    
    def _get_tool_class(self, tool_id: str) -> Optional[Type[BaseTool]]:
        """Get the tool class for a given tool ID."""
        tool_map = {
            "create_product": CreateProductTool,
            "list_product": ListProductsTool,
            "show_product_details": ShowProductDetailsTool,
            "create_invoice": CreateInvoiceTool,
            "list_invoices": ListInvoicesTool,
            "get_invoice": GetInvoiceTool,
            "send_invoice": SendInvoiceTool,
            "send_invoice_reminder": SendInvoiceReminderTool,
            "cancel_sent_invoice": CancelSentInvoiceTool,
            "list_disputes": ListDisputesTool,
            "get_dispute": GetDisputeTool,
            "accept_dispute_claim": AcceptDisputeClaimTool,
        }
        
        return tool_map.get(tool_id)


# ============================================================================
# Tool Input Models
# ============================================================================

class CreateProductInput(BaseModel):
    """Input for creating a product."""
    name: str = Field(description="Product name")
    description: Optional[str] = Field(None, description="Product description")
    type: str = Field(default="SERVICE", description="Product type (PHYSICAL, DIGITAL, SERVICE)")
    category: Optional[str] = Field(None, description="Product category")
    image_url: Optional[str] = Field(None, description="Product image URL")
    home_url: Optional[str] = Field(None, description="Product home page URL")


class ListProductsInput(BaseModel):
    """Input for listing products."""
    page_size: int = Field(default=10, description="Number of items per page (1-20)")
    page: int = Field(default=1, description="Page number (1-based)")


class ShowProductDetailsInput(BaseModel):
    """Input for showing product details."""
    product_id: str = Field(description="Product ID")


class CreateInvoiceInput(BaseModel):
    """Input for creating an invoice."""
    recipient_email: str = Field(description="Recipient email address")
    items: List[Dict[str, Any]] = Field(description="Invoice items with name, quantity, unit_amount")
    currency_code: str = Field(default="USD", description="Currency code (e.g., USD, EUR)")
    note: Optional[str] = Field(None, description="Note to the payer")
    terms: Optional[str] = Field(None, description="Terms and conditions")
    memo: Optional[str] = Field(None, description="Private memo")


class ListInvoicesInput(BaseModel):
    """Input for listing invoices."""
    page_size: int = Field(default=10, description="Number of items per page (1-20)")
    page: int = Field(default=1, description="Page number (1-based)")
    status: Optional[str] = Field(None, description="Filter by status (DRAFT, SENT, PAID, etc.)")


class GetInvoiceInput(BaseModel):
    """Input for getting invoice details."""
    invoice_id: str = Field(description="Invoice ID")


class SendInvoiceInput(BaseModel):
    """Input for sending an invoice."""
    invoice_id: str = Field(description="Invoice ID to send")
    subject: Optional[str] = Field(None, description="Email subject")
    note: Optional[str] = Field(None, description="Note to recipient")
    send_to_invoicer: bool = Field(default=False, description="Send copy to invoicer")


class SendInvoiceReminderInput(BaseModel):
    """Input for sending invoice reminder."""
    invoice_id: str = Field(description="Invoice ID")
    subject: Optional[str] = Field(None, description="Email subject")
    note: Optional[str] = Field(None, description="Note to recipient")


class CancelSentInvoiceInput(BaseModel):
    """Input for canceling a sent invoice."""
    invoice_id: str = Field(description="Invoice ID to cancel")
    subject: Optional[str] = Field(None, description="Email subject")
    note: Optional[str] = Field(None, description="Note to recipient")
    send_to_invoicer: bool = Field(default=False, description="Send copy to invoicer")
    send_to_recipient: bool = Field(default=True, description="Send to recipient")


class ListDisputesInput(BaseModel):
    """Input for listing disputes."""
    page_size: int = Field(default=10, description="Number of items per page (1-50)")
    start_time: Optional[str] = Field(None, description="Start time (ISO 8601)")
    disputed_transaction_id: Optional[str] = Field(None, description="Transaction ID")


class GetDisputeInput(BaseModel):
    """Input for getting dispute details."""
    dispute_id: str = Field(description="Dispute ID")


class AcceptDisputeClaimInput(BaseModel):
    """Input for accepting a dispute claim."""
    dispute_id: str = Field(description="Dispute ID")
    note: Optional[str] = Field(None, description="Notes about accepting the claim")
    accept_claim_reason: Optional[str] = Field(None, description="Reason for accepting")


# ============================================================================
# Tool Implementations
# ============================================================================

class PayPalDirectTool(BaseTool):
    """Base class for PayPal direct API tools."""
    connector: PayPalDirectConnector = Field(exclude=True)
    user_id: str = Field(exclude=True)
    
    class Config:
        arbitrary_types_allowed = True


class CreateProductTool(PayPalDirectTool):
    """Create a product in PayPal catalog."""
    name: str = "paypal_create_product"
    description: str = "Create a new product in PayPal catalog"
    args_schema: Type[BaseModel] = CreateProductInput
    
    async def _arun(self, **kwargs) -> str:
        """Create a product."""
        # Build request data
        data = {
            "name": kwargs["name"],
            "type": kwargs.get("type", "SERVICE"),
        }
        
        if kwargs.get("description"):
            data["description"] = kwargs["description"]
        if kwargs.get("category"):
            data["category"] = kwargs["category"]
        if kwargs.get("image_url"):
            data["image_url"] = kwargs["image_url"]
        if kwargs.get("home_url"):
            data["home_url"] = kwargs["home_url"]
        
        result = await self.connector._make_api_request(
            method="POST",
            endpoint="/v1/catalogs/products",
            user_id=self.user_id,
            data=data
        )
        
        if "error" in result:
            return f"Error creating product: {result['error']}"
        
        return f"Product created successfully. ID: {result.get('id', 'Unknown')}"
    
    def _run(self, **kwargs) -> str:
        """Sync version."""
        import asyncio
        return asyncio.run(self._arun(**kwargs))


class ListProductsTool(PayPalDirectTool):
    """List products from PayPal catalog."""
    name: str = "paypal_list_product"
    description: str = "List products from PayPal catalog"
    args_schema: Type[BaseModel] = ListProductsInput
    
    async def _arun(self, **kwargs) -> str:
        """List products."""
        params = {
            "page_size": min(kwargs.get("page_size", 10), 20),
            "page": kwargs.get("page", 1)
        }
        
        result = await self.connector._make_api_request(
            method="GET",
            endpoint="/v1/catalogs/products",
            user_id=self.user_id,
            params=params
        )
        
        if "error" in result:
            return f"Error listing products: {result['error']}"
        
        products = result.get("products", [])
        if not products:
            return "No products found."
        
        output = f"Found {len(products)} products:\n"
        for product in products:
            output += f"- {product['name']} (ID: {product['id']}, Type: {product.get('type', 'N/A')})\n"
        
        return output
    
    def _run(self, **kwargs) -> str:
        """Sync version."""
        import asyncio
        return asyncio.run(self._arun(**kwargs))


class ShowProductDetailsTool(PayPalDirectTool):
    """Show product details."""
    name: str = "paypal_show_product_details"
    description: str = "Get details of a specific product"
    args_schema: Type[BaseModel] = ShowProductDetailsInput
    
    async def _arun(self, **kwargs) -> str:
        """Get product details."""
        result = await self.connector._make_api_request(
            method="GET",
            endpoint=f"/v1/catalogs/products/{kwargs['product_id']}",
            user_id=self.user_id
        )
        
        if "error" in result:
            return f"Error getting product details: {result['error']}"
        
        output = f"Product Details:\n"
        output += f"- ID: {result['id']}\n"
        output += f"- Name: {result['name']}\n"
        output += f"- Type: {result.get('type', 'N/A')}\n"
        output += f"- Description: {result.get('description', 'N/A')}\n"
        output += f"- Category: {result.get('category', 'N/A')}\n"
        output += f"- Create Time: {result.get('create_time', 'N/A')}\n"
        
        return output
    
    def _run(self, **kwargs) -> str:
        """Sync version."""
        import asyncio
        return asyncio.run(self._arun(**kwargs))


class CreateInvoiceTool(PayPalDirectTool):
    """Create an invoice."""
    name: str = "paypal_create_invoice"
    description: str = "Create a new invoice"
    args_schema: Type[BaseModel] = CreateInvoiceInput
    
    async def _arun(self, **kwargs) -> str:
        """Create an invoice."""
        # Build invoice data
        items = []
        for item in kwargs["items"]:
            items.append({
                "name": item["name"],
                "quantity": str(item.get("quantity", 1)),
                "unit_amount": {
                    "currency_code": kwargs.get("currency_code", "USD"),
                    "value": str(item["unit_amount"])
                }
            })
        
        data = {
            "detail": {
                "currency_code": kwargs.get("currency_code", "USD"),
                "note": kwargs.get("note", ""),
                "terms_and_conditions": kwargs.get("terms", ""),
                "memo": kwargs.get("memo", "")
            },
            "invoicer": {
                "name": {
                    "given_name": "PayPal",
                    "surname": "User"
                }
            },
            "primary_recipients": [{
                "billing_info": {
                    "email_address": kwargs["recipient_email"]
                }
            }],
            "items": items
        }
        
        result = await self.connector._make_api_request(
            method="POST",
            endpoint="/v2/invoicing/invoices",
            user_id=self.user_id,
            data=data
        )
        
        if "error" in result:
            return f"Error creating invoice: {result['error']}"
        
        return f"Invoice created successfully. ID: {result.get('id', 'Unknown')}"
    
    def _run(self, **kwargs) -> str:
        """Sync version."""
        import asyncio
        return asyncio.run(self._arun(**kwargs))


class ListInvoicesTool(PayPalDirectTool):
    """List invoices."""
    name: str = "paypal_list_invoices"
    description: str = "List all invoices"
    args_schema: Type[BaseModel] = ListInvoicesInput
    
    async def _arun(self, **kwargs) -> str:
        """List invoices."""
        params = {
            "page_size": min(kwargs.get("page_size", 10), 20),
            "page": kwargs.get("page", 1)
        }
        
        if kwargs.get("status"):
            params["status"] = kwargs["status"]
        
        result = await self.connector._make_api_request(
            method="GET",
            endpoint="/v2/invoicing/invoices",
            user_id=self.user_id,
            params=params
        )
        
        if "error" in result:
            return f"Error listing invoices: {result['error']}"
        
        invoices = result.get("items", [])
        if not invoices:
            return "No invoices found."
        
        output = f"Found {len(invoices)} invoices:\n"
        for invoice in invoices:
            detail = invoice.get("detail", {})
            amount = invoice.get("amount", {})
            output += f"- Invoice #{invoice.get('invoice_number', 'N/A')} "
            output += f"(ID: {invoice['id']}, Status: {invoice.get('status', 'N/A')}, "
            output += f"Amount: {amount.get('currency_code', '')} {amount.get('value', '0')})\n"
        
        return output
    
    def _run(self, **kwargs) -> str:
        """Sync version."""
        import asyncio
        return asyncio.run(self._arun(**kwargs))


class GetInvoiceTool(PayPalDirectTool):
    """Get invoice details."""
    name: str = "paypal_get_invoice"
    description: str = "Get details of a specific invoice"
    args_schema: Type[BaseModel] = GetInvoiceInput
    
    async def _arun(self, **kwargs) -> str:
        """Get invoice details."""
        result = await self.connector._make_api_request(
            method="GET",
            endpoint=f"/v2/invoicing/invoices/{kwargs['invoice_id']}",
            user_id=self.user_id
        )
        
        if "error" in result:
            return f"Error getting invoice: {result['error']}"
        
        detail = result.get("detail", {})
        amount = result.get("amount", {})
        
        output = f"Invoice Details:\n"
        output += f"- ID: {result['id']}\n"
        output += f"- Number: {result.get('invoice_number', 'N/A')}\n"
        output += f"- Status: {result.get('status', 'N/A')}\n"
        output += f"- Amount: {amount.get('currency_code', '')} {amount.get('value', '0')}\n"
        output += f"- Invoice Date: {detail.get('invoice_date', 'N/A')}\n"
        
        return output
    
    def _run(self, **kwargs) -> str:
        """Sync version."""
        import asyncio
        return asyncio.run(self._arun(**kwargs))


class SendInvoiceTool(PayPalDirectTool):
    """Send an invoice."""
    name: str = "paypal_send_invoice"
    description: str = "Send an invoice to customer"
    args_schema: Type[BaseModel] = SendInvoiceInput
    
    async def _arun(self, **kwargs) -> str:
        """Send an invoice."""
        data = {
            "send_to_invoicer": kwargs.get("send_to_invoicer", False)
        }
        
        if kwargs.get("subject"):
            data["subject"] = kwargs["subject"]
        if kwargs.get("note"):
            data["note"] = kwargs["note"]
        
        result = await self.connector._make_api_request(
            method="POST",
            endpoint=f"/v2/invoicing/invoices/{kwargs['invoice_id']}/send",
            user_id=self.user_id,
            data=data
        )
        
        if "error" in result:
            return f"Error sending invoice: {result['error']}"
        
        return f"Invoice {kwargs['invoice_id']} sent successfully."
    
    def _run(self, **kwargs) -> str:
        """Sync version."""
        import asyncio
        return asyncio.run(self._arun(**kwargs))


class SendInvoiceReminderTool(PayPalDirectTool):
    """Send invoice reminder."""
    name: str = "paypal_send_invoice_reminder"
    description: str = "Send a reminder for an invoice"
    args_schema: Type[BaseModel] = SendInvoiceReminderInput
    
    async def _arun(self, **kwargs) -> str:
        """Send invoice reminder."""
        data = {}
        
        if kwargs.get("subject"):
            data["subject"] = kwargs["subject"]
        if kwargs.get("note"):
            data["note"] = kwargs["note"]
        
        result = await self.connector._make_api_request(
            method="POST",
            endpoint=f"/v2/invoicing/invoices/{kwargs['invoice_id']}/remind",
            user_id=self.user_id,
            data=data
        )
        
        if "error" in result:
            return f"Error sending reminder: {result['error']}"
        
        return f"Reminder sent for invoice {kwargs['invoice_id']}."
    
    def _run(self, **kwargs) -> str:
        """Sync version."""
        import asyncio
        return asyncio.run(self._arun(**kwargs))


class CancelSentInvoiceTool(PayPalDirectTool):
    """Cancel a sent invoice."""
    name: str = "paypal_cancel_sent_invoice"
    description: str = "Cancel an invoice that was sent"
    args_schema: Type[BaseModel] = CancelSentInvoiceInput
    
    async def _arun(self, **kwargs) -> str:
        """Cancel sent invoice."""
        data = {
            "send_to_invoicer": kwargs.get("send_to_invoicer", False),
            "send_to_recipient": kwargs.get("send_to_recipient", True)
        }
        
        if kwargs.get("subject"):
            data["subject"] = kwargs["subject"]
        if kwargs.get("note"):
            data["note"] = kwargs["note"]
        
        result = await self.connector._make_api_request(
            method="POST",
            endpoint=f"/v2/invoicing/invoices/{kwargs['invoice_id']}/cancel",
            user_id=self.user_id,
            data=data
        )
        
        if "error" in result:
            return f"Error canceling invoice: {result['error']}"
        
        return f"Invoice {kwargs['invoice_id']} canceled successfully."
    
    def _run(self, **kwargs) -> str:
        """Sync version."""
        import asyncio
        return asyncio.run(self._arun(**kwargs))


class ListDisputesTool(PayPalDirectTool):
    """List disputes."""
    name: str = "paypal_list_disputes"
    description: str = "List all disputes"
    args_schema: Type[BaseModel] = ListDisputesInput
    
    async def _arun(self, **kwargs) -> str:
        """List disputes."""
        params = {
            "page_size": min(kwargs.get("page_size", 10), 50)
        }
        
        if kwargs.get("start_time"):
            params["start_time"] = kwargs["start_time"]
        if kwargs.get("disputed_transaction_id"):
            params["disputed_transaction_id"] = kwargs["disputed_transaction_id"]
        
        result = await self.connector._make_api_request(
            method="GET",
            endpoint="/v1/customer-disputes",
            user_id=self.user_id,
            params=params
        )
        
        if "error" in result:
            return f"Error listing disputes: {result['error']}"
        
        disputes = result.get("items", [])
        if not disputes:
            return "No disputes found."
        
        output = f"Found {len(disputes)} disputes:\n"
        for dispute in disputes:
            output += f"- Dispute {dispute['dispute_id']} "
            output += f"(Status: {dispute.get('status', 'N/A')}, "
            output += f"Reason: {dispute.get('reason', 'N/A')}, "
            output += f"Amount: {dispute.get('dispute_amount', {}).get('currency_code', '')} "
            output += f"{dispute.get('dispute_amount', {}).get('value', '0')})\n"
        
        return output
    
    def _run(self, **kwargs) -> str:
        """Sync version."""
        import asyncio
        return asyncio.run(self._arun(**kwargs))


class GetDisputeTool(PayPalDirectTool):
    """Get dispute details."""
    name: str = "paypal_get_dispute"
    description: str = "Get details of a specific dispute"
    args_schema: Type[BaseModel] = GetDisputeInput
    
    async def _arun(self, **kwargs) -> str:
        """Get dispute details."""
        result = await self.connector._make_api_request(
            method="GET",
            endpoint=f"/v1/customer-disputes/{kwargs['dispute_id']}",
            user_id=self.user_id
        )
        
        if "error" in result:
            return f"Error getting dispute: {result['error']}"
        
        output = f"Dispute Details:\n"
        output += f"- ID: {result['dispute_id']}\n"
        output += f"- Status: {result.get('status', 'N/A')}\n"
        output += f"- Reason: {result.get('reason', 'N/A')}\n"
        output += f"- Amount: {result.get('dispute_amount', {}).get('currency_code', '')} "
        output += f"{result.get('dispute_amount', {}).get('value', '0')}\n"
        output += f"- Create Time: {result.get('create_time', 'N/A')}\n"
        
        return output
    
    def _run(self, **kwargs) -> str:
        """Sync version."""
        import asyncio
        return asyncio.run(self._arun(**kwargs))


class AcceptDisputeClaimTool(PayPalDirectTool):
    """Accept a dispute claim."""
    name: str = "paypal_accept_dispute_claim"
    description: str = "Accept a dispute claim"
    args_schema: Type[BaseModel] = AcceptDisputeClaimInput
    
    async def _arun(self, **kwargs) -> str:
        """Accept dispute claim."""
        data = {}
        
        if kwargs.get("note"):
            data["note"] = kwargs["note"]
        if kwargs.get("accept_claim_reason"):
            data["accept_claim_reason"] = kwargs["accept_claim_reason"]
        
        result = await self.connector._make_api_request(
            method="POST",
            endpoint=f"/v1/customer-disputes/{kwargs['dispute_id']}/accept-claim",
            user_id=self.user_id,
            data=data
        )
        
        if "error" in result:
            return f"Error accepting dispute claim: {result['error']}"
        
        return f"Dispute claim {kwargs['dispute_id']} accepted successfully."
    
    def _run(self, **kwargs) -> str:
        """Sync version."""
        import asyncio
        return asyncio.run(self._arun(**kwargs))