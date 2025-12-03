"""
Gemini 3.0 Integration Module
Handles streaming responses and function-calling for Broker Copilot.
"""
import os
import json
import asyncio
import httpx
from typing import Dict, Any, List, AsyncGenerator, Optional, Callable
from dataclasses import dataclass, field

from ..core.logging import get_logger
from ..core.exceptions import (
    LLMError,
    LLMAPIError,
    LLMRateLimitError,
    LLMContentFilterError,
    LLMFunctionError,
    ConfigurationError,
)

logger = get_logger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}"


@dataclass
class FunctionDeclaration:
    """Represents a function that can be called by Gemini."""
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema for parameters


@dataclass
class GeminiConfig:
    """Configuration for Gemini API calls."""
    temperature: float = 0.3
    max_output_tokens: int = 2048
    top_p: float = 0.95
    top_k: int = 40
    system_instruction: str = ""
    functions: List[FunctionDeclaration] = field(default_factory=list)


class GeminiClient:
    """Async client for Google Gemini API with streaming and function-calling support."""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or GEMINI_API_KEY
        self.base_url = GEMINI_API_URL

    def _build_headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
        }

    def _build_function_declarations(self, functions: List[FunctionDeclaration]) -> List[Dict]:
        """Convert function declarations to Gemini API format."""
        return [
            {
                "name": f.name,
                "description": f.description,
                "parameters": f.parameters
            }
            for f in functions
        ]

    def _build_request_body(
        self,
        messages: List[Dict[str, Any]],
        config: GeminiConfig
    ) -> Dict[str, Any]:
        """Build the request body for Gemini API."""
        body = {
            "contents": messages,
            "generationConfig": {
                "temperature": config.temperature,
                "maxOutputTokens": config.max_output_tokens,
                "topP": config.top_p,
                "topK": config.top_k,
            }
        }

        if config.system_instruction:
            body["systemInstruction"] = {
                "parts": [{"text": config.system_instruction}]
            }

        if config.functions:
            body["tools"] = [{
                "functionDeclarations": self._build_function_declarations(config.functions)
            }]

        return body

    async def generate(
        self,
        messages: List[Dict[str, Any]],
        config: GeminiConfig = None
    ) -> Dict[str, Any]:
        """Generate a non-streaming response from Gemini."""
        if not self.api_key:
            logger.error("Gemini API key not configured")
            raise ConfigurationError("GEMINI_API_KEY not configured")
        
        config = config or GeminiConfig()
        body = self._build_request_body(messages, config)
        url = f"{self.base_url}:generateContent?key={self.api_key}"

        logger.debug(f"Sending request to Gemini (model: {GEMINI_MODEL})")
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, json=body, headers=self._build_headers())
                
                if response.status_code == 429:
                    logger.warning("Gemini rate limit exceeded")
                    raise LLMRateLimitError(
                        "Gemini API rate limit exceeded",
                        service_name="gemini"
                    )
                
                if response.status_code == 400:
                    error_data = response.json()
                    error_msg = error_data.get("error", {}).get("message", "Bad request")
                    if "safety" in error_msg.lower() or "block" in error_msg.lower():
                        logger.warning(f"Content filtered by Gemini: {error_msg}")
                        raise LLMContentFilterError(
                            f"Content blocked by safety filter: {error_msg}",
                            context={"error": error_data}
                        )
                    raise LLMAPIError(
                        f"Gemini API error: {error_msg}",
                        context={"status_code": 400, "error": error_data}
                    )
                
                response.raise_for_status()
                result = response.json()
                logger.debug("Gemini response received successfully")
                return result
                
        except httpx.TimeoutException:
            logger.error("Gemini request timed out")
            raise LLMError("Gemini request timed out", context={"timeout": 60})
        except httpx.HTTPError as e:
            logger.error(f"HTTP error calling Gemini: {e}")
            raise LLMAPIError(f"HTTP error: {str(e)}", cause=e)

    async def generate_stream(
        self,
        messages: List[Dict[str, Any]],
        config: GeminiConfig = None
    ) -> AsyncGenerator[str, None]:
        """Generate a streaming response from Gemini, yielding text chunks."""
        if not self.api_key:
            logger.error("Gemini API key not configured")
            raise ConfigurationError("GEMINI_API_KEY not configured")
        
        config = config or GeminiConfig()
        body = self._build_request_body(messages, config)
        url = f"{self.base_url}:streamGenerateContent?alt=sse&key={self.api_key}"

        logger.debug(f"Starting streaming request to Gemini")
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream("POST", url, json=body, headers=self._build_headers()) as response:
                    if response.status_code == 429:
                        raise LLMRateLimitError("Gemini rate limit exceeded", service_name="gemini")
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]
                            if data.strip() == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            # Extract text from the response
                            candidates = chunk.get("candidates", [])
                            if candidates:
                                content = candidates[0].get("content", {})
                                parts = content.get("parts", [])
                                for part in parts:
                                    if "text" in part:
                                        yield part["text"]
                        except json.JSONDecodeError:
                            continue

    async def generate_with_functions(
        self,
        messages: List[Dict[str, Any]],
        config: GeminiConfig,
        function_handlers: Dict[str, Callable]
    ) -> Dict[str, Any]:
        """
        Generate a response with function-calling support.
        Automatically executes function calls and continues the conversation.
        Returns the final response with all function call results.
        """
        conversation = list(messages)
        function_results = []
        max_iterations = 5  # Prevent infinite loops

        for _ in range(max_iterations):
            result = await self.generate(conversation, config)

            candidates = result.get("candidates", [])
            if not candidates:
                break

            content = candidates[0].get("content", {})
            parts = content.get("parts", [])

            # Check for function calls
            function_calls = [p for p in parts if "functionCall" in p]

            if not function_calls:
                # No more function calls, return the final text response
                text_parts = [p.get("text", "") for p in parts if "text" in p]
                return {
                    "text": "".join(text_parts),
                    "function_results": function_results,
                    "raw_response": result
                }

            # Execute function calls
            for fc_part in function_calls:
                fc = fc_part["functionCall"]
                func_name = fc["name"]
                func_args = fc.get("args", {})

                if func_name in function_handlers:
                    try:
                        # Execute the function
                        handler = function_handlers[func_name]
                        if asyncio.iscoroutinefunction(handler):
                            func_result = await handler(**func_args)
                        else:
                            func_result = handler(**func_args)

                        function_results.append({
                            "function": func_name,
                            "args": func_args,
                            "result": func_result
                        })

                        # Add the model's response to conversation
                        conversation.append({
                            "role": "model",
                            "parts": [fc_part]
                        })

                        # Add function response to conversation
                        conversation.append({
                            "role": "function",
                            "parts": [{
                                "functionResponse": {
                                    "name": func_name,
                                    "response": {"result": func_result}
                                }
                            }]
                        })

                    except Exception as e:
                        function_results.append({
                            "function": func_name,
                            "args": func_args,
                            "error": str(e)
                        })
                        # Add error response
                        conversation.append({
                            "role": "model",
                            "parts": [fc_part]
                        })
                        conversation.append({
                            "role": "function",
                            "parts": [{
                                "functionResponse": {
                                    "name": func_name,
                                    "response": {"error": str(e)}
                                }
                            }]
                        })
                else:
                    # Unknown function
                    conversation.append({
                        "role": "model",
                        "parts": [fc_part]
                    })
                    conversation.append({
                        "role": "function",
                        "parts": [{
                            "functionResponse": {
                                "name": func_name,
                                "response": {"error": f"Unknown function: {func_name}"}
                            }
                        }]
                    })

        # Max iterations reached
        return {
            "text": "Maximum function call iterations reached.",
            "function_results": function_results,
            "raw_response": result
        }


