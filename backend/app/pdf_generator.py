"""
PDF Generation Module for Broker Copilot

Generates professional PDF documents from briefs using WeasyPrint.
Supports streaming brief content and markdown conversion.
"""
import io
import re
from datetime import datetime
from typing import Optional, Dict, Any
import markdown
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration

from .core.logging import get_logger

logger = get_logger(__name__)


# Professional PDF styles
PDF_STYLES = """
@page {
    size: A4;
    margin: 2cm 2.5cm;
    @top-right {
        content: "Broker Copilot Brief";
        font-size: 9pt;
        color: #666;
    }
    @bottom-center {
        content: "Page " counter(page) " of " counter(pages);
        font-size: 9pt;
        color: #666;
    }
    @bottom-right {
        content: "Generated: """ + datetime.now().strftime("%Y-%m-%d %H:%M") + """";
        font-size: 8pt;
        color: #999;
    }
}

* {
    box-sizing: border-box;
}

body {
    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    font-size: 11pt;
    line-height: 1.6;
    color: #333;
    max-width: 100%;
}

/* Header styles */
.header {
    border-bottom: 3px solid #2563eb;
    padding-bottom: 15px;
    margin-bottom: 25px;
}

.header h1 {
    color: #1e40af;
    font-size: 24pt;
    margin: 0 0 5px 0;
    font-weight: 700;
}

.header .subtitle {
    color: #666;
    font-size: 12pt;
    margin: 0;
}

.header .meta {
    margin-top: 10px;
    font-size: 10pt;
    color: #888;
}

/* Content styles */
h1 {
    color: #1e40af;
    font-size: 18pt;
    margin-top: 25px;
    margin-bottom: 12px;
    padding-bottom: 5px;
    border-bottom: 1px solid #e5e7eb;
}

h2 {
    color: #1e3a8a;
    font-size: 14pt;
    margin-top: 20px;
    margin-bottom: 10px;
}

h3 {
    color: #374151;
    font-size: 12pt;
    margin-top: 15px;
    margin-bottom: 8px;
}

p {
    margin: 8px 0;
    text-align: justify;
}

ul, ol {
    margin: 10px 0;
    padding-left: 25px;
}

li {
    margin: 5px 0;
}

/* Info boxes */
.info-box {
    background: #eff6ff;
    border-left: 4px solid #2563eb;
    padding: 12px 15px;
    margin: 15px 0;
    border-radius: 0 4px 4px 0;
}

.warning-box {
    background: #fef3c7;
    border-left: 4px solid #f59e0b;
    padding: 12px 15px;
    margin: 15px 0;
    border-radius: 0 4px 4px 0;
}

.critical-box {
    background: #fef2f2;
    border-left: 4px solid #ef4444;
    padding: 12px 15px;
    margin: 15px 0;
    border-radius: 0 4px 4px 0;
}

/* Tables */
table {
    width: 100%;
    border-collapse: collapse;
    margin: 15px 0;
    font-size: 10pt;
}

th {
    background: #f3f4f6;
    border: 1px solid #d1d5db;
    padding: 10px 12px;
    text-align: left;
    font-weight: 600;
}

td {
    border: 1px solid #d1d5db;
    padding: 8px 12px;
}

tr:nth-child(even) {
    background: #f9fafb;
}

/* Citations/Sources */
.citation {
    background: #dbeafe;
    color: #1e40af;
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 9pt;
    white-space: nowrap;
}

.sources {
    margin-top: 30px;
    padding-top: 15px;
    border-top: 1px solid #e5e7eb;
}

.sources h2 {
    font-size: 12pt;
    color: #6b7280;
}

.sources ul {
    font-size: 9pt;
    color: #6b7280;
}

/* Score badge */
.score-badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 20px;
    font-weight: 600;
    font-size: 10pt;
}

.score-critical {
    background: #fef2f2;
    color: #dc2626;
}

.score-high {
    background: #fff7ed;
    color: #ea580c;
}

.score-medium {
    background: #fefce8;
    color: #ca8a04;
}

.score-low {
    background: #f0fdf4;
    color: #16a34a;
}

/* Summary box */
.summary-box {
    background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
    border: 1px solid #bfdbfe;
    border-radius: 8px;
    padding: 20px;
    margin: 20px 0;
}

.summary-box h3 {
    margin-top: 0;
    color: #1e40af;
}

/* Footer */
.footer {
    margin-top: 40px;
    padding-top: 15px;
    border-top: 1px solid #e5e7eb;
    font-size: 9pt;
    color: #9ca3af;
}

.footer p {
    margin: 3px 0;
}

/* Print-specific */
@media print {
    body {
        font-size: 10pt;
    }
    
    .no-print {
        display: none;
    }
}
"""


