# topGears — 期刊文献计量分析

调研目标：**近10年（2016–2026）目标期刊上发文最多的作者/团队，以及高频研究主题。**

## 数据源选择与边界

- 主数据源：**OpenAlex**（免费、无访问限制，作者已消歧，含 topic/concept 标签）
- ❌ Web of Science / Scopus 需付费订阅，不使用
- ⚠️ **中文期刊覆盖差**：`土木工程学报`、`中国公路学报` 在 OpenAlex 中条目稀疏。本工程对这两个期刊**默认不抓取**（`source: cnki` 占位）。如需，可通过 CNKI 高级检索导出 Refworks/CSV 后另写解析。

## 目标期刊（journals.yaml 中可改）

8 个用户指定期刊：TII, AEI, AutoCon, CompInd, TITS, EAAI, CCEJ\*, CJHT\*  
（\* 中文期刊，默认跳过）

## 安装

```bash
cd "D:/A我的研究/000_AutoResearch/14_topGears"
python -m venv .venv
.venv/Scripts/activate     # PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 运行顺序

```bash
# 1) 校验期刊清单（确认每个 ISSN 都能在 OpenAlex 命中）
python src/resolve_journals.py

# 2) 抓取数据（首次运行较慢，估计 8 期刊 x 11 年 ≈ 数万条，几分钟到十几分钟）
python src/fetch_works.py

# 仅抓取某几个期刊：
python src/fetch_works.py --only TII AEI

# 强制重抓（默认已存在的分片会跳过）：
python src/fetch_works.py --force

# 3) 分析 + 出报告
python src/analyze.py --top 30
```

## 产出

```
data/raw/{short}_{year}.jsonl       # 原始分片（可断点续抓）
data/processed/works.parquet        # 合并后的扁平数据
output/tables/
    top_authors__ALL.csv            # 跨期刊 Top 作者
    top_authors__{short}.csv        # 单期刊 Top 作者（含主要机构、第一作者数、通讯作者数）
    top_institutions__{short}.csv   # 单期刊 Top 机构（团队代理）
    top_topics__ALL.csv             # 跨期刊 Top 主题
    top_topics__{short}.csv         # 单期刊 Top 主题
    topic_yearly__{short}.csv       # 主题年度热度（长表，便于画热力图）
output/REPORT.md                    # 人读总览
```

## 分析口径说明

- **作者排名**：按 OpenAlex `author_id` 去重计数论文。`author_id` 已做消歧（同名不同人/同人不同写法都会处理），比按字符串名字精度高一档。
- **团队代理**：OpenAlex 不直接给「团队」字段。本工程用「作者最常出现的机构」作为团队归属，并在跨期刊表里用 `top_institutions__*.csv` 单列机构维度。如需「实验室级」团队，需要手工合并别名。
- **主题口径**：用 OpenAlex 的 **topics**（4500+ 层级化主题标签，2024 起替代旧的 concepts），按论文计数。topics 字段已自带 `score`，本工程默认全收，不按 score 过滤——如需更准可在 `analyze.py` 里加阈值。
- **首次/通讯作者**：分别按 `position == first / last` 计数，便于区分「干活的人」和「带队的人」。

## 常见问题

- **抓取很慢/被限流？** 在 `journals.yaml` 填入 `openalex_email`，进入 OpenAlex 的 polite pool，速率更稳定。
- **某期刊 0 结果？** 先跑 `resolve_journals.py` 看是否命中。如果命中但年份范围内为 0，多半是 ISSN 写错或 OpenAlex 该期刊覆盖不全。
- **想新增期刊？** 编辑 `journals.yaml` 加一项，重跑 `resolve_journals.py` 校验，再跑 `fetch_works.py --only <short>` 单独抓取即可。

## 路线图（可选扩展）

- BERTopic 自建主题模型（更贴期刊语义粒度）
- 引文网络分析（高被引论文、谁引谁）
- 国家/机构合作网络可视化
- Streamlit 交互看板
