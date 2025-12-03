"""
Chat Agent Module
Implements connector-backed Q&A with Gemini function-calling for multi-hop reasoning.
"""
import os
import re
import asyncio
from typing import Dict, Any, List, Optional

from .connectors.microsoft_graph import MicrosoftGraphConnector
from .priority import deterministic_score
from .llm.gemini import (
    get_gemini_client, 
    GeminiConfig, 
    BROKER_FUNCTIONS, 
    CHAT_SYSTEM_PROMPT
)
from .llm.provenance import (
    build_provenance_map, 
    inject_links, 
    calculate_confidence_score
)
from .core.logging import get_logger

logger = get_logger(__name__)

# Flag to control LLM usage
USE_LLM = os.getenv("USE_LLM", "true").lower() == "true"


class ToolFunctions:
    """
    Function handlers for Gemini function-calling.
    Each method corresponds to a declared function in BROKER_FUNCTIONS.
    """
    
    def __init__(self, connectors_settings: Dict[str, Any]):
        self.mg = MicrosoftGraphConnector(connectors_settings.get("microsoft", {}))
        self.provenance: Dict[str, str] = {}
        logger.debug("ToolFunctions initialized")
    
    async def get_policy_details(self, policy_id: str) -> Dict[str, Any]:
        """Retrieve policy details from CRM."""
        logger.debug(f"Fetching policy details", extra={"policy_id": policy_id})
        # TODO: Replace with actual CRM connector call
        await asyncio.sleep(0)
        policy = {
            "id": policy_id,
            "policy_number": f"POL-{policy_id}" if not policy_id.startswith("POL-") else policy_id,
            "client_name": "ACME Corporation",
            "premium_at_risk": 125000.0,
            "expiry_date": "2026-01-15",
            "days_to_expiry": 43,
            "claims_frequency": 1,
            "underwriter": "John Smith",
            "policy_type": "Commercial Property",
            "coverage_limit": 500000.0,
            "link": f"https://crm.example.com/policy/{policy_id}"
        }
        self.provenance[policy_id] = policy["link"]
        logger.debug(f"Retrieved policy details", extra={"policy_id": policy_id, "client": policy["client_name"]})
        return policy
    
    async def find_emails(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search for emails matching the query."""
        logger.debug(f"Searching for emails", extra={"query": query, "limit": limit})
        emails = await self.mg.fetch_snippets(query=query, limit=limit)
        for email in emails:
            self.provenance[email["id"]] = email.get("link", "")
        logger.debug(f"Found {len(emails)} emails")
        return emails
    
    async def find_meetings(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search for calendar meetings."""
        logger.debug(f"Searching for meetings", extra={"query": query, "limit": limit})
        # TODO: Replace with actual Calendar connector call
        await asyncio.sleep(0)
        meetings = [
            {
                "id": "mtg-1",
                "subject": f"Meeting about {query}",
                "timestamp": "2025-11-20T09:00:00Z",
                "attendees": ["broker@company.com", "client@acme.com"],
                "notes": "Discussed renewal options",
                "link": "https://calendar.example.com/event/mtg-1"
            },
            {
                "id": "mtg-2",
                "subject": "Quarterly Review",
                "timestamp": "2025-09-15T14:00:00Z",
                "attendees": ["broker@company.com"],
                "link": "https://calendar.example.com/event/mtg-2"
            }
        ][:limit]
        for meeting in meetings:
            self.provenance[meeting["id"]] = meeting.get("link", "")
        return meetings
    
    async def get_client_info(self, client_identifier: str) -> Dict[str, Any]:
        """Look up client information."""
        logger.debug(f"Looking up client info", extra={"client_identifier": client_identifier})
        # TODO: Replace with actual CRM connector call
        await asyncio.sleep(0)
        client = {
            "id": f"client-{client_identifier.lower().replace(' ', '-')}",
            "name": client_identifier if not client_identifier.startswith("client-") else "ACME Corporation",
            "contact_email": "contact@acme.com",
            "contact_phone": "+1-555-0123",
            "industry": "Manufacturing",
            "policies": ["POL-123", "POL-456"],
            "link": f"https://crm.example.com/client/{client_identifier}"
        }
        self.provenance[client["id"]] = client["link"]
        logger.debug(f"Retrieved client info", extra={"client_id": client["id"], "name": client["name"]})
        return client
    
    async def calculate_renewal_priority(self, policy_id: str) -> Dict[str, Any]:
        """Calculate priority score for a policy renewal."""
        logger.debug(f"Calculating renewal priority", extra={"policy_id": policy_id})
        policy = await self.get_policy_details(policy_id)
        score, breakdown = deterministic_score(policy)
        logger.debug(f"Calculated priority score: {score:.2f}", extra={"policy_id": policy_id})
        return {
            "policy_id": policy_id,
            "score": score,
            "breakdown": breakdown,
            "interpretation": _interpret_score(score),
            "link": policy.get("link", "")
        }


def _interpret_score(score: float) -> str:
    """Generate human-readable interpretation of priority score."""
    if score >= 0.8:
        return "CRITICAL - Immediate action required"
    elif score >= 0.6:
        return "HIGH - Prioritize this week"
    elif score >= 0.4:
        return "MEDIUM - Schedule follow-up"
    else:
        return "LOW - Monitor and plan"


async def handle_chat_message(
    payload: Dict[str, Any], 
    connectors_settings: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Handle a chat message with function-calling support for multi-hop reasoning.
    
    Args:
        payload: Dict with 'user_id' and 'message' keys
        connectors_settings: Configuration for data connectors
    
    Returns:
        Dict with 'answer', 'confidence', 'provenance', and optionally 'function_calls'
    """
    message = payload.get("message", "").strip()
    user_id = payload.get("user_id", "unknown")
    
    logger.info(f"Processing chat message", extra={"user_id": user_id, "message_length": len(message)})
    
    if not message:
        logger.warning("Empty chat message received")
        return {
            "answer": "Please provide a question or request.",
            "confidence": 0.0,
            "provenance": {}
        }
    
    tools = ToolFunctions(connectors_settings)
    
    if USE_LLM:
        logger.debug("Processing with Gemini LLM")
        return await _handle_with_gemini(message, tools)
    else:
        logger.debug("Processing with fallback handler (LLM disabled)")
        return await _handle_with_fallback(message, tools)


async def _handle_with_gemini(message: str, tools: ToolFunctions) -> Dict[str, Any]:
    """Handle chat using Gemini with function-calling."""
    logger.info("Starting Gemini chat processing")
    client = get_gemini_client()
    
    # Build function handlers map
    function_handlers = {
        "get_policy_details": tools.get_policy_details,
        "find_emails": tools.find_emails,
        "find_meetings": tools.find_meetings,
        "get_client_info": tools.get_client_info,
        "calculate_renewal_priority": tools.calculate_renewal_priority,
    }
    
    config = GeminiConfig(
        temperature=0.2,  # Lower for more factual responses
        max_output_tokens=1024,
        system_instruction=CHAT_SYSTEM_PROMPT,
        functions=BROKER_FUNCTIONS
    )
    
    messages = [
        {
            "role": "user",
            "parts": [{"text": message}]
        }
    ]
    
    try:
        logger.debug("Calling Gemini with function-calling enabled")
        result = await client.generate_with_functions(
            messages=messages,
            config=config,
            function_handlers=function_handlers
        )
        
        raw_answer = result.get("text", "")
        function_results = result.get("function_results", [])
        
        logger.debug(
            "Gemini response received",
            extra={
                "function_calls": len(function_results),
                "answer_length": len(raw_answer),
            }
        )
        
        # Inject citation links
        answer_with_links, citation_info = inject_links(raw_answer, tools.provenance)
        
        # Calculate confidence based on function call success and citations
        confidence = calculate_confidence_score(
            function_results=function_results,
            citations_resolved=sum(1 for c in citation_info if c["resolved"]),
            citations_total=len(citation_info)
        )
        
        # Apply hallucination guardrail - if no data was retrieved, lower confidence
        if not function_results and not tools.provenance:
            logger.warning("No function calls or provenance data - applying hallucination guardrail")
            confidence = min(confidence, 0.3)
            if "I couldn't find" not in raw_answer and "not available" not in raw_answer.lower():
                answer_with_links = (
                    "⚠️ I wasn't able to retrieve data from connected systems to answer this question. "
                    "Please try rephrasing or asking about a specific policy, client, or email."
                )
                confidence = 0.1
        
        logger.info(
            "Chat response generated",
            extra={
                "confidence": confidence,
                "citations": len(citation_info),
                "function_calls": len(function_results),
            }
        )
        
        return {
            "answer": answer_with_links,
            "raw_answer": raw_answer,
            "confidence": confidence,
            "provenance": tools.provenance,
            "citations": citation_info,
            "function_calls": [
                {"function": fc["function"], "args": fc["args"]}
                for fc in function_results
            ]
        }
        
    except Exception as e:
        logger.error(f"Gemini chat processing failed, using fallback", extra={"error": str(e)})
        # Fallback on error
        fallback_result = await _handle_with_fallback(message, tools)
        fallback_result["error"] = str(e)
        return fallback_result


async def _handle_with_fallback(message: str, tools: ToolFunctions) -> Dict[str, Any]:
    """
    Fallback handler using pattern matching when LLM is unavailable.
    Demonstrates the function-calling concept without actual LLM.
    """
    logger.debug("Processing message with fallback pattern matching")
    message_lower = message.lower()
    function_calls = []
    
    # Pattern matching for common queries
    
    # Policy lookup
    policy_match = re.search(r'POL[-_ ]?(\w+)', message, re.IGNORECASE)
    policy_id = None
    if policy_match:
        policy_id = policy_match.group(0)
    
    # Underwriter query
    if "underwriter" in message_lower:
        if policy_id:
            policy = await tools.get_policy_details(policy_id)
            function_calls.append({"function": "get_policy_details", "args": {"policy_id": policy_id}})
            
            # Check for email follow-up
            if "email" in message_lower or "last" in message_lower:
                underwriter = policy.get("underwriter", "Unknown")
                emails = await tools.find_emails(query=underwriter, limit=3)
                function_calls.append({"function": "find_emails", "args": {"query": underwriter}})
                
                if emails:
                    answer = (
                        f"The underwriter for {policy['policy_number']} is **{underwriter}** [SOURCE:{policy_id}]. "
                        f"Your last email mentioning them was \"{emails[0]['subject']}\" on {emails[0]['timestamp']} [SOURCE:{emails[0]['id']}]."
                    )
                else:
                    answer = (
                        f"The underwriter for {policy['policy_number']} is **{underwriter}** [SOURCE:{policy_id}]. "
                        f"I couldn't find recent emails mentioning them."
                    )
            else:
                answer = f"The underwriter for {policy['policy_number']} is **{policy.get('underwriter', 'Unknown')}** [SOURCE:{policy_id}]."
            
            answer_with_links, citation_info = inject_links(answer, tools.provenance)
            confidence = 0.8
        else:
            answer_with_links = "Please specify a policy ID (e.g., POL-123) to look up the underwriter."
            citation_info = []
            confidence = 0.3
    
    # Priority/score query
    elif "priority" in message_lower or "score" in message_lower or "urgent" in message_lower:
        if policy_id:
            result = await tools.calculate_renewal_priority(policy_id)
            function_calls.append({"function": "calculate_renewal_priority", "args": {"policy_id": policy_id}})
            
            answer = (
                f"The renewal priority for {policy_id} is **{result['score']:.2f}** ({result['interpretation']}) [SOURCE:{policy_id}]. "
                f"Breakdown: Premium risk {result['breakdown']['premium_component']:.1%}, "
                f"Time urgency {result['breakdown']['time_component']:.1%}, "
                f"Claims factor {result['breakdown']['claims_component']:.1%}."
            )
            answer_with_links, citation_info = inject_links(answer, tools.provenance)
            confidence = 0.85
        else:
            answer_with_links = "Please specify a policy ID to calculate renewal priority."
            citation_info = []
            confidence = 0.3
    
    # Email search
    elif "email" in message_lower:
        # Extract search terms
        search_terms = message.replace("email", "").replace("emails", "").strip()
        if not search_terms and policy_id:
            search_terms = policy_id
        
        if search_terms:
            emails = await tools.find_emails(query=search_terms, limit=5)
            function_calls.append({"function": "find_emails", "args": {"query": search_terms}})
            
            if emails:
                answer = f"Found {len(emails)} emails matching \"{search_terms}\":\n"
                for i, email in enumerate(emails[:3], 1):
                    answer += f"\n{i}. **{email['subject']}** ({email['timestamp']}) [SOURCE:{email['id']}]"
            else:
                answer = f"I couldn't find emails matching \"{search_terms}\"."
            
            answer_with_links, citation_info = inject_links(answer, tools.provenance)
            confidence = 0.7 if emails else 0.4
        else:
            answer_with_links = "What would you like me to search for in your emails?"
            citation_info = []
            confidence = 0.2
    
    # Meeting search
    elif "meeting" in message_lower or "calendar" in message_lower:
        search_terms = policy_id or "renewal"
        meetings = await tools.find_meetings(query=search_terms, limit=5)
        function_calls.append({"function": "find_meetings", "args": {"query": search_terms}})
        
        if meetings:
            answer = f"Found {len(meetings)} meetings:\n"
            for i, meeting in enumerate(meetings[:3], 1):
                answer += f"\n{i}. **{meeting['subject']}** ({meeting['timestamp']}) [SOURCE:{meeting['id']}]"
        else:
            answer = "I couldn't find relevant meetings."
        
        answer_with_links, citation_info = inject_links(answer, tools.provenance)
        confidence = 0.7 if meetings else 0.4
    
    # Client lookup
    elif "client" in message_lower or "who is" in message_lower:
        # Try to extract client name
        client_name = None
        if policy_id:
            policy = await tools.get_policy_details(policy_id)
            client_name = policy.get("client_name")
            function_calls.append({"function": "get_policy_details", "args": {"policy_id": policy_id}})
        
        if client_name:
            client = await tools.get_client_info(client_name)
            function_calls.append({"function": "get_client_info", "args": {"client_identifier": client_name}})
            
            answer = (
                f"**{client['name']}** [SOURCE:{client['id']}]\n"
                f"- Email: {client['contact_email']}\n"
                f"- Phone: {client['contact_phone']}\n"
                f"- Industry: {client['industry']}\n"
                f"- Policies: {', '.join(client['policies'])}"
            )
            answer_with_links, citation_info = inject_links(answer, tools.provenance)
            confidence = 0.8
        else:
            answer_with_links = "Please specify a policy ID or client name to look up."
            citation_info = []
            confidence = 0.3
    
    # Default - can't understand
    else:
        answer_with_links = (
            "I can help you with:\n"
            "- Looking up policy details (e.g., \"What's the status of POL-123?\")\n"
            "- Finding the underwriter for a policy\n"
            "- Searching emails and meetings\n"
            "- Calculating renewal priority scores\n"
            "- Looking up client information\n\n"
            "Please ask a specific question about a policy or client."
        )
        citation_info = []
        confidence = 0.5
    
    return {
        "answer": answer_with_links,
        "confidence": confidence,
        "provenance": tools.provenance,
        "citations": citation_info,
        "function_calls": function_calls
    }


async def stream_chat_response(
    payload: Dict[str, Any],
    connectors_settings: Dict[str, Any]
):
    """
    Stream chat response for reduced perceived latency.
    Yields chunks as they become available.
    """
    message = payload.get("message", "").strip()
    tools = ToolFunctions(connectors_settings)
    
    if not USE_LLM:
        # For fallback, just get the full response and yield it
        result = await _handle_with_fallback(message, tools)
        yield result["answer"]
        return
    
    client = get_gemini_client()
    
    function_handlers = {
        "get_policy_details": tools.get_policy_details,
        "find_emails": tools.find_emails,
        "find_meetings": tools.find_meetings,
        "get_client_info": tools.get_client_info,
        "calculate_renewal_priority": tools.calculate_renewal_priority,
    }
    
    config = GeminiConfig(
        temperature=0.2,
        max_output_tokens=1024,
        system_instruction=CHAT_SYSTEM_PROMPT,
        functions=BROKER_FUNCTIONS
    )
    
    messages = [{"role": "user", "parts": [{"text": message}]}]
    
    # First, we need to handle function calls (non-streaming)
    # Then stream the final response
    try:
        # Initial generation to check for function calls
        result = await client.generate(messages, config)
        
        candidates = result.get("candidates", [])
        if not candidates:
            yield "I'm unable to process that request."
            return
        
        content = candidates[0].get("content", {})
        parts = content.get("parts", [])
        
        # Check for function calls
        function_calls = [p for p in parts if "functionCall" in p]
        
        if function_calls:
            yield "🔍 Looking up information...\n\n"
            
            # Execute function calls
            conversation = list(messages)
            for fc_part in function_calls:
                fc = fc_part["functionCall"]
                func_name = fc["name"]
                func_args = fc.get("args", {})
                
                if func_name in function_handlers:
                    handler = function_handlers[func_name]
                    func_result = await handler(**func_args)
                    
                    conversation.append({"role": "model", "parts": [fc_part]})
                    conversation.append({
                        "role": "function",
                        "parts": [{
                            "functionResponse": {
                                "name": func_name,
                                "response": {"result": func_result}
                            }
                        }]
                    })
            
            # Now stream the final response
            config_no_functions = GeminiConfig(
                temperature=0.2,
                max_output_tokens=1024,
                system_instruction=CHAT_SYSTEM_PROMPT
            )
            
            async for chunk in client.generate_stream(conversation, config_no_functions):
                yield chunk
        else:
            # No function calls, stream directly
            text_parts = [p.get("text", "") for p in parts if "text" in p]
            for text in text_parts:
                yield text
                
    except Exception as e:
        yield f"\n⚠️ Error: {str(e)}\n"
        # Fall back to non-LLM response
        result = await _handle_with_fallback(message, tools)
        yield "\n" + result["answer"]