def get_dynamic_styles() -> str:
    """Get CSS with current timestamp."""
    return PDF_STYLES.replace(
        datetime.now().strftime("%Y-%m-%d %H:%M"),
        datetime.now().strftime("%Y-%m-%d %H:%M")
    )


def markdown_to_html(md_content: str) -> str:
    """Convert markdown content to HTML with extensions."""
    extensions = [
        'tables',
        'fenced_code',
        'nl2br',
        'sane_lists',
    ]
    return markdown.markdown(md_content, extensions=extensions)


def format_citations(html_content: str) -> str:
    """Format citation markers in HTML."""
    # Convert [Source: X] patterns to styled citations
    citation_pattern = r'\[Source:\s*([^\]]+)\]'
    html_content = re.sub(
        citation_pattern,
        r'<span class="citation">📎 \1</span>',
        html_content
    )
    
    # Convert [Citation: X] patterns
    citation_pattern2 = r'\[Citation:\s*([^\]]+)\]'
    html_content = re.sub(
        citation_pattern2,
        r'<span class="citation">📎 \1</span>',
        html_content
    )
    
    return html_content


def get_score_class(score: float) -> str:
    """Get CSS class for score badge."""
    if score >= 0.7:
        return "score-critical"
    elif score >= 0.5:
        return "score-high"
    elif score >= 0.3:
        return "score-medium"
    return "score-low"


def get_score_label(score: float) -> str:
    """Get label for score."""
    if score >= 0.7:
        return "Critical Priority"
    elif score >= 0.5:
        return "High Priority"
    elif score >= 0.3:
        return "Medium Priority"
    return "Low Priority"


def create_brief_html(
    policy_id: str,
    content: str,
    policy_data: Optional[Dict[str, Any]] = None,
    score: Optional[float] = None
) -> str:
    """
    Create full HTML document for brief PDF.
    
    Args:
        policy_id: Policy identifier
        content: Markdown content of the brief
        policy_data: Optional policy metadata
        score: Optional priority score
    
    Returns:
        Complete HTML document string
    """
    # Convert markdown to HTML
    html_content = markdown_to_html(content)
    
    # Format citations
    html_content = format_citations(html_content)
    
    # Build metadata section
    meta_parts = [f"Policy ID: {policy_id}"]
    if policy_data:
        if policy_data.get("client_name"):
            meta_parts.append(f"Client: {policy_data['client_name']}")
        if policy_data.get("expiry_date"):
            meta_parts.append(f"Expiry: {policy_data['expiry_date']}")
    
    meta_html = " | ".join(meta_parts)
    
    # Score badge
    score_html = ""
    if score is not None:
        score_class = get_score_class(score)
        score_label = get_score_label(score)
        score_html = f'<span class="score-badge {score_class}">{score_label} ({int(score * 100)}%)</span>'
    
    # Assemble full HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Brief - {policy_id}</title>
</head>
<body>
    <div class="header">
        <h1>One-Page Brief</h1>
        <p class="subtitle">{policy_id} {score_html}</p>
        <p class="meta">{meta_html}</p>
    </div>
    
    <div class="content">
        {html_content}
    </div>
    
    <div class="footer">
        <p>Generated by Broker Copilot | AI-Powered Insurance Workflow Platform</p>
        <p>This brief was generated from live data sources. All facts are linked to their original sources.</p>
        <p>Generated: {datetime.now().strftime("%B %d, %Y at %H:%M")}</p>
    </div>
