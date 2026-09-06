from __future__ import annotations

import unittest

from sg_product_research.model import Candidate, score_candidate


def candidate(**overrides: float | int | str) -> Candidate:
    values: dict[str, float | int | str] = {
        "product_id": "test-product",
        "name_zh": "测试商品",
        "demand_score": 85,
        "trend_score": 85,
        "competition_score": 70,
        "logistics_score": 80,
        "content_fit_score": 85,
        "evidence_confidence": 80,
        "compliance_risk": 1,
        "ip_risk": 1,
        "supplier_cost_cny": 30,
        "freight_cny": 15,
        "retail_price_sgd": 34.9,
    }
    values.update(overrides)
    return Candidate(**values)  # type: ignore[arg-type]


class ScoreCandidateTests(unittest.TestCase):
    def test_viable_candidate_enters_test_queue(self) -> None:
        result = score_candidate(candidate())

        self.assertEqual(result.decision, "TEST")
        self.assertGreater(result.unit_profit_sgd, 0)

    def test_high_trend_does_not_override_ip_gate(self) -> None:
        result = score_candidate(candidate(ip_risk=5, trend_score=100))

        self.assertEqual(result.decision, "BLOCK")

    def test_low_margin_is_blocked(self) -> None:
        result = score_candidate(candidate(supplier_cost_cny=100, freight_cny=30))

        self.assertEqual(result.decision, "BLOCK")
        self.assertLess(result.contribution_margin, 0.20)


if __name__ == "__main__":
    unittest.main()