# Singleton client instance
_client: Optional[GeminiClient] = None


def get_gemini_client() -> GeminiClient:
    """Get or create the Gemini client singleton."""
    global _client
    if _client is None:
        _client = GeminiClient()
    return _client


# Pre-defined function declarations for Broker Copilot

BROKER_FUNCTIONS = [
    FunctionDeclaration(
        name="get_policy_details",
        description="Retrieve details about a specific insurance policy by its ID. Returns policy number, client name, premium, expiry date, and other metadata.",
        parameters={
            "type": "object",
            "properties": {
                "policy_id": {
                    "type": "string",
                    "description": "The unique identifier of the policy (e.g., 'POL-123')"
                }
            },
            "required": ["policy_id"]
        }
    ),
    FunctionDeclaration(
        name="find_emails",
        description="Search for emails related to a client, policy, or topic. Returns a list of email snippets with subjects, timestamps, and links.",
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query for finding relevant emails"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of emails to return (default 5)"
                }
            },
            "required": ["query"]
        }
    ),
    FunctionDeclaration(
        name="find_meetings",
        description="Search for calendar meetings related to a client or policy. Returns meeting details with timestamps and links.",
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query for finding relevant meetings"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of meetings to return (default 5)"
                }
            },
            "required": ["query"]
        }
    ),
    FunctionDeclaration(
        name="get_client_info",
        description="Retrieve information about a client by name or ID. Returns contact details and associated policies.",
        parameters={
            "type": "object",
            "properties": {
                "client_identifier": {
                    "type": "string",
                    "description": "Client name or ID to look up"
                }
            },
            "required": ["client_identifier"]
        }
    ),
    FunctionDeclaration(
        name="calculate_renewal_priority",
        description="Calculate the priority score for a policy renewal based on premium at risk, time to expiry, and claims frequency.",
        parameters={
            "type": "object",
            "properties": {
                "policy_id": {
                    "type": "string",
                    "description": "The policy ID to calculate priority for"
                }
            },
            "required": ["policy_id"]
        }
    )
]


