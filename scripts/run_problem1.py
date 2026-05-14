from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from problem1.pipeline import search_solutions, write_groups_csv, write_metrics_csv, write_summary


def main() -> None:
    data_path = PROJECT_ROOT / "data" / "raw" / "teams.csv"
    output_dir = PROJECT_ROOT / "results" / "problem1"
    output_dir.mkdir(parents=True, exist_ok=True)

    solutions = search_solutions(data_path, trials=500)
    if not solutions:
        raise RuntimeError("No feasible grouping solution found. Try increasing trials.")

    best_solution = solutions[0]
    write_groups_csv(best_solution.groups, output_dir / "best_groups.csv")
    write_metrics_csv(solutions, output_dir / "all_scores.csv")
    write_summary(solutions, output_dir / "summary.txt")

    print("Problem 1 pipeline finished.")
    print(f"Feasible solutions found: {len(solutions)}")
    print("Best metrics:")
    for key, value in best_solution.metrics.items():
        print(f"  {key}: {value}")
    print(f"Results saved to: {output_dir}")


if __name__ == "__main__":
    main()
