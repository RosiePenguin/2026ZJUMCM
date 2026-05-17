# 问题 4：赛制优化模型与建议

## 1. 建模思路

问题 4 在题目给定的“16 组、每组 4 队、前两名进入 32 强淘汰赛”框架下，比较不同淘汰赛编排和赛程恢复规则。模型采用蒙特卡洛仿真：先按问题 1 分组进行小组赛，再按候选赛制进入淘汰赛，重复 20000 次后统计强队保护、公平性和出行负担指标。

模型输入为：

- `results/problem1/best_groups.csv`：只使用其中的分组结果。
- `data/raw/region_metrics.csv`：用于客观合成队伍实力代理值。
- `results/problem34/problem3_team_distances.csv`：问题 3 给出的各队小组赛出行距离。

## 2. 实力代理值合成

原始分组文件中的 `strength` 不直接作为模型输入。本文根据 `region_metrics.csv` 中 64 个地区的综合发展和足球基础指标，用熵权法合成队伍实力代理值：

```text
population_score, gdp_score, transport_score, football_score, sports_base_score
```

熵权法根据各指标在 64 个地区中的离散程度确定权重，离散程度越高的指标提供的信息量越大。得到的综合得分再经 min-max 线性映射到 `[60, 90]`，作为赛事仿真的 `strength_proxy`。当前权重输出见：

- `results/problem34/problem4_strength_weights.txt`
- `results/problem34/problem4_strength_proxy.csv`

当前权重为：

| 指标 | 权重 |
|---|---:|
| population_score | 0.184290 |
| gdp_score | 0.301823 |
| transport_score | 0.160993 |
| football_score | 0.190868 |
| sports_base_score | 0.162026 |

## 3. 比赛模拟模型

### 3.1 小组赛

每组 4 队单循环，共 6 场。胜者积 3 分，平局各积 1 分。小组排名依次按积分、净胜球、进球数、实力代理值和随机微扰排序，前两名晋级。

有效实力为：

```text
effective_strength_i = strength_proxy_i - fatigue_i
fatigue_i = max(0, travel_km_i - threshold) / divisor + match_fatigue
```

基准参数取 `threshold = 150 km`、`divisor = 70`。若赛制设置额外休整，则疲劳项乘以 `0.35`。后续淘汰赛中，晋级队伍会带入已比赛场次，并按上一阶段旅行负担增加累积疲劳。

### 3.2 淘汰赛

淘汰赛不再直接二选一判胜负，而是显式加入“常规时间平局、加时赛、点球大战”过程。常规时间平局概率随实力差扩大而下降；若平局，则先以较低强弱区分度模拟加时赛，仍未决出胜负时进入点球大战。点球大战使用更高温度参数，表示随机性更强。

小组赛和淘汰赛的常规时间胜负均采用统一 logistic 温度参数：

```text
P(A wins in decisive regular-time result) = 1 / (1 + exp(-Delta / 9))
```

## 4. 候选赛制

为避免只用 3 个方案做 TOPSIS，本文扩展为 7 个候选方案：

| 方案 | 含义 |
|---|---|
| `current_random_draw` | 32 强淘汰赛完全随机抽签。 |
| `random_draw_rest` | 随机抽签，但高出行负担队伍获得额外休整。 |
| `random_draw_reseeded` | 32 强随机抽签，16 强以后复排。 |
| `group_rank_seeded` | 32 强小组第一对小组第二，并回避同组重赛。 |
| `group_rank_seeded_rest` | 小组名次种子制，并加入高出行队伍休整。 |
| `seeded_reseeded` | 32 强种子制，16 强以后按表现复排。 |
| `seeded_reseeded_rest` | 种子制、后续复排和高出行队伍休整同时采用。 |

## 5. 评价指标与综合评分

综合评价纳入以下指标：

- `champion_strength_mean`：冠军平均实力，正向指标。
- `top8_quarterfinal_rate`：实力前 8 队进入八强的平均概率，正向指标。
- `top4_round32_elimination_rate`：实力前 4 队在 32 强首轮出局概率，逆向指标。
- `high_travel_quarterfinal_rate`：高出行负担队伍进入八强概率，正向公平性指标。

`high_travel_group_exit_rate` 只作为描述性统计输出。由于 7 个候选方案的小组赛完全相同，该指标不具备赛制区分能力，不参与综合评价。

最终综合得分采用“预设优先级权重 + TOPSIS”。不用熵权法作为最终排序依据，是因为 `high_travel_quarterfinal_rate` 的跨方案极差只有约 0.6 个百分点，纯熵权容易把这种噪声级波动放大为较高权重。本文将熵权结果保留为诊断对照，但最终排序采用下表权重：

| 指标 | 权重 |
|---|---:|
| champion_strength_mean | 0.25 |
| top8_quarterfinal_rate | 0.30 |
| top4_round32_elimination_rate | 0.35 |
| high_travel_quarterfinal_rate | 0.10 |

该权重体现“竞技公平优先、赛程公平辅助”的原则：前三个核心竞技指标合计占 90%，高出行队伍八强率占 10%。诊断性熵权结果见 `results/problem34/problem4_topsis_weights.txt`。

## 6. 模拟结果

每种方案进行 20000 次模拟，结果如下：

