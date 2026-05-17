from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import combinations

from .data_loader import Region, Team
from .weights import CAPACITY_WEIGHTS, IMPACT_WEIGHTS, CapacityWeights, ImpactWeights, VenueWeights, get_scenario


EARTH_RADIUS_KM = 6371.0088


@dataclass(frozen=True)
class CandidateScore:
    scenario: str
    group_a: str
    group_b: str
    venue_team_name: str
    venue_region_name: str
    avg_distance_km: float
    max_distance_km: float
    distance_std_km: float
    travel_score: float
    worst_travel_score: float
    fairness_score: float
    impact_score: float
    capacity_score: float
    home_penalty: float
    total_score: float


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def mean(values: list[float]) -> float:
    return sum(values) / len(values)


def std(values: list[float]) -> float:
    avg = mean(values)
    return (sum((value - avg) ** 2 for value in values) / len(values)) ** 0.5


def clamp(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
    return min(upper, max(lower, value))


def impact_score(region: Region, weights: ImpactWeights | None = None) -> float:
    w = weights or IMPACT_WEIGHTS
    weighted = (
        region.population_score * w.population
        + region.gdp_score * w.gdp
        + region.transport_score * w.transport
        + region.football_score * w.sports_atmosphere
    )
    return weighted / 5.0 * 100.0


def capacity_score(region: Region, weights: CapacityWeights | None = None) -> float:
    w = weights or CAPACITY_WEIGHTS
    sports_base_score = region.sports_base_score / 5.0 * 100.0
    return (
        sports_base_score * w.sports_base
        + region.stadium_capacity_score * w.stadium_capacity
        + region.rail_access_score * w.rail_access
        + region.airport_access_score * w.airport_access
    )


def city_concentration_score(teams: list[Team]) -> float:
    city_counts: dict[str, int] = {}
    for team in teams:
        city_counts[team.parent_city] = city_counts.get(team.parent_city, 0) + 1
    excess = sum(max(0, count - 2) for count in city_counts.values())
    return clamp(100.0 - excess * 8.0)


def score_pair_venue(
    group_a: str,
    group_b: str,
    teams: list[Team],
    venue: Region,
    weights: VenueWeights | None = None,
    impact_weights: ImpactWeights | None = None,
    capacity_weights: CapacityWeights | None = None,
) -> CandidateScore:
    weights = weights or get_scenario("balanced")
    distances = [
        haversine_km(team.region.lat, team.region.lon, venue.lat, venue.lon)
        for team in teams
    ]
    avg_distance = mean(distances)
    max_distance = max(distances)
    distance_std = std(distances)

    travel_score = clamp(100.0 - avg_distance / 260.0 * 100.0 + venue.transport_score * 4.0)
    worst_travel_score = clamp(100.0 - max_distance / 360.0 * 100.0)
    dispersion_score = clamp(100.0 - distance_std / 150.0 * 100.0)
    fairness_score = dispersion_score * 0.70 + city_concentration_score(teams) * 0.30
    venue_impact = impact_score(venue, impact_weights)
    venue_capacity = capacity_score(venue, capacity_weights)
    home_penalty = weights.home_penalty if any(team.team_name == venue.team_name for team in teams) else 0.0

    total = (
        travel_score * weights.avg_travel
        + worst_travel_score * weights.worst_travel
        + fairness_score * weights.fairness
        + venue_impact * weights.impact
        + venue_capacity * weights.capacity
        - home_penalty
    )

    return CandidateScore(
        scenario=weights.name,
        group_a=group_a,
        group_b=group_b,
        venue_team_name=venue.team_name,
        venue_region_name=venue.region_name,
        avg_distance_km=round(avg_distance, 2),
        max_distance_km=round(max_distance, 2),
        distance_std_km=round(distance_std, 2),
        travel_score=round(travel_score, 2),
        worst_travel_score=round(worst_travel_score, 2),
        fairness_score=round(fairness_score, 2),
        impact_score=round(venue_impact, 2),
        capacity_score=round(venue_capacity, 2),
        home_penalty=round(home_penalty, 2),
        total_score=round(total, 2),
    )


def rank_pair_venues(
    group_a: str,
    group_b: str,
    groups: dict[str, list[Team]],
    venues: list[Region],
    weights: VenueWeights | None = None,
    limit: int = 10,
    impact_weights: ImpactWeights | None = None,
    capacity_weights: CapacityWeights | None = None,
) -> list[CandidateScore]:
    teams = groups[group_a] + groups[group_b]
    scenario = weights or get_scenario("balanced")
    scores = [
        score_pair_venue(group_a, group_b, teams, venue, scenario, impact_weights, capacity_weights)
        for venue in venues
    ]
    scores.sort(key=lambda item: item.total_score, reverse=True)
    return scores[:limit]


def build_pair_scores(
    groups: dict[str, list[Team]],
    venues: list[Region],
    weights: VenueWeights | None = None,
    candidate_limit: int = 10,
    impact_weights: ImpactWeights | None = None,
    capacity_weights: CapacityWeights | None = None,
) -> dict[tuple[str, str], list[CandidateScore]]:
    scenario = weights or get_scenario("balanced")
    scores: dict[tuple[str, str], list[CandidateScore]] = {}
    for group_a, group_b in combinations(groups.keys(), 2):
        scores[(group_a, group_b)] = rank_pair_venues(
            group_a, group_b, groups, venues, scenario, candidate_limit,
            impact_weights, capacity_weights,
        )
    return scores


def _collect_pair_venue_objective_matrix(
    groups: dict[str, list[Team]],
    venues: list[Region],
    impact_weights: ImpactWeights | None = None,
    capacity_weights: CapacityWeights | None = None,
) -> list[list[float]]:
    """Compute all pair-venue sub-scores and return them as an n×5 matrix.

    Columns: [travel_score, worst_travel_score, fairness_score, impact_score, capacity_score].
    Weights are not needed because sub-scores are computed independently of them.
    """
    matrix: list[list[float]] = []
    for group_a, group_b in combinations(groups.keys(), 2):
        teams = groups[group_a] + groups[group_b]
        for venue in venues:
            distances = [
                haversine_km(team.region.lat, team.region.lon, venue.lat, venue.lon)
                for team in teams
            ]
            avg_distance = mean(distances)
            max_dist = max(distances)
            dist_std = std(distances)
            travel = clamp(100.0 - avg_distance / 260.0 * 100.0 + venue.transport_score * 4.0)
            worst = clamp(100.0 - max_dist / 360.0 * 100.0)
            disp = clamp(100.0 - dist_std / 150.0 * 100.0)
            fair = disp * 0.70 + city_concentration_score(teams) * 0.30
            imp = impact_score(venue, impact_weights)
            cap = capacity_score(venue, capacity_weights)
            matrix.append([travel, worst, fair, imp, cap])
    return matrix


def optimize_assignments(
    groups: dict[str, list[Team]],
    venues: list[Region],
    weights: VenueWeights | None = None,
    candidate_limit: int = 10,
    beam_width: int = 300,
    impact_weights: ImpactWeights | None = None,
    capacity_weights: CapacityWeights | None = None,
) -> list[CandidateScore]:
    scenario = weights or get_scenario("balanced")
    group_names = tuple(groups.keys())
    pair_scores = build_pair_scores(
        groups, venues, scenario, candidate_limit, impact_weights, capacity_weights
    )

    states: list[tuple[float, tuple[str, ...], frozenset[str], tuple[CandidateScore, ...]]] = [
        (0.0, group_names, frozenset(), ())
    ]
    while states:
        if not states[0][1]:
            best_plan = states[0][3]
            break

        expanded: list[tuple[float, tuple[str, ...], frozenset[str], tuple[CandidateScore, ...]]] = []
        for total, remaining, used_venues, plan in states:
            if not remaining:
                expanded.append((total, remaining, used_venues, plan))
                continue

            first = remaining[0]
            for index in range(1, len(remaining)):
                second = remaining[index]
                rest = remaining[1:index] + remaining[index + 1 :]
                pair_key = tuple(sorted((first, second)))
                for score in pair_scores[pair_key]:
                    if score.venue_team_name in used_venues:
                        continue
                    expanded.append(
                        (
                            total + score.total_score,
                            tuple(rest),
                            used_venues | {score.venue_team_name},
                            plan + (score,),
                        )
                    )

        if not expanded:
            break
        expanded.sort(key=lambda item: item[0], reverse=True)
        states = expanded[:beam_width]
    else:
        best_plan = ()

    if not states or states[0][1]:
        best_plan = ()

    if len(best_plan) != 8:
        raise RuntimeError("failed to produce 8 unique venue assignments")
    return sorted(best_plan, key=lambda item: (item.group_a, item.group_b))
