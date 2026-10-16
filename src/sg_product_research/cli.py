from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Dict, List, Tuple

from .model import Candidate, score_candidate
from .research import EVIDENCE_PATH, evidence_gate, load_evidence, summarize_evidence


NUMERIC_FIELDS = {
    "demand_score": float,
    "trend_score": float,
    "competition_score": float,
    "logistics_score": float,
    "content_fit_score": float,
    "evidence_confidence": float,
    "compliance_risk": int,
    "ip_risk": int,
    "supplier_cost_cny": float,
    "freight_cny": float,
    "retail_price_sgd": float,
    "cny_per_sgd": float,
    "platform_fee_rate": float,
    "ad_cost_rate": float,
    "return_loss_rate": float,
}


def load_candidates(path: Path) -> List[Tuple[Dict[str, str], Candidate]]:
    rows: List[Tuple[Dict[str, str], Candidate]] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for raw in csv.DictReader(handle):
            values = {field: converter(raw[field]) for field, converter in NUMERIC_FIELDS.items()}
            candidate = Candidate(
                product_id=raw["product_id"],
                name_zh=raw["name_zh"],
                **values,
            )
            rows.append((raw, candidate))
    return rows


def write_outputs(rows: List[Tuple[Dict[str, str], Candidate]], output_dir: Path, evidence_path: Path = EVIDENCE_PATH) -> None:
    evidence = load_evidence(evidence_path)
    ranked = [(raw, candidate, evidence_gate(score_candidate(candidate), summarize_evidence(
        [record for record in evidence if record["product_id"] == candidate.product_id]
    ))) for raw, candidate in rows]
    ranked.sort(key=lambda item: item[2].score, reverse=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    with (output_dir / "ranking.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        fieldnames = [
            "rank", "product_id", "name_zh", "score", "decision", "unit_profit_sgd",
            "contribution_margin", "evidence_confidence", "evidence_date", "source_ids", "reason",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for index, (raw, candidate, result) in enumerate(ranked, start=1):
            writer.writerow({
                "rank": index,
                "product_id": candidate.product_id,
                "name_zh": candidate.name_zh,
                "score": result.score,
                "decision": result.decision,
                "unit_profit_sgd": result.unit_profit_sgd,
                "contribution_margin": f"{result.contribution_margin:.1%}",
                "evidence_confidence": candidate.evidence_confidence,
                "evidence_date": raw["evidence_date"],
                "source_ids": raw["source_ids"],
                "reason": result.reason,
            })

    report = [
        "# 新加坡选品评分结果",
        "",
        "> 这是基于公开信号与成本假设的筛选结果，不是平台真实销量证明。报价、运费和合规状态须在下单前复核。",
        "",
        "| 排名 | 候选 | 得分 | 决策 | 单件利润(SGD) | 贡献毛利率 | 证据置信度 |",
        "|---:|---|---:|---|---:|---:|---:|",
    ]
    for index, (_, candidate, result) in enumerate(ranked, start=1):
        report.append(
            f"| {index} | {candidate.name_zh} | {result.score:.2f} | {result.decision} | "
            f"{result.unit_profit_sgd:.2f} | {result.contribution_margin:.1%} | "
            f"{candidate.evidence_confidence:.0f} |"
        )
    report.extend([
        "",
        "## 决策规则",
        "",
        "- `TEST`: 得分至少 70 且近期交叉证据齐备，可评估 20-50 件小批量测试，采购前仍需复核。",
        "- `WATCH`: 得分 55-69.99，或高分但近期交叉证据不足。",
        "- `DROP`: 得分低于 55。",
        "- `BLOCK`: 合规/IP 风险达到 4，或保守贡献毛利率低于 20%。",
        "",
        "计算口径见 `docs/methodology.md`，原始假设见 `data/candidates.csv`。",
    ])
    (output_dir / "ranking.md").write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="生成中国到新加坡跨境电商选品排名")
    parser.add_argument("--input", type=Path, default=Path("data/candidates.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("generated"))
    args = parser.parse_args()
    write_outputs(load_candidates(args.input), args.output_dir)
    print(f"Generated {args.output_dir / 'ranking.csv'} and {args.output_dir / 'ranking.md'}")


if __name__ == "__main__":
    main()
