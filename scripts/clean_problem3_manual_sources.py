from __future__ import annotations

import argparse
import csv
import math
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_REGION_METRICS = PROJECT_ROOT / "data" / "raw" / "region_metrics.csv"
SOURCE_DIR = PROJECT_ROOT / "data" / "raw" / "problem3_manual_sources"
MISSING_FIELDS_LOOKUP = PROJECT_ROOT / "data" / "raw" / "problem3_missing_fields_lookup.csv"
OUTPUT_PATH = PROJECT_ROOT / "data" / "raw" / "region_metrics.csv"
INSPECTION_REPORT = PROJECT_ROOT / "results" / "problem34" / "problem3_source_inspection.txt"

warnings.filterwarnings("ignore", message="Workbook contains no default style.*")

# Composite-score weights used during data cleaning.  They are kept as named
# constants so the model notes can cite one stable set of assumptions.
TRANSPORT_COMPONENT_WEIGHTS = {
    "road_km": 0.25,
    "expressway_km": 0.20,
    "passenger_volume_10k": 0.20,
    "rail_passenger_10k": 0.20,
    "auto_count": 0.15,
}

SPORTS_ATMOSPHERE_ABSOLUTE_WEIGHT = 0.70
SPORTS_ATMOSPHERE_DENSITY_WEIGHT = 0.30

# ── Administrative division mapping ──────────────────────────────────────────
# Prefecture-level city → list of constituent district names as they appear in the
# yearbook.  County-level cities and counties are matched directly.
CITY_DISTRICTS: dict[str, list[str]] = {
    "杭州": ["上城区", "拱墅区", "西湖区", "滨江区", "萧山区",
             "余杭区", "临平区", "钱塘区", "富阳区", "临安区"],
    "宁波": ["海曙区", "江北区", "北仑区", "镇海区", "鄞州区", "奉化区"],
    "温州": ["鹿城区", "龙湾区", "瓯海区", "洞头区"],
    "嘉兴": ["南湖区", "秀洲区"],
    "湖州": ["吴兴区", "南浔区"],
    "绍兴": ["越城区", "柯桥区", "上虞区"],
    "金华": ["婺城区", "金东区"],
    "衢州": ["柯城区", "衢江区"],
    "舟山": ["定海区", "普陀区"],
    "台州": ["椒江区", "黄岩区", "路桥区"],
    "丽水": ["莲都区"],
}

# Competition region_name → yearbook county-level name (only for mismatches)
YEARBOOK_NAME_LOOKUP: dict[str, str] = {
    "景宁畲族自治县": "景宁县",
}

# Build reverse lookup: competition region_name → its yearbook district names (if city)
def _build_city_lookup() -> dict[str, list[str]]:
    """Return {city_region_name: [district_names_in_yearbook]} for 11 cities."""
    return {f"{city}市": districts for city, districts in CITY_DISTRICTS.items()}

CITY_REGION_TO_DISTRICTS = _build_city_lookup()

# Build set of all district names (for quick "is this a district?" check)
_ALL_DISTRICT_NAMES: set[str] = set()
for _districts in CITY_DISTRICTS.values():
    _ALL_DISTRICT_NAMES.update(_districts)

# ── Excel parsing helpers ────────────────────────────────────────────────────

def _read_clean(path: Path) -> pd.DataFrame:
    """Read an Excel file with no styling, dropping all-NaN rows/cols."""
    df = pd.read_excel(path, header=None, dtype=object, engine="openpyxl")
    return df.dropna(axis=0, how="all").dropna(axis=1, how="all").fillna("")


def _parse_simple_table(path: Path, data_start_row: int) -> dict[str, list[str]]:
    """Parse a yearbook table where data rows start at `data_start_row`.

    Returns {region_name: [col1_value, col2_value, ...]}
    """
    df = _read_clean(path)
    result: dict[str, list[str]] = {}
    for i in range(data_start_row, len(df)):
        name = str(df.iloc[i, 0]).strip()
        if not name or name == "nan" or name.startswith("注"):
            continue
        row = [str(df.iloc[i, j]).strip() for j in range(1, df.shape[1])]
        row = ["" if v == "nan" else v for v in row]
        result[name] = row
    return result


