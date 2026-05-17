from __future__ import annotations

import math
from dataclasses import dataclass

from .data_loader import Region


@dataclass(frozen=True)
class VenueWeights:
    name: str
    avg_travel: float
    worst_travel: float
    fairness: float
    impact: float
    capacity: float
    home_penalty: float = 8.0

    def objective_weights(self) -> tuple[float, ...]:
        return (
            self.avg_travel,
            self.worst_travel,
            self.fairness,
            self.impact,
            self.capacity,
        )


def entropy_weight(matrix: list[list[float]], epsilon: float = 1e-4) -> list[float]:
    """Compute indicator weights via the Entropy Weight Method.

    Args:
        matrix: n rows (samples) × m columns (indicators), each value >= 0.
        epsilon: offset for zero entries so that ln(0) is avoided.

    Returns:
        List of m weights that sum to 1.0.  An indicator whose values are
        nearly identical across all samples receives a weight close to 0;
        an indicator with high dispersion receives a higher weight.
    """
    n = len(matrix)
    if n == 0:
        raise ValueError("entropy_weight: empty matrix")
    m = len(matrix[0])
    if m == 0:
        raise ValueError("entropy_weight: empty indicators")

    # Step 1 — shift to guarantee all values > 0
    shifted = [[max(val, 0.0) + epsilon for val in row] for row in matrix]

    # Step 2 — proportion normalisation per column
    col_sums = [sum(row[j] for row in shifted) for j in range(m)]
    p = [[shifted[i][j] / col_sums[j] for j in range(m)] for i in range(n)]

    # Step 3 — entropy per indicator
    ln_n = math.log(n)
    entropies: list[float] = []
    for j in range(m):
        e_j = 0.0
        for i in range(n):
            p_ij = p[i][j]
            if p_ij > 0:
                e_j += p_ij * math.log(p_ij)
        entropies.append(-e_j / ln_n)

    # Step 4 — information utility
    d = [1.0 - e for e in entropies]

    # Step 5 — normalise to weights
    d_sum = sum(d)
    if d_sum == 0:
        return [1.0 / m] * m
    return [dj / d_sum for dj in d]


def compute_impact_entropy_weights(regions: list[Region]) -> ImpactWeights:
    """Derive ImpactWeights from region indicator dispersion via entropy."""
    matrix = [
        [r.population_score, r.gdp_score, r.transport_score, r.football_score]
        for r in regions
    ]
    w = entropy_weight(matrix)
    return ImpactWeights(
        population=w[0],
        gdp=w[1],
        transport=w[2],
        sports_atmosphere=w[3],
    )


def compute_capacity_entropy_weights(regions: list[Region]) -> CapacityWeights:
    """Derive CapacityWeights from region capacity-indicator dispersion via entropy."""
    matrix = [
        [r.sports_base_score, r.stadium_capacity_score, r.rail_access_score, r.airport_access_score]
        for r in regions
    ]
    w = entropy_weight(matrix)
    return CapacityWeights(
        sports_base=w[0],
        stadium_capacity=w[1],
        rail_access=w[2],
        airport_access=w[3],
    )


def compute_venue_objective_entropy_weights(
    objective_matrix: list[list[float]],
) -> VenueWeights:
    """Derive VenueWeights from pair-venue objective-score dispersion via entropy.

    Args:
        objective_matrix: n rows × 5 columns where each row corresponds to one
            (group_pair, venue) combination and the columns are:
            [travel_score, worst_travel_score, fairness_score, impact_score, capacity_score].
    """
    w = entropy_weight(objective_matrix)
    return VenueWeights(
        name="entropy",
        avg_travel=w[0],
        worst_travel=w[1],
        fairness=w[2],
        impact=w[3],
        capacity=w[4],
    )


@dataclass(frozen=True)
class ImpactWeights:
    population: float
    gdp: float
    transport: float
    sports_atmosphere: float

    def components(self) -> tuple[float, ...]:
        return (self.population, self.gdp, self.transport, self.sports_atmosphere)


@dataclass(frozen=True)
class CapacityWeights:
    sports_base: float
    stadium_capacity: float
    rail_access: float
    airport_access: float

    def components(self) -> tuple[float, ...]:
        return (self.sports_base, self.stadium_capacity, self.rail_access, self.airport_access)


# Balanced weights follow a hierarchy used in the model notes:
# travel burden first, then fairness and social impact, with venue feasibility as
# an explicit condition.  Alternative scenarios stress-test that hierarchy.
IMPACT_WEIGHTS = ImpactWeights(
    population=0.30,
    gdp=0.30,
    transport=0.25,
    sports_atmosphere=0.15,
)

CAPACITY_WEIGHTS = CapacityWeights(
    sports_base=0.15,
    stadium_capacity=0.50,
    rail_access=0.20,
    airport_access=0.15,
)


SCENARIOS = [
    VenueWeights(
        name="balanced",
        avg_travel=0.32,
        worst_travel=0.18,
        fairness=0.20,
        impact=0.18,
        capacity=0.12,
    ),
    VenueWeights(
        name="travel_first",
        avg_travel=0.42,
        worst_travel=0.24,
        fairness=0.16,
        impact=0.08,
        capacity=0.10,
    ),
    VenueWeights(
        name="impact_first",
        avg_travel=0.25,
        worst_travel=0.15,
        fairness=0.15,
        impact=0.33,
        capacity=0.12,
    ),
]


def _validate_sum(name: str, components: tuple[float, ...], expected: float = 1.0) -> None:
    if abs(sum(components) - expected) > 1e-9:
        raise ValueError(f"{name} weights must sum to {expected}")


_validate_sum("impact", IMPACT_WEIGHTS.components())
_validate_sum("capacity", CAPACITY_WEIGHTS.components())
for _scenario in SCENARIOS:
    _validate_sum(_scenario.name, _scenario.objective_weights())


def get_scenario(name: str) -> VenueWeights:
    for scenario in SCENARIOS:
        if scenario.name == name:
            return scenario
    raise ValueError(f"unknown venue scoring scenario: {name}")
