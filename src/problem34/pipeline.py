from __future__ import annotations

import csv
from pathlib import Path

from .data_loader import (
    Region,
    StrengthProxyWeights,
    Team,
    compute_strength_proxies,
    load_group_assignments,
    load_regions,
)
from .venue_model import (
    CandidateScore,
    _collect_pair_venue_objective_matrix,
    build_pair_scores,
    haversine_km,
    optimize_assignments,
)
from .weights import (
    SCENARIOS,
    compute_capacity_entropy_weights,
    compute_impact_entropy_weights,
    compute_venue_objective_entropy_weights,
    get_scenario,
)
from .tournament_model import SimulationSummary, TeamProbability, simulate_formats


def run_problem3(
    region_metrics_path: str | Path,
    best_groups_path: str | Path,
    output_dir: str | Path,
    candidate_limit: int = 12,
) -> list[CandidateScore]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    regions_by_team = load_regions(region_metrics_path)
    groups = load_group_assignments(best_groups_path, regions_by_team)
    venues = sorted(regions_by_team.values(), key=lambda item: item.team_name)
    all_regions = list(regions_by_team.values())

    # ── entropy-based sub-indicator weights ──
    entropy_impact = compute_impact_entropy_weights(all_regions)
    entropy_capacity = compute_capacity_entropy_weights(all_regions)

    # ── collect objective matrix for top-level entropy weights ──
    objective_matrix = _collect_pair_venue_objective_matrix(
        groups, venues, entropy_impact, entropy_capacity
    )
    entropy_venue = compute_venue_objective_entropy_weights(objective_matrix)

    # ── scenarios: entropy first (data-driven default), then hand-crafted ──
    all_scenarios = [entropy_venue] + list(SCENARIOS)

    scenario_plans = {
        scenario.name: optimize_assignments(
            groups, venues, scenario, candidate_limit=candidate_limit,
            impact_weights=entropy_impact, capacity_weights=entropy_capacity,
        )
        for scenario in all_scenarios
    }
    assignments = scenario_plans["entropy"]
    pair_scores = build_pair_scores(
        groups, venues, entropy_venue, candidate_limit=5,
        impact_weights=entropy_impact, capacity_weights=entropy_capacity,
    )

    write_assignments(assignments, groups, regions_by_team, output_path / "problem3_venue_assignments.csv")
    write_candidate_scores(pair_scores, regions_by_team, output_path / "problem3_venue_scores.csv")
    write_summary(assignments, output_path / "problem3_summary.txt")
    write_sensitivity(scenario_plans, output_path / "problem3_sensitivity.csv")
    write_typhoon_chart(scenario_plans, output_path / "problem3_typhoon_sensitivity.png")
    write_team_distances(assignments, groups, output_path / "problem3_team_distances.csv")
    write_group_metrics(assignments, groups, output_path / "problem3_group_metrics.csv")
    write_data_quality_report(output_path / "problem3_data_quality_report.txt", regions_by_team)
    write_entropy_weights_report(
        output_path / "problem3_entropy_weights.txt",
        entropy_impact, entropy_capacity, entropy_venue,
    )
    return assignments


def run_problem4(
    region_metrics_path: str | Path,
    best_groups_path: str | Path,
    team_distances_path: str | Path,
    output_dir: str | Path,
    simulations: int = 20000,
) -> tuple[list[SimulationSummary], list[TeamProbability]]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    regions_by_team = load_regions(region_metrics_path)
    groups = load_group_assignments(best_groups_path, regions_by_team)
    strength_proxies, strength_weights = compute_strength_proxies(list(regions_by_team.values()))
    write_strength_proxy_report(
        strength_proxies,
        strength_weights,
        regions_by_team,
        output_path / "problem4_strength_proxy.csv",
        output_path / "problem4_strength_weights.txt",
    )
    return simulate_formats(
        groups=groups,
        team_distances_path=team_distances_path,
        output_dir=output_path,
        simulations=simulations,
    )