def _safe_float(values: list[str], index: int) -> float:
    """Extract float from values list, returning 0.0 for empty/missing."""
    if index >= len(values):
        return 0.0
    val = values[index]
    if val == "" or val == "nan":
        return 0.0
    try:
        return float(val)
    except ValueError:
        return 0.0


# ── Parse each yearbook table into {name: {field: value}} ────────────────────

@dataclass
class YearbookData:
    """Parsed raw data for a single county-level division."""
    name: str
    population_10k: float          # 年末常住人口（万人）
    gdp_100m: float                # 生产总值（亿元）
    gdp_per_capita: float          # 人均生产总值（元）
    urban_population_10k: float    # 城镇常住人口（万人）
    road_km: float                 # 境内公路里程（公里）
    expressway_km: float           # 高速公路里程（公里）
    passenger_volume_10k: float    # 公路水路客运量（万人）
    rail_passenger_10k: float      # 轨道交通客运量（万人次）
    freight_volume_10k: float      # 公路水路货运量（万吨）
    auto_count: float              # 民用汽车拥有量（辆）
    sports_venue_count: float      # 体育场地数（个，广义体育场地/设施点）

    @classmethod
    def from_yearbook_files(cls) -> dict[str, YearbookData]:
        """Parse all 5 yearbook Excel files, returning {county_name: data}."""
        # 17-25: main indicators (data starts row 3)
        main = _parse_simple_table(
            SOURCE_DIR / "17-25 各市、县国民经济主要指标（2024年）.xlsx", 3)

        # 17-26: population (data starts row 4)
        pop = _parse_simple_table(
            SOURCE_DIR / "17-26 各市、县年末人口数（2024年）.xlsx", 4)

        # 17-34: passenger/freight (data starts row 3)
        freight = _parse_simple_table(
            SOURCE_DIR / "17-34 各市、县客运量和货运量（2024年）.xlsx", 3)

        # 17-35: highway (data starts row 3)
        highway = _parse_simple_table(
            SOURCE_DIR / "17-35 各市、县公路里程邮电通信和用电量情况（2024年）.xlsx", 3)

        # 17-42: culture/health (data starts row 2)
        culture = _parse_simple_table(
            SOURCE_DIR / "17-42 各市、县文化和卫生事业主要指标（2024年）.xlsx", 2)

        all_names = set(main.keys()) | set(pop.keys()) | set(freight.keys()) | set(highway.keys()) | set(culture.keys())
        data: dict[str, YearbookData] = {}

        for name in all_names:
            m = main.get(name, [])
            p = pop.get(name, [])
            f = freight.get(name, [])
            h = highway.get(name, [])
            c = culture.get(name, [])

            data[name] = cls(
                name=name,
                # 17-25: col0=土地面积, col1=年末常住人口, col2=生产总值, col7=人均生产总值
                population_10k=_safe_float(m, 1),
                gdp_100m=_safe_float(m, 2),
                gdp_per_capita=_safe_float(m, 7),
                # 17-26: col0=常住人口, col1=城镇常住人口
                urban_population_10k=_safe_float(p, 1),
                # 17-34: col0=客运量公路水路, col1=轨道交通, col2=货运量
                passenger_volume_10k=_safe_float(f, 0),
                rail_passenger_10k=_safe_float(f, 1),
                freight_volume_10k=_safe_float(f, 2),
                # 17-35: col0=境内公路里程, col1=高速, col2=民用汽车
                road_km=_safe_float(h, 0),
                expressway_km=_safe_float(h, 1),
                auto_count=_safe_float(h, 2),
                # 17-42: col0=体育场地数
                sports_venue_count=_safe_float(c, 0),
            )

        return data


# ── Aggregate city data ──────────────────────────────────────────────────────

