"""
OpenAI Responses API Compatible Models
Based on: https://platform.openai.com/docs/api-reference/responses
"""
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


# Request Models
class ResponseInputTextItem(BaseModel):
    """Text input item."""
    type: Literal["text"] = "text"
    text: str


class ResponseInputImageSource(BaseModel):
    """Image source for input."""
    type: Literal["url", "base64"] = "url"
    url: Optional[str] = None
    base64: Optional[str] = None


class ResponseInputImageItem(BaseModel):
    """Image input item."""
    type: Literal["image"] = "image"
    source: ResponseInputImageSource


ResponseInputItem = Union[ResponseInputTextItem, ResponseInputImageItem]


class ResponseToolFunction(BaseModel):
    """Function definition for a tool."""
    name: str
    description: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None


class ResponseTool(BaseModel):
    """Tool definition in OpenAI format."""
    type: Literal["function"] = "function"
    function: ResponseToolFunction


class ResponseRequest(BaseModel):
    """OpenAI Responses API request schema."""
    model: str = Field(..., description="Model identifier (e.g., 'mainagent', 'financialanalysis')")
    input: Union[str, List[ResponseInputItem]] = Field(..., description="Input text or structured input items")
    tools: Optional[List[ResponseTool]] = Field(None, description="Available tools/functions")
    stream: Optional[bool] = Field(False, description="Whether to stream the response")
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: Optional[int] = Field(None, gt=0, description="Maximum tokens to generate")
    metadata: Optional[Dict[str, str]] = Field(None, description="Optional metadata")


# Response Models
class ResponseUsage(BaseModel):
    """Token usage information."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ResponseOutputText(BaseModel):
    """Text output item."""
    type: Literal["text"] = "text"
    text: str


class ResponseFunctionCall(BaseModel):
    """Function call information."""
    name: str
    arguments: str  # JSON string


class ResponseOutputFunctionCall(BaseModel):
    """Function call output item."""
    type: Literal["function_call"] = "function_call"
    function_call: ResponseFunctionCall


ResponseOutputItem = Union[ResponseOutputText, ResponseOutputFunctionCall]


class ResponseStatus(str, Enum):
    """Response status values."""
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ResponseObject(BaseModel):
    """Main response object (non-streaming)."""
    id: str = Field(..., description="Unique response identifier")
    object: Literal["response"] = "response"
    created: int = Field(..., description="Unix timestamp of creation")
    model: str = Field(..., description="Model used")
    status: ResponseStatus = Field(..., description="Response status")
    output: List[ResponseOutputItem] = Field(default_factory=list, description="Output items")
    usage: Optional[ResponseUsage] = Field(None, description="Token usage")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional metadata (supports custom extensions like artifacts)")


# Streaming Event Models
class StreamEventResponseCreated(BaseModel):
    """Event: response.created"""
    event: Literal["response.created"] = "response.created"
    data: ResponseObject


class StreamEventOutputTextDelta(BaseModel):
    """Event: response.output_text.delta - token-by-token streaming"""
    event: Literal["response.output_text.delta"] = "response.output_text.delta"
    data: Dict[str, Any] = Field(
        ...,
        description="Delta data with 'delta' key containing incremental text"
    )


class StreamEventOutputItemAdded(BaseModel):
    """Event: response.output_item.added - when complete items are added"""
    event: Literal["response.output_item.added"] = "response.output_item.added"
    data: Dict[str, Any] = Field(
        ...,
        description="Output item data"
    )


class StreamEventResponseCompleted(BaseModel):
    """Event: response.completed - final event with full response"""
    event: Literal["response.completed"] = "response.completed"
    data: ResponseObject


class StreamEventResponseFailed(BaseModel):
    """Event: response.failed - error event"""
    event: Literal["response.failed"] = "response.failed"
    data: Dict[str, Any] = Field(
        ...,
        description="Error information"
    )


StreamEvent = Union[
    StreamEventResponseCreated,
    StreamEventOutputTextDelta,
    StreamEventOutputItemAdded,
    StreamEventResponseCompleted,
    StreamEventResponseFailed,
]


# Error Models
class OpenAIError(BaseModel):
    """OpenAI-compatible error response."""
    error: Dict[str, Any] = Field(
        ...,
        description="Error object with 'message', 'type', 'code' fields"
    )


def create_error_response(message: str, error_type: str = "invalid_request_error", code: Optional[str] = None) -> OpenAIError:
    """Create an OpenAI-compatible error response."""
    error_obj = {
        "message": message,
        "type": error_type,
    }
    if code:
        error_obj["code"] = code
    return OpenAIError(error=error_obj)
