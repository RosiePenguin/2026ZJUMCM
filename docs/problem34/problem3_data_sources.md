# 问题 3 数据源与替换计划

## 官方来源优先级

1. 浙江省统计局：浙江省 2024 年国民经济和社会发展统计公报。
2. 浙江省统计局：2024 年浙江省人口主要数据公报。
3. 浙江省统计年鉴县市表：用于替换 64 个参赛地区的人口和 GDP 明细。
4. 浙江省交通运输厅：2024 年 1-12 月全省交通经济运行主要指标表。
5. 各市县统计公报、交通运输和体育主管部门公开信息：补充县市级人口、GDP、交通枢纽和体育场馆数据。

## 当前实现状态

当前 `data/raw/region_metrics.csv` 已完成第一轮官方统计数据替换和人工补充字段合并，从 10 列扩展为 30 列。已由 2025 年浙江统计年鉴的 2024 年县市表提取或聚合得到：

- 常住人口：`population_10k`
- 生产总值：`gdp_100m`
- 交通统计：`road_km`、`expressway_km`、`passenger_volume_10k`、`rail_transit_passenger_10k`、`auto_count`
- 体育基础：`sports_venue_count`。该字段为年鉴中的广义体育场地/设施点数量，用于刻画体育基础和群众体育氛围，不解释为大型比赛场馆数量。
- 模型评分：`population_score`、`gdp_score`、`transport_score`、`football_score`、`sports_base_score`

其中 `population_score`、`gdp_score`、`transport_score`、`football_score` 和 `sports_base_score` 已由官方统计指标归一化得到，不再是最初的手工代理等级。当前模型读取 `sports_base_score`，并仅将其作为承办能力的辅助项；具体承办能力主要由代表性场馆容量和交通可达性刻画。

已由 `data/raw/problem3_missing_fields_lookup.csv` 人工补充：

- 铁路客运站可达性：`has_rail_station`
- 机场可达性：`nearest_airport`、`nearest_airport_km`
- 具体承办场馆：`stadium_name`、`stadium_capacity`

因此，当前版本可作为“官方统计数据 + 人工公开资料补充”的可复现版本。需要注意的是，人工补充字段不是统一官方年鉴口径，部分记录仍为 `partial` 或 `verified(在建)`。具体场馆容量、铁路可达性和机场可达性已经进入承办能力评分，但缺失或不完整记录采用保守降权。

人工下载与补录步骤见 `docs/problem34/problem3_manual_data_collection_plan.md`。

## 后续补强字段

后续可继续把 `region_metrics.csv` 补充为：

```text
region_name,team_name,level,parent_city,lat,lon,
population_10k,gdp_100m,
road_km,expressway_km,passenger_volume_10k,rail_transit_passenger_10k,auto_count,
sports_venue_count,has_rail_station,nearest_airport,nearest_airport_km,
stadium_name,stadium_capacity,
population_score,gdp_score,transport_score,football_score,sports_base_score,
data_year,source_url,data_quality,notes
```

后续若继续补齐剩余容量字段，只需更新 `problem3_missing_fields_lookup.csv` 并重跑清洗和模型。小组配对、场地唯一性、敏感性分析和距离明细输出不需要重写。

## 建议引用链接

- 浙江省 2024 年国民经济和社会发展统计公报：`https://tjj.zj.gov.cn/art/2025/3/1/art_1229129205_5469690.html`
- 2024 年浙江省人口主要数据公报：`https://tjj.zj.gov.cn/art/2025/3/1/art_1229129205_5469687.html`
- 2024 年 1-12 月全省交通经济运行主要指标表：`https://jtyst.zj.gov.cn/art/2025/3/12/art_1229248362_5474290.html`