def aggregate_city(district_names: list[str], yearbook: dict[str, YearbookData]) -> YearbookData:
    """Sum district-level numeric values to create a prefecture-city row."""
    districts = [yearbook[name] for name in district_names if name in yearbook]
    if not districts:
        raise ValueError(f"No yearbook data found for districts: {district_names}")

    total_pop = sum(d.population_10k for d in districts)
    total_gdp = sum(d.gdp_100m for d in districts)

    return YearbookData(
        name="",
        population_10k=total_pop,
        gdp_100m=total_gdp,
        gdp_per_capita=(total_gdp * 1e8) / (total_pop * 1e4) if total_pop > 0 else 0,
        urban_population_10k=sum(d.urban_population_10k for d in districts),
        road_km=sum(d.road_km for d in districts),
        expressway_km=sum(d.expressway_km for d in districts),
        passenger_volume_10k=sum(d.passenger_volume_10k for d in districts),
        rail_passenger_10k=sum(d.rail_passenger_10k for d in districts),
        freight_volume_10k=sum(d.freight_volume_10k for d in districts),
        auto_count=sum(d.auto_count for d in districts),
        sports_venue_count=sum(d.sports_venue_count for d in districts),
    )


# ── Map 64 competition regions to yearbook data ──────────────────────────────

def resolve_yearbook_name(region_name: str) -> str:
    """Map a competition region_name to its yearbook name."""
    return YEARBOOK_NAME_LOOKUP.get(region_name, region_name)


def build_region_data(
    regions: list[dict],
    yearbook: dict[str, YearbookData],
) -> dict[str, YearbookData]:
    """For each of the 64 competition regions, produce a YearbookData row.

    Cities are aggregated from their constituent districts.
    Counties are looked up directly (with alias handling).
    """
    result: dict[str, YearbookData] = {}
    missing: list[str] = []

    for row in regions:
        name = row["region_name"]
        parent = row["parent_city"]

        if name in CITY_REGION_TO_DISTRICTS:
            # Prefecture city → aggregate districts
            district_names = CITY_REGION_TO_DISTRICTS[name]
            result[name] = aggregate_city(district_names, yearbook)
        else:
            # County / county-level city → direct lookup
            yb_name = resolve_yearbook_name(name)
            if yb_name in yearbook:
                data = yearbook[yb_name]
                result[name] = YearbookData(
                    name=name,
                    population_10k=data.population_10k,
                    gdp_100m=data.gdp_100m,
                    gdp_per_capita=data.gdp_per_capita,
                    urban_population_10k=data.urban_population_10k,
                    road_km=data.road_km,
                    expressway_km=data.expressway_km,
                    passenger_volume_10k=data.passenger_volume_10k,
                    rail_passenger_10k=data.rail_passenger_10k,
                    freight_volume_10k=data.freight_volume_10k,
                    auto_count=data.auto_count,
                    sports_venue_count=data.sports_venue_count,
                )
            else:
                missing.append(f"{name} (looked for '{yb_name}')")

    if missing:
        raise ValueError(f"Missing yearbook data for: {', '.join(missing)}")

    return result


# ── Score normalization ──────────────────────────────────────────────────────

def minmax_1to5(values: list[float]) -> list[float]:
    """Normalize a list of values to [1, 5] range using min-max scaling."""
    vmin = min(values)
    vmax = max(values)
    if vmax == vmin:
        return [3.0] * len(values)
    return [round(1.0 + (v - vmin) / (vmax - vmin) * 4.0, 4) for v in values]


def logminmax_1to5(values: list[float]) -> list[float]:
    """Normalize via log1p → min-max to [1, 5]. Handles extreme skew better."""
    logged = [math.log1p(v) for v in values]
    return minmax_1to5(logged)


