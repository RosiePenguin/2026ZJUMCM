from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Region:
    region_name: str
    team_name: str
    level: str
    parent_city: str
    lat: float
    lon: float
    population_score: float
    gdp_score: float
    transport_score: float
    football_score: float
    sports_base_score: float
    has_rail_station: str
    nearest_airport: str
    nearest_airport_km: float | None
    stadium_name: str
    stadium_capacity: float | None
    data_quality: str
    stadium_capacity_score: float
    rail_access_score: float
    airport_access_score: float


@dataclass(frozen=True)
class Team:
    group: str
    team_name: str
    level: str
    parent_city: str
    strength: float
    region: Region


@dataclass(frozen=True)
class StrengthProxyWeights:
    population: float
    gdp: float
    transport: float
    football: float
    sports_base: float

    def components(self) -> tuple[float, ...]:
        return (self.population, self.gdp, self.transport, self.football, self.sports_base)


def load_regions(csv_path: str | Path) -> dict[str, Region]:
    required_columns = {
        "region_name",
        "team_name",
        "level",
        "parent_city",
        "lat",
        "lon",
        "population_score",
        "gdp_score",
        "transport_score",
        "football_score",
        "has_rail_station",
        "nearest_airport",
        "nearest_airport_km",
        "stadium_name",
        "stadium_capacity",
        "data_quality",
    }
    regions: dict[str, Region] = {}
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        missing = required_columns - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"region metrics missing columns: {sorted(missing)}")
        rows = list(reader)
        score_column = choose_sports_base_score_column(reader.fieldnames or [])

        capacity_scores = compute_stadium_capacity_scores(rows)
        for row in rows:
            team_name = row["team_name"]
            if team_name in regions:
                raise ValueError(f"duplicate team in region metrics: {team_name}")
            regions[team_name] = Region(
                region_name=row["region_name"],
                team_name=team_name,
                level=row["level"],
                parent_city=row["parent_city"],
                lat=float(row["lat"]),
                lon=float(row["lon"]),
                population_score=float(row["population_score"]),
                gdp_score=float(row["gdp_score"]),
                transport_score=float(row["transport_score"]),
                football_score=float(row["football_score"]),
                sports_base_score=float(row[score_column]),
                has_rail_station=row["has_rail_station"],
                nearest_airport=row["nearest_airport"],
                nearest_airport_km=parse_optional_float(row["nearest_airport_km"]),
                stadium_name=row["stadium_name"],
                stadium_capacity=parse_optional_float(row["stadium_capacity"]),
                data_quality=row["data_quality"],
                stadium_capacity_score=capacity_scores[row["region_name"]],
                rail_access_score=rail_access_score(row["has_rail_station"]),
                airport_access_score=airport_access_score(
                    row["nearest_airport"],
                    parse_optional_float(row["nearest_airport_km"]),
                ),
            )
    if len(regions) != 64:
        raise ValueError(f"expected 64 region rows, got {len(regions)}")
    return regions


def choose_sports_base_score_column(fieldnames: list[str]) -> str:
    if "sports_base_score" in fieldnames:
        return "sports_base_score"
    if "stadium_score" in fieldnames:
        return "stadium_score"
    raise ValueError("region metrics missing columns: ['sports_base_score']")


def parse_optional_float(value: str) -> float | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def minmax_20to100(values: list[float]) -> list[float]:
    if not values:
        return []
    vmin = min(values)
    vmax = max(values)
    if vmax == vmin:
        return [100.0] * len(values)
    return [20.0 + (value - vmin) / (vmax - vmin) * 80.0 for value in values]


def minmax_60to90(values: list[float]) -> list[float]:
    if not values:
        return []
    vmin = min(values)
    vmax = max(values)
    if vmax == vmin:
        return [75.0] * len(values)
    return [60.0 + (value - vmin) / (vmax - vmin) * 30.0 for value in values]


def entropy_weight(matrix: list[list[float]], epsilon: float = 1e-6) -> list[float]:
    n = len(matrix)
    if n == 0:
        raise ValueError("entropy_weight: empty matrix")
    m = len(matrix[0])
    shifted = [[max(value, 0.0) + epsilon for value in row] for row in matrix]
    column_sums = [sum(row[index] for row in shifted) for index in range(m)]
    proportions = [
        [row[index] / column_sums[index] for index in range(m)]
        for row in shifted
    ]
    entropies: list[float] = []
    for index in range(m):
        entropy = 0.0
        for row in proportions:
            p = row[index]
            if p > 0:
                entropy += p * math.log(p)
        entropies.append(-entropy / math.log(n))
    utilities = [1.0 - entropy for entropy in entropies]
    total = sum(utilities)
    if total == 0:
        return [1.0 / m] * m
    return [value / total for value in utilities]


