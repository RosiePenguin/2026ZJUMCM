from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from problem34.pipeline import run_problem3, run_problem4


def main() -> None:
    output_dir = PROJECT_ROOT / "results" / "problem34"
    assignments = run_problem3(
        region_metrics_path=PROJECT_ROOT / "data" / "raw" / "region_metrics.csv",
        best_groups_path=PROJECT_ROOT / "results" / "problem1" / "best_groups.csv",
        output_dir=output_dir,
    )

    print("Problem 3 venue selection finished.")
    print(f"Recommended venues: {len(assignments)}")
    for item in assignments:
        print(f"  {item.venue_region_name}: {item.group_a}+{item.group_b}, score={item.total_score}")

    summaries, _ = run_problem4(
        region_metrics_path=PROJECT_ROOT / "data" / "raw" / "region_metrics.csv",
        best_groups_path=PROJECT_ROOT / "results" / "problem1" / "best_groups.csv",
        team_distances_path=output_dir / "problem3_team_distances.csv",
        output_dir=output_dir,
    )
    print("Problem 4 competition format simulation finished.")
    for item in summaries:
        print(
            f"  {item.format_name}: priority_topsis_score={item.priority_topsis_score}, "
            f"top8_qf={item.top8_quarterfinal_rate}"
        )
    print(f"Results saved to: {output_dir}")


if __name__ == "__main__":
    main()