def compute_transport_composite(data: YearbookData) -> float:
    """Compute a raw transport composite value from multiple indicators.

    Uses log-transformed components to avoid extreme skew from 杭州市.
    """
    return (
        math.log1p(data.road_km) * TRANSPORT_COMPONENT_WEIGHTS["road_km"]
        + math.log1p(data.expressway_km) * TRANSPORT_COMPONENT_WEIGHTS["expressway_km"]
        + math.log1p(data.passenger_volume_10k) * TRANSPORT_COMPONENT_WEIGHTS["passenger_volume_10k"]
        + math.log1p(data.rail_passenger_10k) * TRANSPORT_COMPONENT_WEIGHTS["rail_passenger_10k"]
        + math.log1p(data.auto_count) * TRANSPORT_COMPONENT_WEIGHTS["auto_count"]
    )


def compute_scores(region_data: dict[str, YearbookData]) -> dict[str, dict[str, float]]:
    """Compute normalized 1-5 scores for population, GDP, transport and sports base."""
    names = list(region_data.keys())

    # Raw values
    pop_raw = [region_data[n].population_10k for n in names]
    gdp_raw = [region_data[n].gdp_100m for n in names]
    transport_raw = [compute_transport_composite(region_data[n]) for n in names]
    sports_raw = [region_data[n].sports_venue_count for n in names]

    # sports_venue_count is a broad public-sports infrastructure measure, not
    # the number of match-ready stadiums.  The composite below is therefore used
    # only as a sports-atmosphere proxy: absolute scale plus per-capita density.
    football_raw = []
    for n in names:
        d = region_data[n]
        pop = d.population_10k if d.population_10k > 0 else 1
        raw_abs = d.sports_venue_count
        raw_density = d.sports_venue_count / pop
        football_raw.append(
            raw_abs * SPORTS_ATMOSPHERE_ABSOLUTE_WEIGHT
            + raw_density * 10.0 * SPORTS_ATMOSPHERE_DENSITY_WEIGHT
        )

    # Normalize to 1-5 — log-minmax for heavily skewed raw metrics,
    # linear minmax for transport (components already log-transformed).
    pop_score = logminmax_1to5(pop_raw)
    gdp_score = logminmax_1to5(gdp_raw)
    transport_score = minmax_1to5(transport_raw)
    football_score = logminmax_1to5(football_raw)
    sports_base_score = logminmax_1to5(sports_raw)

    result: dict[str, dict[str, float]] = {}
    for i, name in enumerate(names):
        result[name] = {
            "population_score": pop_score[i],
            "gdp_score": gdp_score[i],
            "transport_score": transport_score[i],
            "football_score": football_score[i],
            "sports_base_score": sports_base_score[i],
        }
    return result


# ── Main pipeline ────────────────────────────────────────────────────────────

SOURCE_URL = "https://zjjcmspublicnew.oss-cn-hangzhou-zwynet-d01-a.internet.cloud.zj.gov.cn/cms_files/jcms1/web3077/site/flash/tjj/Reports1/2025%E6%B5%99%E6%B1%9F%E7%BB%9F%E8%AE%A1%E5%B9%B4%E9%89%B4/indexcn.html"
DATA_YEAR = 2024


def load_existing_regions(path: Path) -> list[dict]:
    """Read the existing region_metrics.csv, returning rows as dicts."""
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def clean_lookup_value(value: str) -> str:
    """Normalize lookup placeholders while preserving meaningful text."""
    value = (value or "").strip()
    return "" if value == "-" else value


def load_missing_field_lookup(path: Path, expected_regions: list[str]) -> dict[str, dict[str, str]]:
    """Load optional manually collected rail/airport/stadium fields."""
    if not path.exists():
        return {}

    required_columns = {
        "region_name",
        "has_rail_station",
        "nearest_airport",
        "nearest_airport_km",
        "stadium_name",
        "stadium_capacity",
        "data_quality",
        "notes",
    }
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing_columns = required_columns - set(reader.fieldnames or [])
        if missing_columns:
            raise ValueError(f"lookup missing columns: {sorted(missing_columns)}")
        rows = list(reader)

    lookup_names = [row["region_name"] for row in rows]
    duplicates = sorted(name for name in set(lookup_names) if lookup_names.count(name) > 1)
    if duplicates:
        raise ValueError(f"duplicate regions in lookup: {duplicates}")

    expected = set(expected_regions)
    actual = set(lookup_names)
    missing_regions = sorted(expected - actual)
    extra_regions = sorted(actual - expected)
    if missing_regions or extra_regions:
        raise ValueError(
            "lookup region mismatch: "
            f"missing={missing_regions}, extra={extra_regions}"
        )

    return {row["region_name"]: row for row in rows}


