"""Scoring: location (log) × industry weight."""
import math


def score_company(location_count: int, industry: str, industry_weights: dict) -> float:
    """
    Score = location_score * industry_weight.
    Location (0–70): 70 * ln(count) / ln(50), clamped.
    """
    if location_count <= 0:
        loc_score = 0.0
    else:
        loc_score = 70.0 * math.log(location_count) / math.log(50)
        loc_score = max(0.0, min(70.0, loc_score))
    ind_weight = industry_weights.get(industry, 1.0)
    return round(loc_score * ind_weight, 2)