</body>
</html>
"""
    return html


def generate_brief_pdf(
    policy_id: str,
    content: str,
    policy_data: Optional[Dict[str, Any]] = None,
    score: Optional[float] = None
) -> bytes:
    """
    Generate PDF from brief content.
    
    Args:
        policy_id: Policy identifier
        content: Markdown content of the brief
        policy_data: Optional policy metadata
        score: Optional priority score
    
    Returns:
        PDF bytes
    """
    logger.info(f"Generating PDF for policy", extra={"policy_id": policy_id})
    
    try:
        # Create HTML document
        logger.debug("Creating HTML content for PDF")
        html_content = create_brief_html(policy_id, content, policy_data, score)
        
        # Configure fonts
        font_config = FontConfiguration()
        
        # Create CSS
        css = CSS(string=get_dynamic_styles(), font_config=font_config)
        
        # Generate PDF
        logger.debug("Rendering PDF with WeasyPrint")
        html = HTML(string=html_content)
        pdf_bytes = html.write_pdf(stylesheets=[css], font_config=font_config)
        
        logger.info(
            f"PDF generated successfully",
            extra={
                "policy_id": policy_id,
                "pdf_size_bytes": len(pdf_bytes),
            }
        )
        
        return pdf_bytes
    except Exception as e:
        logger.error(
            f"PDF generation failed",
            extra={"policy_id": policy_id, "error": str(e)}
        )
        raise


def generate_brief_pdf_to_file(
    policy_id: str,
    content: str,
    output_path: str,
    policy_data: Optional[Dict[str, Any]] = None,
    score: Optional[float] = None
) -> str:
    """
    Generate PDF and save to file.
    
    Args:
        policy_id: Policy identifier
        content: Markdown content of the brief
        output_path: Path to save PDF
        policy_data: Optional policy metadata
        score: Optional priority score
    
    Returns:
        Path to generated PDF
    """
    logger.info(f"Generating PDF to file", extra={"policy_id": policy_id, "output_path": output_path})
    pdf_bytes = generate_brief_pdf(policy_id, content, policy_data, score)
    
    with open(output_path, 'wb') as f:
        f.write(pdf_bytes)
    
    return output_path


# Convenience function for creating sample brief
def create_sample_brief_content(policy_id: str, policy_data: Dict[str, Any]) -> str:
    """Create sample brief content for testing."""
    return f"""# Executive Summary

This brief provides a comprehensive overview of policy **{policy_id}** for **{policy_data.get('client_name', 'Unknown Client')}**.

## Key Facts

- **Premium at Risk**: ${policy_data.get('premium_at_risk', 0):,.0f}
- **Days to Expiry**: {policy_data.get('days_to_expiry', 'N/A')} days
- **Policy Type**: {policy_data.get('policy_type', 'N/A')}
- **Claims Frequency**: {policy_data.get('claims_frequency', 0)} claims

## Risk Assessment

Based on current data analysis, this policy requires attention due to:

1. Premium value indicates significant business relationship
2. Expiration timeline requires proactive engagement
3. Claims history suggests careful renewal negotiation

## Recommendations

| Priority | Action | Timeline |
|----------|--------|----------|
| High | Contact client to discuss renewal | Within 7 days |
| Medium | Review coverage adequacy | Within 14 days |
| Low | Update contact information | Within 30 days |

## Recent Communications

[Source: Email - Dec 1, 2025] Client expressed interest in expanding coverage options.

[Source: CRM Note] Last renewal was processed with 5% premium increase.

## Next Steps

1. Schedule renewal discussion call
2. Prepare competitive quote comparison
3. Review claims history for negotiation points

---

*This brief is generated from live data sources. Click any citation to view the original source.*
"""