def merged_quality(auxiliary: dict[str, str] | None) -> str:
    """Preserve official core-data quality while recording auxiliary quality."""
    if not auxiliary:
        return "A_core"
    quality = clean_lookup_value(auxiliary.get("data_quality", ""))
    return f"A_core; aux_{quality}" if quality else "A_core"


def merged_notes(auxiliary: dict[str, str] | None) -> str:
    """Build a compact note that distinguishes official and auxiliary fields."""
    parts = [
        "A-grade yearbook core indicators",
        "rail/airport/stadium fields from manual lookup",
    ]
    if auxiliary:
        quality = clean_lookup_value(auxiliary.get("data_quality", ""))
        note = clean_lookup_value(auxiliary.get("notes", ""))
        if quality:
            parts.append(f"aux_quality={quality}")
        if note:
            parts.append(note)
    else:
        parts.append("aux fields pending")
    return "; ".join(parts)


def clean(output_path: Path | None = None) -> None:
    """Main cleaning pipeline: parse yearbook data, compute scores, write CSV."""
    output_path = output_path or OUTPUT_PATH

    print("=== Problem 3: Cleaning yearbook data ===\n")

    # 1. Parse all yearbook Excel files
    print("1. Parsing 5 yearbook Excel files...")
    yearbook = YearbookData.from_yearbook_files()
    print(f"   Parsed {len(yearbook)} county-level divisions")

    # 2. Load existing 64 competition regions
    print("2. Loading existing 64 competition regions...")
    existing = load_existing_regions(RAW_REGION_METRICS)
    print(f"   Found {len(existing)} regions")

    # 3. Load optional manually collected missing fields.
    print("3. Loading optional rail/airport/stadium lookup...")
    lookup = load_missing_field_lookup(
        MISSING_FIELDS_LOOKUP,
        [row["region_name"] for row in existing],
    )
    if lookup:
        print(f"   Loaded lookup rows for {len(lookup)} regions")
    else:
        print("   Lookup file not found; auxiliary fields will remain blank")

    # 4. Map each competition region to yearbook data (aggregating cities)
    print("4. Mapping competition regions to yearbook data...")
    region_data = build_region_data(existing, yearbook)
    print(f"   Mapped {len(region_data)} regions")

    # 5. Compute normalized scores
    print("5. Computing normalized 1-5 scores from raw data...")
    scores = compute_scores(region_data)

    # 6. Write enriched CSV
    print(f"6. Writing enriched region_metrics.csv → {output_path}")
    fieldnames = [
        "region_name", "team_name", "level", "parent_city", "lat", "lon",
        "population_10k", "gdp_100m", "urban_population_10k", "gdp_per_capita",
        "road_km", "expressway_km", "passenger_volume_10k", "rail_transit_passenger_10k",
        "auto_count", "sports_venue_count",
        "has_rail_station", "nearest_airport", "nearest_airport_km",
        "stadium_name", "stadium_capacity",
        "population_score", "gdp_score", "transport_score", "football_score", "sports_base_score",
        "data_year", "source_url", "data_quality", "notes",
    ]

    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in existing:
            name = row["region_name"]
            d = region_data[name]
            s = scores[name]
            auxiliary = lookup.get(name)

            writer.writerow({
                "region_name": row["region_name"],
                "team_name": row["team_name"],
                "level": row["level"],
                "parent_city": row["parent_city"],
                "lat": row["lat"],
                "lon": row["lon"],
                "population_10k": d.population_10k,
                "gdp_100m": d.gdp_100m,
                "urban_population_10k": d.urban_population_10k,
                "gdp_per_capita": round(d.gdp_per_capita, 0) if d.gdp_per_capita > 0 else "",
                "road_km": d.road_km if d.road_km > 0 else "",
                "expressway_km": d.expressway_km if d.expressway_km > 0 else "",
                "passenger_volume_10k": d.passenger_volume_10k if d.passenger_volume_10k > 0 else "",
                "rail_transit_passenger_10k": d.rail_passenger_10k if d.rail_passenger_10k > 0 else "",
                "auto_count": d.auto_count if d.auto_count > 0 else "",
                "sports_venue_count": int(d.sports_venue_count) if d.sports_venue_count > 0 else "",
                "has_rail_station": clean_lookup_value(auxiliary.get("has_rail_station", "")) if auxiliary else "",
                "nearest_airport": clean_lookup_value(auxiliary.get("nearest_airport", "")) if auxiliary else "",
                "nearest_airport_km": clean_lookup_value(auxiliary.get("nearest_airport_km", "")) if auxiliary else "",
                "stadium_name": clean_lookup_value(auxiliary.get("stadium_name", "")) if auxiliary else "",
                "stadium_capacity": clean_lookup_value(auxiliary.get("stadium_capacity", "")) if auxiliary else "",
                "population_score": s["population_score"],
                "gdp_score": s["gdp_score"],
                "transport_score": s["transport_score"],
                "football_score": s["football_score"],
                "sports_base_score": s["sports_base_score"],
                "data_year": DATA_YEAR,
                "source_url": SOURCE_URL,
                "data_quality": merged_quality(auxiliary),
                "notes": merged_notes(auxiliary),
            })

    # 6. Print summary statistics
    print("\n=== Summary ===")
    print(f"Regions: {len(existing)}")
    pop_scores = [scores[r["region_name"]]["population_score"] for r in existing]
    gdp_scores = [scores[r["region_name"]]["gdp_score"] for r in existing]
    tr_scores = [scores[r["region_name"]]["transport_score"] for r in existing]
    fb_scores = [scores[r["region_name"]]["football_score"] for r in existing]

    print(f"Population score: {min(pop_scores):.2f} – {max(pop_scores):.2f} (mean {np.mean(pop_scores):.2f})")
    print(f"GDP score:        {min(gdp_scores):.2f} – {max(gdp_scores):.2f} (mean {np.mean(gdp_scores):.2f})")
    print(f"Transport score:  {min(tr_scores):.2f} – {max(tr_scores):.2f} (mean {np.mean(tr_scores):.2f})")
    print(f"Football score:   {min(fb_scores):.2f} – {max(fb_scores):.2f} (mean {np.mean(fb_scores):.2f})")

    # Top 5 by transport
    print("\nTop 10 by transport_score:")
    ranked = sorted(existing, key=lambda r: scores[r["region_name"]]["transport_score"], reverse=True)
    for i, r in enumerate(ranked[:10], 1):
        d = region_data[r["region_name"]]
        s = scores[r["region_name"]]
        print(f"  {i}. {r['region_name']}: transport={s['transport_score']:.2f}, "
              f"road={d.road_km:.0f}km, highway={d.expressway_km:.0f}km, "
              f"pax={d.passenger_volume_10k:.0f}万, rail={d.rail_passenger_10k:.0f}万")

    print("\nDone.")


