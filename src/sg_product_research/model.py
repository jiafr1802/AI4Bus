from __future__ import annotations

from dataclasses import dataclass


GST_RATE = 0.09


@dataclass(frozen=True)
class Candidate:
    product_id: str
    name_zh: str
    demand_score: float
    trend_score: float
    competition_score: float
    logistics_score: float
    content_fit_score: float
    evidence_confidence: float
    compliance_risk: int
    ip_risk: int
    supplier_cost_cny: float
    freight_cny: float
    retail_price_sgd: float
    cny_per_sgd: float = 5.5
    platform_fee_rate: float = 0.12
    ad_cost_rate: float = 0.15
    return_loss_rate: float = 0.04


@dataclass(frozen=True)
class ScoreResult:
    score: float
    unit_profit_sgd: float
    contribution_margin: float
    decision: str
    reason: str


def _bounded(value: float, field: str) -> float:
    if not 0 <= value <= 100:
        raise ValueError(f"{field} must be between 0 and 100")
    return value


def score_candidate(candidate: Candidate) -> ScoreResult:
    """Score a candidate while preserving compliance and unit-economics gates."""
    scored_fields = {
        "demand_score": candidate.demand_score,
        "trend_score": candidate.trend_score,
        "competition_score": candidate.competition_score,
        "logistics_score": candidate.logistics_score,
        "content_fit_score": candidate.content_fit_score,
        "evidence_confidence": candidate.evidence_confidence,
    }
    for field, value in scored_fields.items():
        _bounded(value, field)

    if candidate.cny_per_sgd <= 0 or candidate.retail_price_sgd <= 0:
        raise ValueError("exchange rate and retail price must be positive")

    landed_cost = (candidate.supplier_cost_cny + candidate.freight_cny) / candidate.cny_per_sgd
    net_revenue = candidate.retail_price_sgd / (1 + GST_RATE)
    variable_cost = candidate.retail_price_sgd * (
        candidate.platform_fee_rate + candidate.ad_cost_rate + candidate.return_loss_rate
    )
    unit_profit = net_revenue - landed_cost - variable_cost
    contribution_margin = unit_profit / net_revenue
    margin_score = max(0.0, min(100.0, contribution_margin / 0.40 * 100))

    base_score = (
        candidate.demand_score * 0.25
        + candidate.trend_score * 0.15
        + margin_score * 0.25
        + candidate.logistics_score * 0.15
        + candidate.competition_score * 0.10
        + candidate.content_fit_score * 0.10
    )
    confidence_multiplier = 0.70 + candidate.evidence_confidence / 100 * 0.30
    risk_penalty = candidate.compliance_risk * 4 + candidate.ip_risk * 6
    score = max(0.0, min(100.0, base_score * confidence_multiplier - risk_penalty))

    if candidate.compliance_risk >= 4 or candidate.ip_risk >= 4:
        decision, reason = "BLOCK", "合规或知识产权风险达到硬门槛"
    elif contribution_margin < 0.20:
        decision, reason = "BLOCK", "保守贡献毛利率低于20%"
    elif score >= 70:
        decision, reason = "TEST", "进入小批量测试"
    elif score >= 55:
        decision, reason = "WATCH", "补充证据后复评"
    else:
        decision, reason = "DROP", "当前综合分不足"

    return ScoreResult(
        score=round(score, 2),
        unit_profit_sgd=round(unit_profit, 2),
        contribution_margin=round(contribution_margin, 4),
        decision=decision,
        reason=reason,
    )
