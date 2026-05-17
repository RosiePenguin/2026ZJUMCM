from __future__ import annotations

import math


def calculate_entropy(items: list[str]) -> float:
    total = len(items)
    if total == 0:
        return 0.0

    counts: dict[str, int] = {}
    for item in items:
        counts[item] = counts.get(item, 0) + 1

    entropy = 0.0
    for count in counts.values():
        p = count / total
        entropy -= p * math.log(p, 2)
    return entropy


def evaluate_groups(groups: dict[str, list[dict]]) -> dict[str, float]:
    soft_conflict_pairs = 0
    group_entropies: list[float] = []
    group_strengths: list[float] = []

    for members in groups.values():
        county_cities = [member["parent_city"] for member in members if member["level"] == "county"]
        city_counts: dict[str, int] = {}
        for city in county_cities:
            city_counts[city] = city_counts.get(city, 0) + 1
        soft_conflict_pairs += sum(count * (count - 1) // 2 for count in city_counts.values())

        all_cities = [member["parent_city"] for member in members]
        group_entropies.append(calculate_entropy(all_cities))
        group_strengths.append(sum(member["strength"] for member in members))

    mean_strength = sum(group_strengths) / len(group_strengths)
    variance = sum((x - mean_strength) ** 2 for x in group_strengths) / len(group_strengths)
    strength_balance_std = variance ** 0.5

    avg_city_entropy = sum(group_entropies) / len(group_entropies)
    final_score = avg_city_entropy * 100 - soft_conflict_pairs * 15 - strength_balance_std * 2

    return {
        "soft_conflict_pairs": float(soft_conflict_pairs),
        "avg_city_entropy": round(avg_city_entropy, 4),
        "strength_balance_std": round(strength_balance_std, 4),
        "final_score": round(final_score, 4),
    }