# ── Inspection (already existing, kept for backward compat) ──────────────────

def read_xlsx_frame(path: Path) -> pd.DataFrame:
    frame = pd.read_excel(path, header=None, dtype=object, engine="openpyxl")
    return frame.dropna(axis=0, how="all").dropna(axis=1, how="all").fillna("")


def compact_row(row: list[object]) -> list[object]:
    end = len(row)
    while end > 0 and row[end - 1] == "":
        end -= 1
    return row[:end]


def row_text(row: list[object], max_items: int = 8) -> str:
    values = [str(value).strip().replace("\n", " ") for value in compact_row(row)]
    return " | ".join(values[:max_items])


def detect_header_rows(frame: pd.DataFrame) -> list[str]:
    header_rows: list[str] = []
    for row in frame.head(5).values.tolist():
        text = row_text(row)
        if "市县名称" in text or "常住人口" in text or "公路" in text or "体育场地" in text:
            header_rows.append(text)
    return header_rows[:3]


def inspect_sources(report_path: Path = INSPECTION_REPORT) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_lines: list[str] = []
    stdout_lines = ["Problem 3 source inspection:"]

    files = [
        ("main", "17-25 各市、县国民经济主要指标（2024年）.xlsx", "17-25 各市、县国民经济主要指标（2024年）"),
        ("population", "17-26 各市、县年末人口数（2024年）.xlsx", "17-26 各市、县年末人口数（2024年）"),
        ("freight", "17-34 各市、县客运量和货运量（2024年）.xlsx", "17-34 各市、县客运量和货运量（2024年）"),
        ("highway", "17-35 各市、县公路里程邮电通信和用电量情况（2024年）.xlsx", "17-35 各市、县公路里程邮电通信和用电量情况（2024年）"),
        ("culture_health", "17-42 各市、县文化和卫生事业主要指标（2024年）.xlsx", "17-42 各市、县文化和卫生事业主要指标（2024年）"),
    ]

    for key, fname, title in files:
        path = SOURCE_DIR / fname
        if not path.exists():
            stdout_lines.append(f"- {key}: missing")
            report_lines.extend([f"## {title}", f"MISSING: {path}", ""])
            continue

        frame = read_xlsx_frame(path)
        header_rows = detect_header_rows(frame)
        stdout_lines.append(
            f"- {key}: {frame.shape[0]} rows x {frame.shape[1]} cols; headers={len(header_rows)}"
        )
        report_lines.extend([
            f"## {title}", f"path: {path}",
            f"shape: {frame.shape[0]} rows x {frame.shape[1]} cols",
            "detected headers:",
        ])
        report_lines.extend(f"- {line}" for line in header_rows)
        report_lines.append("")

    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    print("\n".join(stdout_lines))
    print(f"Detailed report: {report_path}")


