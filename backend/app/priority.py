from math import exp
from typing import Dict, Any, Tuple

def time_decay_score(days_to_expiry: float) -> float:
    """Non-linear decay: as expiry nears, priority increases.
    We'll use an inverse exponential curve clamped to [0,1].
    """
    if days_to_expiry <= 0:
        return 1.0
    # scale so that at 90 days it's low, at 1 day it's near 1
    k = 0.05
    return 1 - exp(-k * max(0.0, 90 - min(days_to_expiry, 90)))

def deterministic_score(policy: Dict[str, Any]) -> Tuple[float, Dict[str, float]]:
    """Compute a deterministic priority score in [0,1].
    Inputs expected in policy dict:
    - premium_at_risk (float)
    - days_to_expiry (float)
    - claims_frequency (float)
    Returns (score, breakdown)
    """
    premium = float(policy.get("premium_at_risk", 0.0))
    days = float(policy.get("days_to_expiry", 90.0))
    claims = float(policy.get("claims_frequency", 0.0))

    # Normalize premium: assume 0-250k meaningful range
    prem_norm = min(premium / 250000.0, 1.0)

    # Normalize claims frequency: assume 0-10
    claims_norm = min(claims / 10.0, 1.0)

    decay = time_decay_score(days)

    # Weighted combination
    w_premium = 0.5
    w_time = 0.35
    w_claims = 0.15

    score = (w_premium * prem_norm) + (w_time * decay) + (w_claims * claims_norm)
    score = max(0.0, min(1.0, score))

    breakdown = {
        "premium_component": w_premium * prem_norm,
        "time_component": w_time * decay,
        "claims_component": w_claims * claims_norm,
    }
    return score, breakdown