# System prompts for different use cases

BRIEF_SYSTEM_PROMPT = """You are an AI assistant for insurance brokers, specialized in generating comprehensive policy briefings.

Your task is to synthesize information from multiple sources (CRM, email, calendar, chat) into a structured brief.

CRITICAL RULES:
1. ONLY use information provided to you from the connected data sources.
2. NEVER invent or hallucinate facts. If information is not available, explicitly state "Information not available."
3. For EVERY fact you state, you MUST include a citation in the format [SOURCE:id] where id is the record ID from the source data.
4. Structure your response with clear sections: Policy Overview, Risk Analysis, Recent Communications, Suggested Next Actions.
5. Be concise but comprehensive.
6. When suggesting actions, base them on the actual data provided.

Citation format example: "The client's premium is $125,000 [SOURCE:policy-123]"
"""

CHAT_SYSTEM_PROMPT = """You are an AI assistant for insurance brokers with access to connected data systems (CRM, Outlook, Calendar, Teams).

CRITICAL RULES:
1. You can ONLY answer questions using data retrieved from the connected tools.
2. NEVER guess or make up information. If you cannot find the answer, say "I couldn't find that information in the connected systems."
3. For EVERY fact you state, include a citation in the format [SOURCE:id] referencing the source record.
4. If a question requires multiple pieces of information, use the appropriate tools to gather all needed data before answering.
5. Be helpful but accurate. Accuracy is more important than completeness.
6. If the user asks about something outside the scope of connected systems, politely explain what you can and cannot access.

You have access to these tools:
- get_policy_details: Look up policy information
- find_emails: Search emails
- find_meetings: Search calendar
- get_client_info: Look up client details
- calculate_renewal_priority: Calculate priority scores

Always use these tools to find information before responding.
"""