# ── CLI ──────────────────────────────────────────────────────────────────────

def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Clean Zhejiang yearbook manual sources for Problem 3."
    )
    parser.add_argument("--inspect", action="store_true",
                       help="Print a compact source summary and write details to a report file.")
    parser.add_argument("--inspection-report", type=Path, default=INSPECTION_REPORT,
                       help="Path for the detailed inspection report.")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH,
                       help="Path for the cleaned region_metrics.csv.")
    parser.add_argument("--dry-run", action="store_true",
                       help="Validate all mappings without writing output.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)

    if args.inspect:
        inspect_sources(args.inspection_report)
        return 0

    if args.dry_run:
        print("Dry run: verifying yearbook data parsing and region mapping...")
        yearbook = YearbookData.from_yearbook_files()
        print(f"Parsed {len(yearbook)} county-level divisions from yearbook")

        existing = load_existing_regions(RAW_REGION_METRICS)
        print(f"Loaded {len(existing)} competition regions")

        region_data = build_region_data(existing, yearbook)
        print(f"Successfully mapped all {len(region_data)} regions")

        scores = compute_scores(region_data)
        for row in existing:
            name = row["region_name"]
            s = scores[name]
            d = region_data[name]
            print(f"  {name}: pop={d.population_10k:.1f}万 gdp={d.gdp_100m:.0f}亿 "
                  f"road={d.road_km:.0f}km hw={d.expressway_km:.0f}km "
                  f"pax={d.passenger_volume_10k:.0f}万 rail={d.rail_passenger_10k:.0f}万 "
                  f"venues={d.sports_venue_count:.0f} "
                  f"→ P{s['population_score']:.1f} G{s['gdp_score']:.1f} "
                  f"T{s['transport_score']:.1f} F{s['football_score']:.1f}")
        return 0

    clean(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
