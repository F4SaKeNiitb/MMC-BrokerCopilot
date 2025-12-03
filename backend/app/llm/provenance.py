"""
Provenance Injection Module
Handles citation parsing and deep-link injection for LLM outputs.
"""
import re
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass

from ..core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Citation:
    """Represents a citation in the LLM output."""
    source_id: str
    start_pos: int
    end_pos: int
    link: str = ""


def build_provenance_map(sources: Dict[str, List[Dict[str, Any]]]) -> Dict[str, str]:
    """
    Build a mapping from source IDs to their deep links.
    
    Args:
        sources: Dictionary with source type keys (emails, meetings, etc.)
                 and lists of records with 'id' and 'link' fields.
    
    Returns:
        Dictionary mapping record IDs to their deep links.
    """
    logger.debug("Building provenance map from sources")
    provenance = {}
    for source_type, records in sources.items():
        if isinstance(records, list):
            for record in records:
                if isinstance(record, dict):
                    record_id = record.get("id")
                    link = record.get("link")
                    if record_id and link:
                        provenance[record_id] = link
        elif isinstance(records, dict):
            # Single record
            record_id = records.get("id")
            link = records.get("link")
            if record_id and link:
                provenance[record_id] = link
    
    logger.debug(f"Built provenance map with {len(provenance)} entries")
    return provenance


def extract_citations(text: str) -> List[Citation]:
    """
    Extract citation markers from text.
    Looks for patterns like [SOURCE:id] or [SOURCE:policy-123]
    
    Args:
        text: The LLM-generated text containing citation markers.
    
    Returns:
        List of Citation objects with positions.
    """
    pattern = r'\[SOURCE:([^\]]+)\]'
    citations = []
    
    for match in re.finditer(pattern, text):
        citations.append(Citation(
            source_id=match.group(1),
            start_pos=match.start(),
            end_pos=match.end()
        ))
    
    logger.debug(f"Extracted {len(citations)} citations from text")
    return citations


def inject_links(text: str, provenance: Dict[str, str]) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Replace citation markers with clickable links (Markdown format).
    
    Args:
        text: The LLM-generated text with citation markers.
        provenance: Mapping from source IDs to deep links.
    
    Returns:
        Tuple of (text_with_links, list_of_citation_info)
    """
    citations = extract_citations(text)
    citation_info = []
    
    # Process in reverse order to maintain positions
    result = text
    resolved_count = 0
    unresolved_count = 0
    
    for citation in reversed(citations):
        link = provenance.get(citation.source_id, "")
        if link:
            # Replace [SOURCE:id] with [📎](link)
            replacement = f"[📎]({link})"
            result = result[:citation.start_pos] + replacement + result[citation.end_pos:]
            citation_info.insert(0, {
                "source_id": citation.source_id,
                "link": link,
                "resolved": True
            })
            resolved_count += 1
        else:
            # Keep the marker but note it's unresolved
            unresolved_count += 1
            citation_info.insert(0, {
                "source_id": citation.source_id,
                "link": None,
                "resolved": False
            })
    
    if citations:
        logger.debug(
            f"Injected links into text",
            extra={
                "total_citations": len(citations),
                "resolved": resolved_count,
                "unresolved": unresolved_count,
            }
        )
    
    return result, citation_info


def inject_links_html(text: str, provenance: Dict[str, str]) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Replace citation markers with clickable HTML links.
    
    Args:
        text: The LLM-generated text with citation markers.
        provenance: Mapping from source IDs to deep links.
    
    Returns:
        Tuple of (html_with_links, list_of_citation_info)
    """
    logger.debug("Injecting HTML links into citations")
    citations = extract_citations(text)
    citation_info = []
    
    # Process in reverse order to maintain positions
    result = text
    for citation in reversed(citations):
        link = provenance.get(citation.source_id, "")
        if link:
            # Replace [SOURCE:id] with clickable icon
            replacement = f'<a href="{link}" target="_blank" class="citation-link" title="View source: {citation.source_id}">📎</a>'
            result = result[:citation.start_pos] + replacement + result[citation.end_pos:]
            citation_info.insert(0, {
                "source_id": citation.source_id,
                "link": link,
                "resolved": True
            })
        else:
            # Replace with unresolved marker
            replacement = f'<span class="citation-unresolved" title="Source not found: {citation.source_id}">❓</span>'
            result = result[:citation.start_pos] + replacement + result[citation.end_pos:]
            citation_info.insert(0, {
                "source_id": citation.source_id,
                "link": None,
                "resolved": False
            })
    
    logger.debug(f"Injected HTML links for {len(citations)} citations")
    return result, citation_info


def create_citation_footnotes(text: str, provenance: Dict[str, str]) -> Tuple[str, str]:
    """
    Convert inline citations to numbered footnotes.
    
    Args:
        text: The LLM-generated text with citation markers.
        provenance: Mapping from source IDs to deep links.
    
    Returns:
        Tuple of (text_with_footnote_numbers, footnotes_section)
    """
    citations = extract_citations(text)
    footnote_map = {}
    footnote_num = 1
    
    # First pass: assign footnote numbers
    for citation in citations:
        if citation.source_id not in footnote_map:
            footnote_map[citation.source_id] = footnote_num
            footnote_num += 1
    
    # Second pass: replace citations with footnote numbers
    result = text
    for citation in reversed(citations):
        num = footnote_map[citation.source_id]
        replacement = f"[{num}]"
        result = result[:citation.start_pos] + replacement + result[citation.end_pos:]
    
    # Build footnotes section
    footnotes_lines = ["\n---\n**Sources:**\n"]
    for source_id, num in sorted(footnote_map.items(), key=lambda x: x[1]):
        link = provenance.get(source_id, "")
        if link:
            footnotes_lines.append(f"[{num}] [{source_id}]({link})")
        else:
            footnotes_lines.append(f"[{num}] {source_id} (link unavailable)")
    
    footnotes = "\n".join(footnotes_lines)
    
    return result, footnotes


def calculate_confidence_score(
    function_results: List[Dict[str, Any]],
    citations_resolved: int,
    citations_total: int
) -> float:
    """
    Calculate a confidence score based on data retrieval success.
    
    Args:
        function_results: List of function call results
        citations_resolved: Number of citations that could be linked
        citations_total: Total number of citations in response
    
    Returns:
        Confidence score between 0.0 and 1.0
    """
    if not function_results and citations_total == 0:
        return 0.0
    
    # Factor 1: Function call success rate
    successful_calls = sum(1 for r in function_results if "error" not in r)
    total_calls = len(function_results) if function_results else 1
    call_success_rate = successful_calls / total_calls
    
    # Factor 2: Citation resolution rate
    citation_rate = citations_resolved / citations_total if citations_total > 0 else 1.0
    
    # Factor 3: Data richness (more function calls with results = more confidence)
    richness_bonus = min(0.1 * len([r for r in function_results if r.get("result")]), 0.2)
    
    # Weighted combination
    confidence = (0.5 * call_success_rate) + (0.4 * citation_rate) + richness_bonus
    
    return min(1.0, max(0.0, confidence))
