# topGears — 期刊文献计量分析

调研目标：**近10年（2016–2026）目标期刊上发文最多的作者/团队，以及高频研究主题。**

---

## 已完成的研究产出

| 阶段 | 产出 | 说明 |
|---|---|---|
| 文献检索 | 6 期刊 2016-2026 数据抓取 | TII, AEI, AutoCon, CompInd, TITS, EAAI |
| 专题分析 | `output/KG_Industry_2024-2026.md` | 知识图谱 × 工业交叉 134 篇文献，按引用降序 |
| 深度阅读 | `downloads/KG_Industry/` | 91 个 PDF 直链 + 30 篇已下 |
| AI 泛读 | `downloads/notes/` | `paper_reader.py` 调用 LLM 生成结构化阅读笔记 |
| 单作者深入 | `downloads/Gangyan_Xu-AEI/` | Xu 的 11 篇论文 PDF + 泛读笔记 + 摘要分析 |

---

## 数据源选择与边界

- 主数据源：**OpenAlex**（免费、无访问限制，作者已消歧，含 topic/concept 标签）
- 辅助数据源：**AMiner** 开放 API（学者搜索、论文详情、引用关系等）
- ❌ Web of Science / Scopus 需付费订阅，不使用
- ⚠️ **中文期刊覆盖差**：`土木工程学报`、`中国公路学报` 在 OpenAlex 中条目稀疏。本工程对这两个期刊**默认不抓取**（`source: cnki` 占位）。如需，可通过 CNKI 高级检索导出 Refworks/CSV 后另写解析。

## 目标期刊（journals.yaml 中可改）

8 个用户指定期刊：TII, AEI, AutoCon, CompInd, TITS, EAAI, CCEJ\*, CJHT\*  
（\* 中文期刊，默认跳过）

## 安装

```bash
cd "D:/A我的研究/000_AutoResearch/14_topGears"
python -m venv .venv
.venv/Scripts/activate
pip install -r requirements.txt
```

## 密钥配置

敏感信息（API token/key）统一存放于项目根目录 `secrets.json`（已 `.gitignore`）：

```json
{
    "aminer_token": "your_jwt_token",
    "siliconflow_api_key": "your_api_key"
}
```

## OpenAlex 数据流水线

```bash
# 1) 校验期刊清单
python src/resolve_journals.py

# 2) 抓取数据
python src/fetch_works.py
python src/fetch_works.py --only TII AEI   # 仅抓取某几个期刊
python src/fetch_works.py --force          # 强制重抓

# 3) 分析 + 出报告
python src/analyze.py --top 30
```

## AMiner API 工具包

`src/aminer_api.py` — 封装 AMiner 开放数据平台 6 个端点：

| API | 方法 | 价格 | 说明 |
|---|---|---|---|
| `search_papers` | GET | 0.01元 | 论文搜索 Pro（标题/关键词/作者/机构） |
| `paper_detail` | GET | 0.01元 | 论文详情（摘要、作者、DOI、期刊） |
| `paper_info` | POST | **免费** | 批量论文信息（最多 100 ID） |
| `paper_citations` | GET | 0.10元 | 论文引用关系 |
| `search_persons` | POST | **免费** | 学者搜索 |
| `person_detail` | GET | 1.00元 | 学者详情（简介、教育、荣誉） |

```python
import json, sys
sys.path.insert(0, r"D:\A我的研究\000_AutoResearch\14_topGears")
from src.aminer_api import AMinerClient

with open("../secrets.json") as f:
    token = json.load(f)["aminer_token"]
client = AMinerClient(token)

# 搜索知识图谱+工业的论文
r = client.search_papers(title="knowledge graph", keyword="industrial", size=20)
ids = [p["id"] for p in r["data"]]
# 批量获取摘要（免费）
r = client.paper_info(ids)
```

## PDF 批量下载

`downloads/KG_Industry/pdf_links.txt` 包含 91 个 ScienceDirect PDF 直链。  
在已登录 ScienceDirect 的浏览器中打开链接即可下载。

## AI 论文泛读

```bash
cd downloads
python paper_reader.py   # 读取 PDF → LLM 生成中文结构化笔记
```

输出格式（Markdown）：文献基本信息 → 一句话总结 → 背景/动机/方法/实验/数据集/结果/改进方向

## 产出目录结构

```
data/raw/{short}_{year}.jsonl        # 原始分片（可断点续抓）
data/processed/works.parquet         # 合并后的扁平数据

output/
    KG_Industry_2024-2026.md         # 专题文献报告（134篇）
    tables/                          # 作者/主题/机构 Top-N CSV

downloads/
    KG_Industry/papers_list.json     # 文献元数据
    KG_Industry/pdf_links.txt        # PDF 下载直链
    Gangyan_Xu-AEI/                  # 单作者论文 PDF + 笔记
    notes/                           # AI 泛读笔记
    paper_reader.py                  # 论文泛读工具

src/
    fetch_works.py                   # 数据抓取
    analyze.py                       # 数据分析
    resolve_journals.py              # 期刊校验
    aminer_api.py                    # AMiner API 工具包
```

## 分析口径说明

- **作者排名**：按 OpenAlex `author_id` 去重计数论文。`author_id` 已做消歧，比按字符串名字精度高一档。
- **团队代理**：用「作者最常出现的机构」作为团队归属。如需「实验室级」团队，需手工合并别名。
- **主题口径**：用 OpenAlex 的 **topics**（4500+ 层级化主题标签），按论文计数。如需更准可在 `analyze.py` 里加 score 阈值。
- **首次/通讯作者**：分别按 `position == first / last` 计数。

## 常见问题

- **抓取很慢/被限流？** 在 `journals.yaml` 填入 `openalex_email`，进入 OpenAlex 的 polite pool。
- **某期刊 0 结果？** 先跑 `resolve_journals.py` 看是否命中。
- **想新增期刊？** 编辑 `journals.yaml`，重跑 `resolve_journals.py`，再跑 `fetch_works.py --only <short>`。

## 路线图

- BERTopic 自建主题模型
- 引文网络分析
- 机构合作网络可视化
- Streamlit 交互看板
- AMiner 数据补充 OpenAlex 缺失的摘要和引用关系