def write_assignments(
    assignments: list[CandidateScore],
    groups: dict[str, list[Team]],
    regions_by_team: dict[str, Region],
    output_path: str | Path,
) -> None:
    fieldnames = [
        "venue_region",
        "venue_team",
        "stadium_name",
        "stadium_capacity",
        "nearest_airport",
        "nearest_airport_km",
        "groups",
        "teams",
        "avg_distance_km",
        "max_distance_km",
        "distance_std_km",
        "travel_score",
        "worst_travel_score",
        "fairness_score",
        "impact_score",
        "capacity_score",
        "home_penalty",
        "total_score",
    ]
    with open(output_path, "w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for assignment in assignments:
            teams = groups[assignment.group_a] + groups[assignment.group_b]
            venue = regions_by_team[assignment.venue_team_name]
            writer.writerow(
                {
                    "venue_region": assignment.venue_region_name,
                    "venue_team": assignment.venue_team_name,
                    "stadium_name": venue.stadium_name,
                    "stadium_capacity": format_optional_number(venue.stadium_capacity),
                    "nearest_airport": venue.nearest_airport,
                    "nearest_airport_km": format_optional_number(venue.nearest_airport_km),
                    "groups": f"{assignment.group_a}+{assignment.group_b}",
                    "teams": "、".join(team.team_name for team in teams),
                    "avg_distance_km": assignment.avg_distance_km,
                    "max_distance_km": assignment.max_distance_km,
                    "distance_std_km": assignment.distance_std_km,
                    "travel_score": assignment.travel_score,
                    "worst_travel_score": assignment.worst_travel_score,
                    "fairness_score": assignment.fairness_score,
                    "impact_score": assignment.impact_score,
                    "capacity_score": assignment.capacity_score,
                    "home_penalty": assignment.home_penalty,
                    "total_score": assignment.total_score,
                }
            )


def write_candidate_scores(
    pair_scores: dict[tuple[str, str], list[CandidateScore]],
    regions_by_team: dict[str, Region],
    output_path: str | Path,
) -> None:
    fieldnames = [
        "group_pair",
        "rank",
        "venue_region",
        "venue_team",
        "stadium_name",
        "stadium_capacity",
        "nearest_airport",
        "nearest_airport_km",
        "avg_distance_km",
        "max_distance_km",
        "travel_score",
        "worst_travel_score",
        "fairness_score",
        "impact_score",
        "capacity_score",
        "home_penalty",
        "total_score",
    ]
    with open(output_path, "w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for pair, scores in sorted(pair_scores.items()):
            for rank, score in enumerate(scores, start=1):
                venue = regions_by_team[score.venue_team_name]
                writer.writerow(
                    {
                        "group_pair": f"{pair[0]}+{pair[1]}",
                        "rank": rank,
                        "venue_region": score.venue_region_name,
                        "venue_team": score.venue_team_name,
                        "stadium_name": venue.stadium_name,
                        "stadium_capacity": format_optional_number(venue.stadium_capacity),
                        "nearest_airport": venue.nearest_airport,
                        "nearest_airport_km": format_optional_number(venue.nearest_airport_km),
                        "avg_distance_km": score.avg_distance_km,
                        "max_distance_km": score.max_distance_km,
                        "travel_score": score.travel_score,
                        "worst_travel_score": score.worst_travel_score,
                        "fairness_score": score.fairness_score,
                        "impact_score": score.impact_score,
                        "capacity_score": score.capacity_score,
                        "home_penalty": score.home_penalty,
                        "total_score": score.total_score,
                    }
                )


def format_optional_number(value: float | None) -> str:
    if value is None:
        return ""
    if value.is_integer():
        return str(int(value))
    return str(round(value, 2))


def write_strength_proxy_report(
    strength_proxies: dict[str, float],
    weights: StrengthProxyWeights,
    regions_by_team: dict[str, Region],
    csv_path: str | Path,
    txt_path: str | Path,
) -> None:
    fieldnames = [
        "team_name",
        "region_name",
        "population_score",
        "gdp_score",
        "transport_score",
        "football_score",
        "sports_base_score",
        "strength_proxy",
    ]
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for team_name, strength in sorted(
            strength_proxies.items(),
            key=lambda item: (-item[1], item[0]),
        ):
            region = regions_by_team[team_name]
            writer.writerow(
                {
                    "team_name": team_name,
                    "region_name": region.region_name,
                    "population_score": region.population_score,
                    "gdp_score": region.gdp_score,
                    "transport_score": region.transport_score,
                    "football_score": region.football_score,
                    "sports_base_score": region.sports_base_score,
                    "strength_proxy": strength,
                }
            )
    with open(txt_path, "w", encoding="utf-8") as file:
        file.write("Problem 4 Strength Proxy Weights\n")
        file.write("================================\n")
        file.write("Strength is synthesized from region_metrics.csv by entropy weights over 64 regions, then min-max scaled to [60, 90].\n\n")
        file.write(f"- population_score: {weights.population:.6f}\n")
        file.write(f"- gdp_score: {weights.gdp:.6f}\n")
        file.write(f"- transport_score: {weights.transport:.6f}\n")
        file.write(f"- football_score: {weights.football:.6f}\n")
        file.write(f"- sports_base_score: {weights.sports_base:.6f}\n")


def write_summary(assignments: list[CandidateScore], output_path: str | Path) -> None:
    avg_distance = sum(item.avg_distance_km for item in assignments) / len(assignments)
    max_distance = max(item.max_distance_km for item in assignments)
    total_score = sum(item.total_score for item in assignments)
    impact_total = sum(item.impact_score for item in assignments)
    home_count = sum(1 for item in assignments if item.home_penalty > 0)
    used_groups = sorted(group for item in assignments for group in (item.group_a, item.group_b))

    with open(output_path, "w", encoding="utf-8") as file:
        file.write("Problem 3 Venue Selection Summary\n")
        file.write("=================================\n")
        file.write("Model: entropy-weighted multi-objective discrete facility-location model with venue-capacity, access and soft home-advantage terms.\n\n")
        file.write("Recommended venues:\n")
        for index, item in enumerate(assignments, start=1):
            file.write(
                f"{index}. {item.venue_region_name}: {item.group_a}+{item.group_b}, "
                f"avg_distance={item.avg_distance_km} km, max_distance={item.max_distance_km} km, "
                f"score={item.total_score}\n"
            )
        file.write("\nAggregate metrics:\n")
        file.write(f"- venue_count: {len(assignments)}\n")
        file.write(f"- covered_groups: {','.join(used_groups)}\n")
        file.write(f"- mean_assignment_avg_distance_km: {avg_distance:.2f}\n")
        file.write(f"- overall_max_distance_km: {max_distance:.2f}\n")
        file.write(f"- total_assignment_score: {total_score:.2f}\n")
        file.write(f"- total_impact_score: {impact_total:.2f}\n")
        file.write(f"- assignments_with_home_penalty: {home_count}\n")


def write_sensitivity(
    scenario_plans: dict[str, list[CandidateScore]],
    output_path: str | Path,
) -> None:
    fieldnames = [
        "scenario",
        "venue_count",
        "venue_regions",
        "group_pairs",
        "mean_assignment_avg_distance_km",
        "overall_max_distance_km",
        "mean_fairness_score",
        "total_impact_score",
        "total_assignment_score",
        "home_penalty_count",
    ]
    with open(output_path, "w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for scenario, assignments in scenario_plans.items():
            writer.writerow(
                {
                    "scenario": scenario,
                    "venue_count": len(assignments),
                    "venue_regions": "、".join(item.venue_region_name for item in assignments),
                    "group_pairs": "、".join(f"{item.group_a}+{item.group_b}" for item in assignments),
                    "mean_assignment_avg_distance_km": round(
                        sum(item.avg_distance_km for item in assignments) / len(assignments), 2
                    ),
                    "overall_max_distance_km": max(item.max_distance_km for item in assignments),
                    "mean_fairness_score": round(
                        sum(item.fairness_score for item in assignments) / len(assignments), 2
                    ),
                    "total_impact_score": round(sum(item.impact_score for item in assignments), 2),
                    "total_assignment_score": round(sum(item.total_score for item in assignments), 2),
                    "home_penalty_count": sum(1 for item in assignments if item.home_penalty > 0),
                }
            )


def scenario_metrics(assignments: list[CandidateScore]) -> dict[str, float]:
    return {
        "mean_assignment_avg_distance_km": sum(item.avg_distance_km for item in assignments) / len(assignments),
        "overall_max_distance_km": max(item.max_distance_km for item in assignments),
        "mean_fairness_score": sum(item.fairness_score for item in assignments) / len(assignments),
        "total_impact_score": sum(item.impact_score for item in assignments),
    }


def write_typhoon_chart(
    scenario_plans: dict[str, list[CandidateScore]],
    output_path: str | Path,
) -> None:
    """Write a tornado chart comparing scenario metrics to entropy baseline."""
    if "entropy" not in scenario_plans:
        return

    import os

    output_path = Path(output_path)
    mpl_config_dir = output_path.parent / ".matplotlib"
    mpl_config_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(mpl_config_dir))

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    metric_labels = {
        "mean_assignment_avg_distance_km": "Mean avg distance (km)",
        "overall_max_distance_km": "Max distance (km)",
        "mean_fairness_score": "Mean fairness score",
        "total_impact_score": "Total impact score",
    }
    baseline = scenario_metrics(scenario_plans["entropy"])
    scenarios = [name for name in scenario_plans if name != "entropy"]
    colors = {
        "balanced": "#4277b8",
        "travel_first": "#d06b2d",
        "impact_first": "#5b9b66",
    }

    rows = []
    for key, label in metric_labels.items():
        deltas = []
        for scenario in scenarios:
            value = scenario_metrics(scenario_plans[scenario])[key]
            delta_pct = (value - baseline[key]) / baseline[key] * 100.0
            deltas.append((scenario, delta_pct, value))
        max_abs_delta = max(abs(delta) for _, delta, _ in deltas)
        rows.append((max_abs_delta, key, label, deltas))
    rows.sort(reverse=True)

    fig, ax = plt.subplots(figsize=(11.5, 6.8))
    y_tick_positions = []
    y_tick_labels = []
    y = 0
    bar_height = 0.22
    for _, key, label, deltas in rows:
        group_positions = []
        for offset, (scenario, delta, value) in enumerate(deltas):
            y_pos = y + offset * bar_height
            group_positions.append(y_pos)
            ax.barh(
                y_pos,
                delta,
                height=bar_height * 0.82,
                color=colors.get(scenario, "#777777"),
                label=scenario if key == rows[0][1] else None,
            )
            text_x = delta + (0.8 if delta >= 0 else -0.8)
            ha = "left" if delta >= 0 else "right"
            sign = "+" if delta >= 0 else ""
            ax.text(text_x, y_pos, f"{sign}{delta:.1f}% ({value:.2f})", va="center", ha=ha, fontsize=8.5)
        y_tick_positions.append(sum(group_positions) / len(group_positions))
        y_tick_labels.append(f"{label}\nentropy={baseline[key]:.2f}")
        y += 0.94

    ax.axvline(0, color="#222222", linewidth=1.0)
    ax.set_yticks(y_tick_positions)
    ax.set_yticklabels(y_tick_labels, fontsize=9)
    ax.set_xlabel("Percentage change relative to entropy-weighted baseline")
    ax.set_title("Problem 3 Scenario Sensitivity Tornado Chart", fontsize=13, fontweight="bold")
    ax.grid(axis="x", color="#dddddd", linewidth=0.8)
    ax.legend(loc="upper right", frameon=False)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(axis="y", length=0)
    max_abs = max(abs(delta) for _, _, _, deltas in rows for _, delta, _ in deltas)
    ax.set_xlim(-max_abs * 1.25, max_abs * 1.25)
    fig.tight_layout()
    fig.savefig(output_path, dpi=220)
    plt.close(fig)


def assignment_lookup(assignments: list[CandidateScore]) -> dict[str, CandidateScore]:
    lookup: dict[str, CandidateScore] = {}
    for assignment in assignments:
        lookup[assignment.group_a] = assignment
        lookup[assignment.group_b] = assignment
    return lookup


def write_team_distances(
    assignments: list[CandidateScore],
    groups: dict[str, list[Team]],
    output_path: str | Path,
) -> None:
    venues_by_team = {team.team_name: team for group in groups.values() for team in group}
    lookup = assignment_lookup(assignments)
    fieldnames = [
        "group",
        "team_name",
        "parent_city",
        "venue_region",
        "venue_team",
        "distance_km",
        "is_home_venue",
    ]
    with open(output_path, "w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for group_name, teams in groups.items():
            assignment = lookup[group_name]
            venue_team = venues_by_team[assignment.venue_team_name]
            for team in teams:
                distance = haversine_km(team.region.lat, team.region.lon, venue_team.region.lat, venue_team.region.lon)
                writer.writerow(
                    {
                        "group": group_name,
                        "team_name": team.team_name,
                        "parent_city": team.parent_city,
                        "venue_region": assignment.venue_region_name,
                        "venue_team": assignment.venue_team_name,
                        "distance_km": round(distance, 2),
                        "is_home_venue": "yes" if team.team_name == assignment.venue_team_name else "no",
                    }
                )


def write_group_metrics(
    assignments: list[CandidateScore],
    groups: dict[str, list[Team]],
    output_path: str | Path,
) -> None:
    venues_by_team = {team.team_name: team for group in groups.values() for team in group}
    lookup = assignment_lookup(assignments)
    fieldnames = [
        "group",
        "venue_region",
        "venue_team",
        "avg_distance_km",
        "max_distance_km",
        "min_distance_km",
        "home_team_count",
    ]
    with open(output_path, "w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for group_name, teams in groups.items():
            assignment = lookup[group_name]
            venue_team = venues_by_team[assignment.venue_team_name]
            distances = [
                haversine_km(team.region.lat, team.region.lon, venue_team.region.lat, venue_team.region.lon)
                for team in teams
            ]
            writer.writerow(
                {
                    "group": group_name,
                    "venue_region": assignment.venue_region_name,
                    "venue_team": assignment.venue_team_name,
                    "avg_distance_km": round(sum(distances) / len(distances), 2),
                    "max_distance_km": round(max(distances), 2),
                    "min_distance_km": round(min(distances), 2),
                    "home_team_count": sum(1 for team in teams if team.team_name == assignment.venue_team_name),
                }
            )


def write_data_quality_report(output_path: str | Path, regions_by_team: dict[str, Region]) -> None:
    regions = sorted(regions_by_team.values(), key=lambda region: region.region_name)
    missing_capacity = [region.region_name for region in regions if region.stadium_capacity is None]
    missing_stadium = [region.region_name for region in regions if not region.stadium_name.strip()]
    partial_regions = [region.region_name for region in regions if "partial" in region.data_quality]
    in_progress_regions = [region.region_name for region in regions if "在建" in region.data_quality]

    with open(output_path, "w", encoding="utf-8") as file:
        file.write("Problem 3 Data Quality Report\n")
        file.write("=============================\n")
        file.write("Data sources:\n")
        file.write("- 2025 Zhejiang Statistical Yearbook tables (2024 data):\n")
        file.write("   - 17-25: main indicators (population, GDP, fiscal)\n")
        file.write("   - 17-26: year-end population (urban/rural split)\n")
        file.write("   - 17-34: passenger and freight volume\n")
        file.write("   - 17-35: highway mileage, expressway, auto count\n")
        file.write("   - 17-42: culture and health (sports venues, hospitals)\n")
        file.write("- data/raw/problem3_missing_fields_lookup.csv: manually collected\n")
        file.write("  rail station, airport and representative venue fields.\n")
        file.write("- Prefecture-city values aggregated from constituent district rows.\n")
        file.write("- Coordinates: manually curated administrative-center coordinates.\n\n")
        file.write("Quality scope:\n")
        file.write("- Core statistical indicators are quality grade A because they come from\n")
        file.write("  official yearbook tables.\n")
        file.write("- Rail station, airport, stadium name and stadium capacity fields are\n")
        file.write("  auxiliary manual lookup fields. Their row-level status is encoded as\n")
        file.write("  A_core; aux_verified, A_core; aux_partial or A_core; aux_verified(在建).\n\n")
        file.write("Known data gaps:\n")
        file.write("- Urban rail transit (metro) passenger data is missing for Hangzhou, Ningbo,\n")
        file.write("  and Shaoxing in the yearbook because the district-level table does not\n")
        file.write("  separately report metro system statistics. This may understate transport_score\n")
        file.write("  for these cities. Paper should note this limitation.\n")
        file.write("- Blank expressway_km, passenger_volume_10k, rail_transit_passenger_10k\n")
        file.write("  and auto_count values are treated as 0 in the transport composite. For\n")
        file.write("  rail_transit_passenger_10k, this only means the yearbook cell is blank;\n")
        file.write("  it is not interpreted as no passenger rail station.\n")
        file.write(f"- Stadium capacity is still blank for {len(missing_capacity)} regions: ")
        file.write(f"{'、'.join(missing_capacity) or 'none'}.\n")
        file.write(f"- Stadium name is still blank for {len(missing_stadium)} regions: ")
        file.write(f"{'、'.join(missing_stadium) or 'none'}.\n")
        file.write("- Some auxiliary venue records are partial or under construction and should\n")
        file.write("  not be treated as official completed venue-capacity data.\n\n")
        file.write("Score construction:\n")
        file.write("- population_score / gdp_score: log-minmax normalization of raw values.\n")
        file.write("- transport_score: composite of log(road_km), log(expressway_km),\n")
        file.write("  log(passenger_volume), log(rail_passenger), log(auto_count), then minmax.\n")
        file.write("- football_score: composite of absolute venue count (70%) and venue density\n")
        file.write("  per 10k population (30%), then log-minmax normalization. It is a public\n")
        file.write("  sports-atmosphere proxy, not a football-only statistic.\n")
        file.write("- sports_base_score: log-minmax normalization of broad sports venue count;\n")
        file.write("  this is interpreted as public sports infrastructure, not match-ready stadiums.\n")
        file.write("- capacity_score: entropy-weighted composite of sports-base,\n")
        file.write("  stadium-capacity, rail-access and airport-access scores.\n")
        file.write("- Missing stadium capacity or stadium name receives the lowest capacity tier.\n")
        file.write("- partial auxiliary venue records multiply the stadium-capacity subscore by\n")
        file.write("  0.85; in-progress venue records multiply that subscore by 0.75.\n")
        file.write("- Rail access is 0 for no passenger rail, 60 for nearest/limited service,\n")
        file.write("  and 100 for explicit local passenger rail stations.\n")
        file.write("- Airport access follows the conservative distance bands documented in\n")
        file.write("  docs/problem34/problem3_model_notes.md.\n\n")
        file.write("Auxiliary quality flags:\n")
        file.write(f"- partial regions ({len(partial_regions)}): {'、'.join(partial_regions) or 'none'}.\n")
        file.write(f"- in-progress venue regions ({len(in_progress_regions)}): {'、'.join(in_progress_regions) or 'none'}.\n\n")
        file.write("Use in paper:\n")
        file.write("- Cite \"2025年浙江统计年鉴\" as primary data source.\n")
        file.write("- Acknowledge that metro data is missing for Hangzhou/Ningbo/Shaoxing.\n")
        file.write("- Describe rail, airport and representative venue fields as manually\n")
        file.write("  collected public-information supplements, not official yearbook indicators.\n")
        file.write("- Concrete venue capacity is now used in capacity_score, but blank/partial/\n")
        file.write("  in-progress records are conservatively downweighted.\n")


def write_entropy_weights_report(
    output_path: str | Path,
    impact_weights: object,
    capacity_weights: object,
    venue_weights: object,
) -> None:
    with open(output_path, "w", encoding="utf-8") as file:
        file.write("Entropy Weight Method — Computed Weights\n")
        file.write("========================================\n\n")
        file.write("Weights are derived via the Entropy Weight Method (熵权法).\n")
        file.write("For each indicator group, a normalised decision matrix is built from all\n")
        file.write("64 regions (sub-indicator level) or all 7,680 pair-venue combinations\n")
        file.write("(objective level). The entropy of each column is computed, and the\n")
        file.write("information utility d_j = 1 - e_j determines the final weight.\n\n")

        file.write("Impact sub-indicator weights (64-region entropy):\n")
        file.write(f"  population       = {impact_weights.population:.6f}\n")
        file.write(f"  gdp              = {impact_weights.gdp:.6f}\n")
        file.write(f"  transport        = {impact_weights.transport:.6f}\n")
        file.write(f"  sports_atmosphere = {impact_weights.sports_atmosphere:.6f}\n")
        file.write(f"  sum              = {sum(impact_weights.components()):.6f}\n\n")

        file.write("Capacity sub-indicator weights (64-region entropy):\n")
        file.write(f"  sports_base       = {capacity_weights.sports_base:.6f}\n")
        file.write(f"  stadium_capacity  = {capacity_weights.stadium_capacity:.6f}\n")
        file.write(f"  rail_access       = {capacity_weights.rail_access:.6f}\n")
        file.write(f"  airport_access    = {capacity_weights.airport_access:.6f}\n")
        file.write(f"  sum               = {sum(capacity_weights.components()):.6f}\n\n")

        file.write("Objective-level weights (7680 pair-venue entropy):\n")
        file.write(f"  avg_travel    = {venue_weights.avg_travel:.6f}\n")
        file.write(f"  worst_travel  = {venue_weights.worst_travel:.6f}\n")
        file.write(f"  fairness      = {venue_weights.fairness:.6f}\n")
        file.write(f"  impact        = {venue_weights.impact:.6f}\n")
        file.write(f"  capacity      = {venue_weights.capacity:.6f}\n")
        file.write(f"  home_penalty  = {venue_weights.home_penalty:.1f}  (fixed, not entropy-derived)\n")
        file.write(f"  sum           = {sum(venue_weights.objective_weights()):.6f}\n\n")

        file.write("Interpretation:\n")
        file.write("- Higher weight → the indicator varies more across alternatives, carrying\n")
        file.write("  more discriminative information.\n")
        file.write("- Lower weight → the indicator is more uniform across alternatives and\n")
        file.write("  contributes less to differentiating good venues from poor ones.\n")
