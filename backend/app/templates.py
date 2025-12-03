from jinja2 import Template
from typing import Dict, Any

# Dynamic Template Engine using Jinja2 for Markdown + placeholders

def render_template(template_text: str, context: Dict[str, Any]) -> str:
    t = Template(template_text)
    return t.render(**context)

# Example usage:
# tpl = "Hello {{client_name}}, your policy {{policy_number}} expires on {{expiry_date}}."
# render_template(tpl, {"client_name": "ACME", "policy_number": "P-123", "expiry_date": "2026-01-15"})
