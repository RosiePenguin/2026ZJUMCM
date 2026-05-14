from __future__ import annotations

import csv
from pathlib import Path

from .data_loader import load_teams
from .generator import Solution, generate_one_solution, team_strength
from .scoring import evaluate_groups


def prepare_teams(csv_path: str | Path) -> list[dict[str, str | float]]:
    teams = load_teams(csv_path)
    enriched = []
    for row in teams:
        item = row.copy()
        item["strength"] = team_strength(row["team_name"], row["level"])
        enriched.append(item)
    return enriched


def search_solutions(csv_path: str | Path, trials: int = 300) -> list[Solution]:
    teams = prepare_teams(csv_path)
    solutions: list[Solution] = []

    for seed in range(1, trials + 1):
        groups = generate_one_solution(teams, seed=seed)
        if groups is None:
            continue
        metrics = evaluate_groups(groups)
        solutions.append(Solution(groups=groups, metrics=metrics))

    solutions.sort(key=lambda item: item.metrics["final_score"], reverse=True)
    return solutions


def write_groups_csv(groups: dict[str, list[dict]], output_path: str | Path) -> None:
    fieldnames = ["group", "team_name", "level", "parent_city", "strength"]
    rows = []
    for group_name, members in groups.items():
        for member in members:
            rows.append(
                {
                    "group": group_name,
                    "team_name": member["team_name"],
                    "level": member["level"],
                    "parent_city": member["parent_city"],
                    "strength": member["strength"],
                }
            )

    rows.sort(key=lambda item: (item["group"], item["level"], item["team_name"]))
    with open(output_path, "w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_metrics_csv(solutions: list[Solution], output_path: str | Path) -> None:
    fieldnames = ["rank", "soft_conflict_pairs", "avg_city_entropy", "strength_balance_std", "final_score"]
    with open(output_path, "w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for index, solution in enumerate(solutions, start=1):
            row = {"rank": index}
            row.update(solution.metrics)
            writer.writerow(row)


def write_summary(solutions: list[Solution], output_path: str | Path, top_n: int = 5) -> None:
    best = solutions[0]
    with open(output_path, "w", encoding="utf-8") as file:
        file.write("Team A Summary\n")
        file.write("====================\n")
        file.write(f"Feasible solutions found: {len(solutions)}\n\n")
        file.write("Best solution metrics:\n")
        for key, value in best.metrics.items():
            file.write(f"- {key}: {value}\n")
        file.write("\nTop solutions:\n")
        for index, solution in enumerate(solutions[:top_n], start=1):
            file.write(
                f"{index}. score={solution.metrics['final_score']}, "
                f"conflicts={solution.metrics['soft_conflict_pairs']}, "
                f"entropy={solution.metrics['avg_city_entropy']}, "
                f"balance_std={solution.metrics['strength_balance_std']}\n"
            )