def compute_strength_proxy_weights(regions: list[Region]) -> StrengthProxyWeights:
    matrix = [
        [
            region.population_score,
            region.gdp_score,
            region.transport_score,
            region.football_score,
            region.sports_base_score,
        ]
        for region in regions
    ]
    weights = entropy_weight(matrix)
    return StrengthProxyWeights(
        population=weights[0],
        gdp=weights[1],
        transport=weights[2],
        football=weights[3],
        sports_base=weights[4],
    )


def compute_strength_proxies(regions: list[Region]) -> tuple[dict[str, float], StrengthProxyWeights]:
    weights = compute_strength_proxy_weights(regions)
    raw_scores = [
        sum(
            value * weight
            for value, weight in zip(
                (
                    region.population_score,
                    region.gdp_score,
                    region.transport_score,
                    region.football_score,
                    region.sports_base_score,
                ),
                weights.components(),
            )
        )
        for region in regions
    ]
    scaled_scores = minmax_60to90(raw_scores)
    return {
        region.team_name: round(score, 4)
        for region, score in zip(regions, scaled_scores)
    }, weights


def quality_multiplier(data_quality: str) -> float:
    if "在建" in data_quality or "in progress" in data_quality:
        return 0.75
    if "partial" in data_quality:
        return 0.85
    return 1.0


def compute_stadium_capacity_scores(rows: list[dict[str, str]]) -> dict[str, float]:
    numeric_capacities = [
        parse_optional_float(row["stadium_capacity"])
        for row in rows
        if row["stadium_name"].strip() and parse_optional_float(row["stadium_capacity"]) is not None
    ]
    logged_scores = minmax_20to100([math.log1p(value) for value in numeric_capacities])
    capacity_to_scores: dict[float, list[float]] = {}
    for capacity, score in zip(numeric_capacities, logged_scores):
        capacity_to_scores.setdefault(capacity, []).append(score)

    scores: dict[str, float] = {}
    for row in rows:
        capacity = parse_optional_float(row["stadium_capacity"])
        if not row["stadium_name"].strip() or capacity is None:
            base_score = 20.0
        else:
            base_score = capacity_to_scores[capacity].pop(0)
        adjusted = base_score * quality_multiplier(row["data_quality"])
        scores[row["region_name"]] = round(max(0.0, min(100.0, adjusted)), 2)
    return scores


def rail_access_score(has_rail_station: str) -> float:
    text = has_rail_station.strip()
    if not text or "无铁路客运站" in text:
        return 0.0
    if "最近" in text or "客运有限" in text:
        return 60.0
    return 100.0


def airport_access_score(nearest_airport: str, distance_km: float | None) -> float:
    if distance_km is None:
        score = 20.0
    elif distance_km <= 30:
        score = 100.0
    elif distance_km <= 60:
        score = 100.0 - (distance_km - 30.0) / 30.0 * 20.0
    elif distance_km <= 100:
        score = 80.0 - (distance_km - 60.0) / 40.0 * 30.0
    elif distance_km <= 160:
        score = 50.0 - (distance_km - 100.0) / 60.0 * 30.0
    else:
        score = 20.0

    if "在建" in nearest_airport:
        score *= 0.7
    return round(max(0.0, min(100.0, score)), 2)


def load_group_assignments(csv_path: str | Path, regions: dict[str, Region]) -> dict[str, list[Team]]:
    required_columns = {"group", "team_name", "level", "parent_city", "strength"}
    groups: dict[str, list[Team]] = {}
    strength_proxies, _ = compute_strength_proxies(list(regions.values()))
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        missing = required_columns - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"group file missing columns: {sorted(missing)}")
        for row in reader:
            team_name = row["team_name"]
            if team_name not in regions:
                raise ValueError(f"group team lacks region metrics: {team_name}")
            team = Team(
                group=row["group"],
                team_name=team_name,
                level=row["level"],
                parent_city=row["parent_city"],
                strength=strength_proxies[team_name],
                region=regions[team_name],
            )
            groups.setdefault(team.group, []).append(team)

    if len(groups) != 16:
        raise ValueError(f"expected 16 groups, got {len(groups)}")
    for group_name, members in groups.items():
        if len(members) != 4:
            raise ValueError(f"{group_name} expected 4 teams, got {len(members)}")
    if sum(len(members) for members in groups.values()) != 64:
        raise ValueError("group assignments must contain exactly 64 teams")
    return dict(sorted(groups.items()))
