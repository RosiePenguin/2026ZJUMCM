from __future__ import annotations

import shutil
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
SUBMISSION_DIR = ROOT / "submission"
PACKAGE_DIR = SUBMISSION_DIR / "B题支撑材料"
ZIP_PATH = SUBMISSION_DIR / "B题支撑材料.zip"


INCLUDE_PATHS = [
    Path("requirements.txt"),
    Path("src/problem1"),
    Path("src/problem2"),
    Path("src/problem34"),
    Path("scripts/run_problem1.py"),
    Path("scripts/run_problem2.py"),
    Path("scripts/run_problem34.py"),
    Path("scripts/clean_problem3_manual_sources.py"),
    Path("data/raw/teams.csv"),
    Path("data/raw/region_metrics.csv"),
    Path("data/raw/problem3_missing_fields_lookup.csv"),
    Path("data/raw/problem3_manual_sources"),
    Path("results/problem1"),
    Path("results/problem2"),
    Path("results/problem34"),
    Path("docs/AI工具使用说明.md"),
    Path("docs/附录与支撑材料清单.md"),
    Path("docs/problem34/problem3_data_sources.md"),
    Path("docs/problem34/problem3_data_cleaning_report.md"),
    Path("docs/problem34/problem3_model_notes.md"),
    Path("docs/problem34/problem4_model_notes.md"),
]


def write_readme(target_root: Path) -> None:
    text = """# B题支撑材料运行说明

本压缩包用于与论文正文 PDF 一同提交，目标是让评阅人可以直接查看源程序、运行命令、关键结果和自主查阅的数据资料。

## 1. 软件环境

- 操作系统：Windows 10/11
- Python：3.10 或 3.11
- 依赖安装：

```powershell
python -m venv .venv
.\\.venv\\Scripts\\activate
pip install -r requirements.txt
```

`requirements.txt` 中包含：

- `numpy>=1.24`
- `scipy>=1.10`
- `matplotlib>=3.9`

## 2. 运行命令

建议在本文件所在目录打开 PowerShell，按下面顺序运行：

```powershell
python scripts/run_problem1.py
python scripts/run_problem2.py
python scripts/run_problem34.py
```

如需重新清洗问题 3 的人工数据，可运行：

```powershell
python scripts/clean_problem3_manual_sources.py
```

## 3. 文件结构说明

- `src/`：全部核心源程序代码
- `scripts/`：运行脚本与数据清洗脚本
- `data/raw/`：运行所需结构化输入文件与自主查阅整理的数据
- `results/`：论文中使用的关键输出结果
- `docs/`：AI 工具使用说明、数据来源说明、附录与支撑材料清单

## 4. 关于数据文件

- `region_metrics.csv`、`problem3_missing_fields_lookup.csv` 和 `problem3_manual_sources/` 下的 Excel 文件属于自主查阅、整理和清洗后的数据资料，应放入支撑材料。
- `teams.csv` 是根据题面给出的参赛队伍信息整理得到的结构化输入文件，程序运行需要该文件。
- 赛题原始 PDF 与学校封面文件不放入本压缩包。

## 5. 关键结果文件

### 问题 1

- `results/problem1/best_groups.csv`
- `results/problem1/all_scores.csv`
- `results/problem1/summary.txt`

### 问题 2

- `results/problem2/summary.md`
- `results/problem2/draw_example.png`
- `results/problem2/fairness_analysis.png`

### 问题 3 与问题 4

- `results/problem34/problem3_venue_assignments.csv`
- `results/problem34/problem3_summary.txt`
- `results/problem34/problem3_typhoon_sensitivity.png`
- `results/problem34/problem4_format_comparison.csv`
- `results/problem34/problem4_format_comparison.png`
- `results/problem34/problem4_summary.txt`

## 6. 可运行性说明

本队已按以下入口脚本组织程序：

- `scripts/run_problem1.py`
- `scripts/run_problem2.py`
- `scripts/run_problem34.py`

评阅人安装依赖后，可直接运行上述脚本复现实验结果。

## 7. AI 使用说明

若需要核对 AI 使用情况，请查看：

- `docs/AI工具使用说明.md`
"""
    (target_root / "README_支撑材料运行说明.md").write_text(text, encoding="utf-8")


def write_run_scripts(target_root: Path) -> None:
    ps1 = """$ErrorActionPreference = 'Stop'
python -m venv .venv
.\\.venv\\Scripts\\activate
pip install -r requirements.txt
python scripts/run_problem1.py
python scripts/run_problem2.py
python scripts/run_problem34.py
"""
    bat = """@echo off
python -m venv .venv
call .\\.venv\\Scripts\\activate
pip install -r requirements.txt
python scripts\\run_problem1.py
python scripts\\run_problem2.py
python scripts\\run_problem34.py
pause
"""
    (target_root / "run_all_windows.ps1").write_text(ps1, encoding="utf-8")
    (target_root / "run_all_windows.bat").write_text(bat, encoding="utf-8")


def copy_path(relative_path: Path, target_root: Path) -> None:
    src = ROOT / relative_path
    dst = target_root / relative_path
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def remove_noise(target_root: Path) -> None:
    for path in target_root.rglob("__pycache__"):
        shutil.rmtree(path, ignore_errors=True)
    for path in target_root.rglob(".matplotlib"):
        shutil.rmtree(path, ignore_errors=True)
    for path in target_root.rglob("*.pyc"):
        path.unlink(missing_ok=True)
    for name in [".gitkeep"]:
        for path in target_root.rglob(name):
            path.unlink(missing_ok=True)


def zip_dir(source_dir: Path, zip_path: Path) -> None:
    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as zf:
        for file in sorted(source_dir.rglob("*")):
            if file.is_file():
                zf.write(file, file.relative_to(source_dir.parent))


def main() -> None:
    if PACKAGE_DIR.exists():
        shutil.rmtree(PACKAGE_DIR)
    PACKAGE_DIR.mkdir(parents=True, exist_ok=True)

    for rel in INCLUDE_PATHS:
        copy_path(rel, PACKAGE_DIR)

    write_readme(PACKAGE_DIR)
    write_run_scripts(PACKAGE_DIR)
    remove_noise(PACKAGE_DIR)

    ZIP_PATH.parent.mkdir(parents=True, exist_ok=True)
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    zip_dir(PACKAGE_DIR, ZIP_PATH)
    print(ZIP_PATH)


if __name__ == "__main__":
    main()