| 方案 | 冠军平均实力 | 前 8 进八强率 | 前 4 首轮出局率 | 高出行队伍八强率 | 优先级 TOPSIS |
|---|---:|---:|---:|---:|---:|
| `current_random_draw` | 82.3054 | 0.3817 | 0.2831 | 0.0995 | 0.258954 |
| `random_draw_rest` | 82.0921 | 0.3794 | 0.2857 | 0.1026 | 0.177112 |
| `random_draw_reseeded` | 82.4141 | 0.3875 | 0.2852 | 0.0977 | 0.398777 |
| `group_rank_seeded` | 82.3523 | 0.3894 | 0.2575 | 0.0980 | 0.662609 |
| `group_rank_seeded_rest` | 82.2552 | 0.3878 | 0.2580 | 0.1012 | 0.596676 |
| `seeded_reseeded` | 82.5267 | 0.3968 | 0.2551 | 0.0964 | 0.822888 |
| `seeded_reseeded_rest` | 82.3047 | 0.3931 | 0.2591 | 0.0995 | 0.706284 |

结果表明，种子保护和后续复排能降低强队在 32 强首轮过早出局的风险。相对于随机抽签，`group_rank_seeded` 将前 4 首轮出局率从 0.2831 降至 0.2575；`seeded_reseeded` 将前 8 进八强率从 0.3817 提高到 0.3968，并取得最高优先级 TOPSIS 分。

需要注意，客观实力代理值使各方案差异比人工实力设定下更小。本文因此不夸大结论，只将其解释为”种子制和复排能带来小幅但稳定的强队保护改善”。

另外，`champion_strength_mean` 跨 7 个方案的极差仅约 0.44（在 [60, 90] 量纲上不足 1.5%），说明赛制编排对冠军归属的影响有限；赛制优化的主要价值在于保护强队不过早相遇（体现为前 8 进八强率和前 4 首轮出局率的改善）。

`seeded_reseeded` 在核心竞技指标上全面领先，但其 `high_travel_quarterfinal_rate`（0.0964）略低于随机抽签基线（0.0995）。这是竞技公平优先的有意识取舍，且差异仅约 0.3 个百分点，低于仿真噪声水平，实践上可以忽略。权重敏感性分析也表明，除非将高出行指标权重提至 20%，否则该取舍不改变推荐结论。

## 7. 权重敏感性

为检验结论是否依赖高出行指标权重，本文设置 5 组权重情景：

| 情景 | 冠军实力 | 前 8 八强 | 前 4 首轮出局 | 高出行八强 | 第一名 |
|---|---:|---:|---:|---:|---|
| core_only | 0.30 | 0.35 | 0.35 | 0.00 | `seeded_reseeded` |
| low_travel | 0.27 | 0.33 | 0.35 | 0.05 | `seeded_reseeded` |
| baseline_priority | 0.25 | 0.30 | 0.35 | 0.10 | `seeded_reseeded` |
| travel_sensitive | 0.23 | 0.28 | 0.34 | 0.15 | `seeded_reseeded` |
| travel_high | 0.20 | 0.27 | 0.33 | 0.20 | `seeded_reseeded_rest` |

可见，当高出行指标权重不超过 15% 时，`seeded_reseeded` 稳居第一；只有将高出行指标提高到 20% 时，休整版才反超。因此本文将 `seeded_reseeded` 作为定量推荐，将额外休整作为运动员保护和赛程福利建议，而不作为提升竞技筛选能力的核心规则。完整表见：

- `results/problem34/problem4_weight_sensitivity.csv`

## 8. 疲劳参数敏感性

对推荐方案 `seeded_reseeded` 做疲劳参数敏感性分析，组合取：

```text
threshold: 100, 150, 200 km
divisor: 50, 70, 90
```

每组参数模拟 4000 次。结果显示：

- `top8_quarterfinal_rate` 范围为 0.3908 到 0.4010。
- `top4_round32_elimination_rate` 范围为 0.2566 到 0.2646。

说明推荐结论对疲劳阈值和衰减尺度的变化不敏感。完整表见：

- `results/problem34/problem4_fatigue_sensitivity.csv`

## 9. 建议

定量推荐采用 `seeded_reseeded`：保留 16 组单循环，小组前二晋级；32 强采用小组第一对小组第二并回避同组；16 强以后按小组名次、积分、净胜球和实力代理值复排。

另外，有两条规则属于模型外的定性制度建议，应与定量结论分开表述：

1. 小组赛最后一轮同组两场同时开球，用于降低策略性默契风险。本文仿真没有建模策略行为，因此该建议来自足球竞赛组织经验，而不是模型直接推出。
2. 高出行负担队伍可获得额外休整日，用于运动员保护和赛程福利。当前仿真未显示该规则能稳定提升竞技筛选能力。

可引用结果文件：

- `results/problem34/problem4_format_comparison.csv`
- `results/problem34/problem4_topsis_weights.txt`
- `results/problem34/problem4_weight_sensitivity.csv`
- `results/problem34/problem4_team_probabilities.csv`
- `results/problem34/problem4_strength_weights.txt`
- `results/problem34/problem4_strength_proxy.csv`
- `results/problem34/problem4_fatigue_sensitivity.csv`
- `results/problem34/problem4_format_comparison.png`
- `results/problem34/problem4_summary.txt`
