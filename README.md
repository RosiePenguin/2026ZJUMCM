# 2026 ZJU MCM Team Project

这是一个面向浙大数模校赛的简洁 Python 项目。项目结构按最终提交时更自然的“问题模块”组织，而不是按成员拆目录。

## 推荐环境

- Python 3.10 或 3.11
- VS Code
- Git
- GitHub
- VS Code 插件：`Python`、`Pylance`

当前版本只依赖 Python 标准库，可以直接运行。

## 快速开始

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python scripts/run_problem1.py
```

运行后结果会保存在 `results/problem1/`。

## 项目结构

```text
2026ZJUMCM/
├─ .vscode/                 VS Code 配置
├─ data/
│  └─ raw/                  原始数据
├─ docs/
│  ├─ problem1/             问题 1 的论文素材
│  ├─ problem2/             问题 2 的论文素材
│  └─ problem34/            问题 3、4 的论文素材
├─ results/
│  ├─ problem1/             问题 1 输出结果
│  ├─ problem2/             问题 2 输出结果
│  └─ problem34/            问题 3、4 输出结果
├─ scripts/
│  ├─ run_problem1.py       问题 1 运行入口
│  ├─ run_problem2.py       问题 2 运行入口
│  └─ run_problem34.py      问题 3、4 运行入口
├─ src/
│  ├─ problem1/             问题 1 核心代码
│  ├─ problem2/             问题 2 核心代码
│  └─ problem34/            问题 3、4 核心代码
└─ README.md
```

## 3 位成员分别写哪里

- 队员 A：
  主要在 `src/problem1/` 写代码，运行入口是 `scripts/run_problem1.py`，输出结果看 `results/problem1/`，论文相关材料放 `docs/problem1/`。

- 队员 B：
  主要在 `src/problem2/` 写代码，运行入口是 `scripts/run_problem2.py`，输出结果放 `results/problem2/`，论文相关材料放 `docs/problem2/`。

- 队员 C：
  主要在 `src/problem34/` 写代码，运行入口是 `scripts/run_problem34.py`，输出结果放 `results/problem34/`，论文相关材料放 `docs/problem34/`。

这样做的好处是最后提交代码时结构很清楚：按题目功能分，而不是按成员名字分。

## 当前已经完成的内容

目前已经完成问题 1 的基础版本，也就是队员 A 的起步代码。

核心文件：

- `src/problem1/data_loader.py`
- `src/problem1/generator.py`
- `src/problem1/scoring.py`
- `src/problem1/pipeline.py`
- `scripts/run_problem1.py`

当前数据文件：

- `data/raw/teams.csv`

当前输出文件：

- `results/problem1/best_groups.csv`
- `results/problem1/all_scores.csv`
- `results/problem1/summary.txt`

## 问题 1 当前实现的功能

- 自动生成满足硬约束的 16 组分组方案
- 尽量减少同市县级队同组
- 对多个方案评分和排序
- 导出分组结果和摘要

硬约束：

- 11 个市级队必须位于不同小组
- 若某组有某市市级队，则该组不能出现该市代管县级队
- 每组 4 支队伍，共 16 组

评价指标：

- `soft_conflict_pairs`：同市县级队同组冲突对数，越小越好
- `avg_city_entropy`：来源城市分散度，越大越好
- `strength_balance_std`：各组总实力标准差，越小越好

## 协作建议

- 每个人主要改自己对应的问题目录
- 公共数据尽量统一放在 `data/`
- 每次修改前先 `git pull`
- 每完成一小块就提交一次
- 合并到主分支前先确保脚本能跑通

## 关于 GitHub 上传

你刚发的链接：

- `https://github.com/users/RosiePenguin/projects/1`

这不是 Git 仓库链接，而是 GitHub Projects 页面链接，所以不能用来 `git push`。

真正可用于推送的仓库链接一般长这样：

- `https://github.com/RosiePenguin/仓库名.git`

或者：

- `git@github.com:RosiePenguin/仓库名.git`

你只要把真正的仓库链接发给我，我就可以继续帮你把本地仓库连上并推送。
