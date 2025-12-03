"""
Brief Generation Module
Fetches multi-source data and synthesizes comprehensive policy briefs using Gemini LLM.
"""
import os
import json
import asyncio
from typing import Dict, Any, List, AsyncGenerator

from .connectors.microsoft_graph import MicrosoftGraphConnector
from .priority import deterministic_score
from .llm.gemini import get_gemini_client, GeminiConfig, BRIEF_SYSTEM_PROMPT
from .llm.provenance import build_provenance_map, inject_links, calculate_confidence_score
from .core.logging import get_logger

logger = get_logger(__name__)

# Flag to control LLM usage (can be disabled for testing)
USE_LLM = os.getenv("USE_LLM", "true").lower() == "true"


async def fetch_policy_data(policy_id: str) -> Dict[str, Any]:
    """Fetch policy data from CRM connector.
    # TODO: Replace with actual CRM connector call using OAuth tokens.
    """
    logger.debug(f"Fetching policy data for {policy_id}")
    await asyncio.sleep(0)
    policy = {
        "id": policy_id,
        "client_name": "ACME Corp",
        "policy_number": f"POL-{policy_id}",
        "premium_at_risk": 125000.0,
        "expiry_date": "2026-01-15",
        "days_to_expiry": 43,
        "claims_frequency": 1,
        "underwriter": "John Smith",
        "policy_type": "Commercial Property",
        "coverage_limit": 500000.0,
        "deductible": 5000.0,
        "link": f"https://crm.example.com/policy/{policy_id}"
    }
    logger.debug(f"Retrieved policy data for {policy_id}", extra={"client": policy["client_name"]})
    return policy


