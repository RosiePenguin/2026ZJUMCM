from __future__ import annotations

import csv
from pathlib import Path


def load_teams(csv_path: str | Path) -> list[dict[str, str]]:
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        teams = list(reader)

    required_columns = {"team_name", "level", "parent_city"}
    if not teams:
        raise ValueError("teams.csv is empty")

    missing = required_columns - set(teams[0].keys())
    if missing:
        raise ValueError(f"teams.csv missing columns: {sorted(missing)}")

    normalized = []
    for row in teams:
        normalized.append(
            {
                "team_name": str(row["team_name"]),
                "level": str(row["level"]),
                "parent_city": str(row["parent_city"]),
            }
        )
    return normalized
