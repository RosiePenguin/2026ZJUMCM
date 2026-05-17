from __future__ import annotations

import random
from dataclasses import dataclass


GROUP_COUNT = 16
GROUP_SIZE = 4


@dataclass
class Solution:
    groups: dict[str, list[dict]]
    metrics: dict[str, float]


def build_group_names() -> list[str]:
    return [f"G{i:02d}" for i in range(1, GROUP_COUNT + 1)]


def team_strength(team_name: str, level: str) -> float:
    base = 75.0 if level == "city" else 60.0
    offset = sum(ord(ch) for ch in team_name) % 17
    return base + offset


def initialize_groups(rng: random.Random) -> tuple[dict[str, list[dict]], list[str]]:
    groups = {name: [] for name in build_group_names()}
    city_team_groups = rng.sample(list(groups.keys()), 11)
    return groups, city_team_groups


def place_city_teams(groups: dict[str, list[dict]], teams: list[dict], chosen_groups: list[str]) -> None:
    city_teams = sorted((team for team in teams if team["level"] == "city"), key=lambda item: item["team_name"])
    for group_name, team in zip(chosen_groups, city_teams):
        groups[group_name].append(team.copy())


def county_sort_key(row: dict[str, str], city_counts: dict[str, int]) -> tuple[int, str]:
    return (-city_counts[row["parent_city"]], row["team_name"])


def pick_group_for_county(row: dict[str, str], groups: dict[str, list[dict]], rng: random.Random) -> str | None:
    candidates: list[tuple[float, str]] = []
    for group_name, members in groups.items():
        if len(members) >= GROUP_SIZE:
            continue

        if any(member["level"] == "city" and member["parent_city"] == row["parent_city"] for member in members):
            continue

        same_city_count = sum(member["parent_city"] == row["parent_city"] for member in members)
        total_members = len(members)
        noise = rng.random() * 0.2
        score = same_city_count * 5 + total_members * 1.5 + noise
        candidates.append((score, group_name))

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0])
    top_k = candidates[: min(3, len(candidates))]
    return rng.choice(top_k)[1]


def generate_one_solution(teams: list[dict], seed: int) -> dict[str, list[dict]] | None:
    rng = random.Random(seed)
    groups, city_team_groups = initialize_groups(rng)
    place_city_teams(groups, teams, city_team_groups)

    county_teams = [team.copy() for team in teams if team["level"] == "county"]
    city_counts: dict[str, int] = {}
    for team in county_teams:
        city_counts[team["parent_city"]] = city_counts.get(team["parent_city"], 0) + 1

    county_rows = sorted(county_teams, key=lambda row: county_sort_key(row, city_counts))
    for row in county_rows:
        group_name = pick_group_for_county(row, groups, rng)
        if group_name is None:
            return None
        groups[group_name].append(row.copy())

    if not all(len(members) == GROUP_SIZE for members in groups.values()):
        return None

    return groups