async def fetch_meetings_data(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Fetch calendar meetings from Calendar connector.
    # TODO: Replace with actual Calendar connector call.
    """
    logger.debug(f"Fetching meetings data", extra={"query": query, "limit": limit})
    await asyncio.sleep(0)
    meetings = [
        {
            "id": "mtg-1",
            "subject": "Renewal Discussion - ACME Corp",
            "timestamp": "2025-11-20T09:00:00Z",
            "attendees": ["broker@company.com", "client@acme.com"],
            "notes": "Discussed coverage options, client interested in increasing limits",
            "link": "https://calendar.example.com/event/mtg-1"
        },
        {
            "id": "mtg-2",
            "subject": "Quarterly Review - ACME",
            "timestamp": "2025-09-15T14:00:00Z",
            "attendees": ["broker@company.com", "cfo@acme.com"],
            "notes": "Reviewed claims history, no major concerns",
            "link": "https://calendar.example.com/event/mtg-2"
        }
    ][:limit]
    logger.debug(f"Retrieved {len(meetings)} meetings")
    return meetings


async def fetch_chats_data(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Fetch Teams chat mentions from Teams connector.
    # TODO: Replace with actual Teams connector call.
    """
    logger.debug(f"Fetching chats data", extra={"query": query, "limit": limit})
    await asyncio.sleep(0)
    chats = [
        {
            "id": "chat-1",
            "subject": "Quick question about ACME renewal",
            "timestamp": "2025-11-29T08:30:00Z",
            "from": "colleague@company.com",
            "snippet": "Hey, the ACME renewal is coming up - do we have the latest financials?",
            "link": "https://teams.microsoft.com/l/message/chat-1"
        }
    ][:limit]
    logger.debug(f"Retrieved {len(chats)} chats")
    return chats


async def generate_brief(policy_id: str, connectors_settings: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch multi-source data and synthesize a comprehensive brief using Gemini LLM.
    All data is ephemeral - fetched live and discarded after request.
    
    Args:
        policy_id: The policy identifier to generate brief for
        connectors_settings: Configuration for various connectors
    
    Returns:
        Dictionary containing policy data, sources, narrative, and provenance map
    """
    logger.info(f"Generating brief for policy", extra={"policy_id": policy_id})
    mg = MicrosoftGraphConnector(connectors_settings.get("microsoft", {}))

    # Parallel fetch from all sources
    logger.debug("Fetching data from multiple sources in parallel")
    policy, emails, meetings, chats = await asyncio.gather(
        fetch_policy_data(policy_id),
        mg.fetch_snippets(query=policy_id, limit=5),
        fetch_meetings_data(policy_id, limit=5),
        fetch_chats_data(policy_id, limit=5)
    )
    
    logger.debug(
        "Data fetched successfully",
        extra={
            "policy_id": policy_id,
            "email_count": len(emails),
            "meeting_count": len(meetings),
            "chat_count": len(chats),
        }
    )

    # Calculate deterministic score
    score, breakdown = deterministic_score(policy)
    logger.debug(f"Priority score calculated: {score:.2f}")

    # Build provenance map for citations
    sources = {
        "policy": policy,
        "emails": emails,
        "meetings": meetings,
        "chats": chats
    }
    provenance = build_provenance_map(sources)
    logger.debug(f"Provenance map built with {len(provenance)} entries")

    # Generate narrative using LLM or fallback
    if USE_LLM:
        logger.info("Generating brief narrative via Gemini LLM")
        try:
            narrative, raw_narrative = await generate_brief_via_gemini(
                policy, emails, meetings, chats, score, breakdown
            )
            logger.info("Brief narrative generated successfully via LLM")
        except Exception as e:
            logger.error(f"LLM generation failed, using fallback", extra={"error": str(e)})
            narrative, raw_narrative = generate_brief_fallback(
                policy, emails, meetings, chats, score, breakdown
            )
    else:
        logger.info("Generating brief narrative via fallback (LLM disabled)")
        narrative, raw_narrative = generate_brief_fallback(
            policy, emails, meetings, chats, score, breakdown
        )

    # Inject citation links
    narrative_with_links, citation_info = inject_links(raw_narrative, provenance)
    logger.debug(f"Injected {len(citation_info)} citations into narrative")

    # Calculate confidence
    confidence = calculate_confidence_score(
        function_results=[],  # No function calls in brief generation
        citations_resolved=sum(1 for c in citation_info if c["resolved"]),
        citations_total=len(citation_info)
    )
    
    logger.info(
        f"Brief generated successfully",
        extra={
            "policy_id": policy_id,
            "score": score,
            "confidence": confidence,
            "citation_count": len(citation_info),
        }
    )

    return {
        "policy": policy,
        "emails": emails,
        "meetings": meetings,
        "chats": chats,
        "deterministic_score": score,
        "score_breakdown": breakdown,
        "narrative": narrative,
        "narrative_with_links": narrative_with_links,
        "raw_narrative": raw_narrative,
        "provenance": provenance,
        "citations": citation_info,
        "confidence": confidence
    }


async def generate_brief_via_gemini(
    policy: Dict[str, Any],
    emails: List[Dict[str, Any]],
    meetings: List[Dict[str, Any]],
    chats: List[Dict[str, Any]],
    score: float,
    breakdown: Dict[str, float]
) -> tuple[Dict[str, Any], str]:
    """
    Generate a structured brief using Gemini LLM with citation injection.
    
    Returns:
        Tuple of (structured_narrative, raw_text_narrative)
    """
    client = get_gemini_client()
    
    # Build the data context for the LLM
    data_context = f"""
## Policy Data [SOURCE:{policy['id']}]
- Policy Number: {policy['policy_number']}
- Client: {policy['client_name']}
- Type: {policy.get('policy_type', 'N/A')}
- Premium at Risk: ${policy['premium_at_risk']:,.2f}
- Coverage Limit: ${policy.get('coverage_limit', 0):,.2f}
- Deductible: ${policy.get('deductible', 0):,.2f}
- Expiry Date: {policy['expiry_date']}
- Days to Expiry: {policy['days_to_expiry']}
- Claims Frequency: {policy['claims_frequency']}
- Underwriter: {policy.get('underwriter', 'N/A')}

## Priority Score
- Overall Score: {score:.2f} (0-1 scale, higher = more urgent)
- Premium Component: {breakdown['premium_component']:.3f}
- Time Urgency Component: {breakdown['time_component']:.3f}
- Claims Risk Component: {breakdown['claims_component']:.3f}

## Recent Emails ({len(emails)} found)
"""
    for email in emails:
        data_context += f"""
### Email [SOURCE:{email['id']}]
- Subject: {email['subject']}
- Date: {email['timestamp']}
- Snippet: {email.get('snippet', 'N/A')}
"""
    
    data_context += f"\n## Recent Meetings ({len(meetings)} found)\n"
    for meeting in meetings:
        data_context += f"""
### Meeting [SOURCE:{meeting['id']}]
- Subject: {meeting['subject']}
- Date: {meeting['timestamp']}
- Notes: {meeting.get('notes', 'N/A')}
"""
    
    data_context += f"\n## Teams Mentions ({len(chats)} found)\n"
    for chat in chats:
        data_context += f"""
### Chat [SOURCE:{chat['id']}]
- Subject: {chat['subject']}
- Date: {chat['timestamp']}
- From: {chat.get('from', 'N/A')}
- Snippet: {chat.get('snippet', 'N/A')}
"""

    user_prompt = f"""Based on the following data from connected systems, generate a comprehensive policy renewal brief.

{data_context}

Please structure your response with these sections:
1. **Policy Overview** - Key facts about the policy
2. **Risk Analysis** - Assessment of renewal risk and priority
3. **Recent Communications Summary** - What's been discussed recently
4. **Suggested Next Actions** - Specific actionable recommendations

Remember to include [SOURCE:id] citations for every fact you mention."""

    config = GeminiConfig(
        temperature=0.3,
        max_output_tokens=2048,
        system_instruction=BRIEF_SYSTEM_PROMPT
    )

    messages = [
        {
            "role": "user",
            "parts": [{"text": user_prompt}]
        }
    ]

    try:
        result = await client.generate(messages, config)
        
        # Extract text from response
        candidates = result.get("candidates", [])
        if candidates:
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            raw_text = "".join(p.get("text", "") for p in parts if "text" in p)
        else:
            raw_text = "Unable to generate brief - no response from LLM."
        
        # Parse into structured format (simple section extraction)
        narrative = parse_brief_sections(raw_text)
        
        return narrative, raw_text
        
    except Exception as e:
        # Fallback if LLM fails
        error_msg = f"LLM generation failed: {str(e)}"
        narrative, raw_text = generate_brief_fallback(
            policy, emails, meetings, chats, score, breakdown
        )
        narrative["error"] = error_msg
        return narrative, raw_text


def parse_brief_sections(raw_text: str) -> Dict[str, Any]:
    """Parse the raw LLM output into structured sections."""
    sections = {
        "policy_overview": "",
        "risk_analysis": "",
        "recent_communications": "",
        "suggested_actions": "",
        "full_text": raw_text
    }
    
    # Simple section extraction based on headers
    import re
    
    patterns = [
        (r'\*\*Policy Overview\*\*[:\s]*(.*?)(?=\*\*|$)', 'policy_overview'),
        (r'\*\*Risk Analysis\*\*[:\s]*(.*?)(?=\*\*|$)', 'risk_analysis'),
        (r'\*\*Recent Communications Summary\*\*[:\s]*(.*?)(?=\*\*|$)', 'recent_communications'),
        (r'\*\*Suggested Next Actions\*\*[:\s]*(.*?)(?=\*\*|$)', 'suggested_actions'),
    ]
    
    for pattern, key in patterns:
        match = re.search(pattern, raw_text, re.DOTALL | re.IGNORECASE)
        if match:
            sections[key] = match.group(1).strip()
    
    return sections


def generate_brief_fallback(
    policy: Dict[str, Any],
    emails: List[Dict[str, Any]],
    meetings: List[Dict[str, Any]],
    chats: List[Dict[str, Any]],
    score: float,
    breakdown: Dict[str, float]
) -> tuple[Dict[str, Any], str]:
    """
    Fallback brief generation when LLM is unavailable.
    Still includes citation markers for provenance tracking.
    """
    overview = f"Policy {policy['policy_number']} for {policy['client_name']} [SOURCE:{policy['id']}]. "
    overview += f"This is a {policy.get('policy_type', 'commercial')} policy with premium at risk of ${policy['premium_at_risk']:,.2f} [SOURCE:{policy['id']}]."
    
    risk = f"**Priority Score: {score:.2f}** [SOURCE:{policy['id']}]\n"
    risk += f"- Premium at risk: ${policy['premium_at_risk']:,.2f} contributes {breakdown['premium_component']:.1%} to priority\n"
    risk += f"- Time urgency ({policy['days_to_expiry']} days to expiry) contributes {breakdown['time_component']:.1%}\n"
    risk += f"- Claims frequency ({policy['claims_frequency']}) contributes {breakdown['claims_component']:.1%}"
    
    comms = f"Found {len(emails)} recent emails"
    if emails:
        comms += f", most recent: \"{emails[0]['subject']}\" ({emails[0]['timestamp']}) [SOURCE:{emails[0]['id']}]"
    comms += f"\nFound {len(meetings)} meetings"
    if meetings:
        comms += f", most recent: \"{meetings[0]['subject']}\" [SOURCE:{meetings[0]['id']}]"
    
    actions = [
        f"Review and contact client regarding renewal options [SOURCE:{policy['id']}]",
        "Prepare competitive quote comparison",
    ]
    if score > 0.7:
        actions.insert(0, "**URGENT**: High priority renewal requires immediate attention")
    
    actions_text = "\n".join(f"- {a}" for a in actions)
    
    raw_text = f"""**Policy Overview**
{overview}

**Risk Analysis**
{risk}

**Recent Communications Summary**
{comms}

**Suggested Next Actions**
{actions_text}
"""
    
    narrative = {
        "policy_overview": overview,
        "risk_analysis": risk,
        "recent_communications": comms,
        "suggested_actions": actions_text,
        "full_text": raw_text
    }
    
    return narrative, raw_text


async def stream_brief(policy_id: str, connectors_settings: Dict[str, Any]) -> AsyncGenerator[str, None]:
    """
    Stream the brief generation for reduced perceived latency.
    Yields chunks of the brief as they become available.
    """
    mg = MicrosoftGraphConnector(connectors_settings.get("microsoft", {}))

    # First, stream the data gathering status
    yield "📊 Gathering data from connected sources...\n\n"
    
    # Parallel fetch
    policy, emails, meetings, chats = await asyncio.gather(
        fetch_policy_data(policy_id),
        mg.fetch_snippets(query=policy_id, limit=5),
        fetch_meetings_data(policy_id, limit=5),
        fetch_chats_data(policy_id, limit=5)
    )
    
    yield f"✅ Policy data loaded: {policy['policy_number']}\n"
    yield f"✅ Found {len(emails)} emails, {len(meetings)} meetings, {len(chats)} chat mentions\n\n"
    
    # Calculate score
    score, breakdown = deterministic_score(policy)
    yield f"📈 Priority Score: **{score:.2f}**\n\n"
    
    # Build provenance
    sources = {"policy": policy, "emails": emails, "meetings": meetings, "chats": chats}
    provenance = build_provenance_map(sources)
    
    yield "🤖 Generating AI analysis...\n\n---\n\n"
    
    if USE_LLM:
        # Stream from Gemini
        client = get_gemini_client()
        
        data_context = _build_data_context(policy, emails, meetings, chats, score, breakdown)
        user_prompt = f"""Based on the following data, generate a policy renewal brief with sections: Policy Overview, Risk Analysis, Recent Communications Summary, Suggested Next Actions.

{data_context}

Include [SOURCE:id] citations for facts."""

        config = GeminiConfig(
            temperature=0.3,
            max_output_tokens=2048,
            system_instruction=BRIEF_SYSTEM_PROMPT
        )

        messages = [{"role": "user", "parts": [{"text": user_prompt}]}]
        
        try:
            buffer = ""
            async for chunk in client.generate_stream(messages, config):
                buffer += chunk
                # Inject links in real-time (simplified - full injection at end)
                yield chunk
            
            # Final provenance section
            yield "\n\n---\n📎 **Data Provenance:**\n"
            for source_id, link in provenance.items():
                yield f"- [{source_id}]({link})\n"
                
        except Exception as e:
            yield f"\n⚠️ LLM streaming failed: {str(e)}\n"
            yield "Falling back to template-based brief...\n\n"
            narrative, raw_text = generate_brief_fallback(
                policy, emails, meetings, chats, score, breakdown
            )
            text_with_links, _ = inject_links(raw_text, provenance)
            yield text_with_links
    else:
        # Fallback streaming
        narrative, raw_text = generate_brief_fallback(
            policy, emails, meetings, chats, score, breakdown
        )
        text_with_links, _ = inject_links(raw_text, provenance)
        
        # Stream in chunks for effect
        words = text_with_links.split()
        chunk_size = 10
        for i in range(0, len(words), chunk_size):
            yield " ".join(words[i:i+chunk_size]) + " "
            await asyncio.sleep(0.05)


def _build_data_context(policy, emails, meetings, chats, score, breakdown) -> str:
    """Build the data context string for LLM prompts."""
    ctx = f"""## Policy [SOURCE:{policy['id']}]
- Number: {policy['policy_number']}
- Client: {policy['client_name']}
- Premium: ${policy['premium_at_risk']:,.2f}
- Expiry: {policy['expiry_date']} ({policy['days_to_expiry']} days)
- Claims: {policy['claims_frequency']}
- Score: {score:.2f}

## Emails
"""
    for e in emails:
        ctx += f"- [{e['id']}] {e['subject']} ({e['timestamp']})\n"
    
    ctx += "\n## Meetings\n"
    for m in meetings:
        ctx += f"- [{m['id']}] {m['subject']} ({m['timestamp']})\n"
    
    ctx += "\n## Chats\n"
    for c in chats:
        ctx += f"- [{c['id']}] {c['subject']} ({c['timestamp']})\n"
    
    return ctx
