"""
Read data/processed/works.parquet and produce:

  output/tables/top_authors__{short}.csv          # top N authors per journal
  output/tables/top_authors__ALL.csv              # aggregated across journals
  output/tables/top_institutions__{short}.csv     # team proxy: leading institution
  output/tables/top_topics__{short}.csv           # OpenAlex topic frequency per journal
  output/tables/top_topics__ALL.csv
  output/tables/topic_yearly__{short}.csv         # topic x year matrix (long form)
  output/REPORT.md                                # human-readable summary

Usage:
    python src/analyze.py                  # all journals, top 30
    python src/analyze.py --top 50         # change top-N
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed" / "works.parquet"
TABLES = ROOT / "output" / "tables"
REPORT = ROOT / "output" / "REPORT.md"


def _iter_list(val) -> list:
    """Parquet round-trip turns list<struct> into numpy arrays; normalize back."""
    if val is None:
        return []
    try:
        if len(val) == 0:
            return []
    except TypeError:
        return []
    return list(val)


def explode_authorships(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in df.iterrows():
        for a in _iter_list(r["authorships"]):
            rows.append({
                "work_id": r["id"],
                "year": r["year"],
                "journal_short": r["journal_short"],
                "author_id": a.get("author_id"),
                "author_name": a.get("author_name"),
                "institution_id": a.get("institution_id"),
                "institution_name": a.get("institution_name"),
                "country": a.get("country"),
                "position": a.get("position"),
            })
    return pd.DataFrame(rows)


def explode_topics(df: pd.DataFrame, key: str = "topics") -> pd.DataFrame:
    rows = []
    for _, r in df.iterrows():
        for t in _iter_list(r[key]):
            rows.append({
                "work_id": r["id"],
                "year": r["year"],
                "journal_short": r["journal_short"],
                "topic_id": t.get("id"),
                "topic_name": t.get("display_name"),
                "score": t.get("score"),
            })
    return pd.DataFrame(rows)


def top_authors(authors: pd.DataFrame, top_n: int) -> pd.DataFrame:
    # Count distinct works per (author_id, author_name)
    base = authors.copy()
    base["author_id"] = base["author_id"].replace("", pd.NA)
    g = (
        base.dropna(subset=["author_id"])
        .groupby(["author_id", "author_name"])["work_id"]
        .nunique()
        .reset_index(name="works")
        .sort_values("works", ascending=False)
    )
    return g.head(top_n)


def top_authors_with_lead(authors: pd.DataFrame, top_n: int) -> pd.DataFrame:
    """Top authors enriched with their most common institution + first/last author counts."""
    base = authors.copy()
    base["author_id"] = base["author_id"].replace("", pd.NA)
    base = base.dropna(subset=["author_id"])
    works_per_author = (
        base.groupby(["author_id", "author_name"])["work_id"]
        .nunique()
        .reset_index(name="works")
    )

    # Most common institution per author
    inst_mode = (
        base.dropna(subset=["institution_name"])
        .groupby(["author_id", "institution_name"])
        .size()
        .reset_index(name="n")
        .sort_values(["author_id", "n"], ascending=[True, False])
        .drop_duplicates("author_id")
        .rename(columns={"institution_name": "primary_institution"})
        [["author_id", "primary_institution"]]
    )

    first = base[base["position"] == "first"].groupby("author_id")["work_id"].nunique().rename("first_author")
    last = base[base["position"] == "last"].groupby("author_id")["work_id"].nunique().rename("last_author")

    out = (
        works_per_author
        .merge(inst_mode, on="author_id", how="left")
        .merge(first, on="author_id", how="left")
        .merge(last, on="author_id", how="left")
        .fillna({"first_author": 0, "last_author": 0})
        .astype({"first_author": int, "last_author": int})
        .sort_values("works", ascending=False)
    )
    return out.head(top_n)


def top_institutions(authors: pd.DataFrame, top_n: int) -> pd.DataFrame:
    base = authors.copy()
    base["institution_id"] = base["institution_id"].replace("", pd.NA)
    g = (
        base.dropna(subset=["institution_id"])
        .groupby(["institution_id", "institution_name", "country"])["work_id"]
        .nunique()
        .reset_index(name="works")
        .sort_values("works", ascending=False)
    )
    return g.head(top_n)


def top_topics(topics: pd.DataFrame, top_n: int) -> pd.DataFrame:
    g = (
        topics.dropna(subset=["topic_id"])
        .groupby(["topic_id", "topic_name"])["work_id"]
        .nunique()
        .reset_index(name="works")
        .sort_values("works", ascending=False)
    )
    return g.head(top_n)


def topic_yearly(topics: pd.DataFrame, top_n: int) -> pd.DataFrame:
    """Long-form (topic, year, works) for the top-N topics."""
    top = top_topics(topics, top_n)["topic_name"].tolist()
    sub = topics[topics["topic_name"].isin(top)]
    g = (
        sub.groupby(["topic_name", "year"])["work_id"]
        .nunique()
        .reset_index(name="works")
        .sort_values(["topic_name", "year"])
    )
    return g


def write_report(stats: dict, top_n: int) -> None:
    lines = []
    lines.append(f"# topGears 文献计量报告\n")
    lines.append(f"- 数据源: OpenAlex（author_id 已消歧）")
    lines.append(f"- 年份范围: {stats['year_min']}–{stats['year_max']}")
    lines.append(f"- 期刊数: {stats['n_journals']}")
    lines.append(f"- 论文数: {stats['n_works']:,}\n")

    lines.append("> **数据质量提示**：")
    lines.append("> - `works`、`first_author`、`last_author` 均基于 OpenAlex `author_id`，已对同名作者做消歧，准确度较高。")
    lines.append("> - `primary_institution`（作者最常出现的机构）依赖 OpenAlex 的机构链接，存在噪声。")
    lines.append(">   尤其 **TITS** 在 OpenAlex 上常将多位欧洲作者错标为 *Virginia Tech*（疑似机构别名归并问题），")
    lines.append(">   遇到不符常识的机构请以作者真实归属为准；论文数本身不受影响。")
    lines.append("> - 中文期刊（土木工程学报、中国公路学报）在 OpenAlex 覆盖差，本次未抓取。\n")

    lines.append("## 各期刊产出概览\n")
    lines.append(stats["per_journal"].to_markdown(index=False))
    lines.append("")

    lines.append(f"\n## 跨期刊 Top {top_n} 作者\n")
    lines.append(stats["top_authors_all"].to_markdown(index=False))

    lines.append(f"\n## 跨期刊 Top {top_n} 主题\n")
    lines.append(stats["top_topics_all"].to_markdown(index=False))

    # Per-journal inline top-10
    show_n = min(10, top_n)
    lines.append(f"\n---\n\n## 各期刊 Top {show_n} 作者\n")
    for short, df_a in stats["per_journal_authors"].items():
        lines.append(f"### {short}\n")
        lines.append(df_a.head(show_n).to_markdown(index=False))
        lines.append("")

    lines.append(f"\n## 各期刊 Top {show_n} 主题\n")
    for short, df_t in stats["per_journal_topics"].items():
        lines.append(f"### {short}\n")
        lines.append(df_t.head(show_n).to_markdown(index=False))
        lines.append("")

    lines.append("\n## 完整明细 CSV\n")
    lines.append("`output/tables/` 下：\n")
    lines.append("- `top_authors__{short}.csv` — 作者 Top 30（含主要机构、第一/通讯作者数）")
    lines.append("- `top_institutions__{short}.csv` — 机构 Top 30（团队代理）")
    lines.append("- `top_topics__{short}.csv` — OpenAlex topic Top 30")
    lines.append("- `topic_yearly__{short}.csv` — Top 30 主题的年度长表")
    lines.append("- `top_authors__ALL.csv` / `top_topics__ALL.csv` — 跨期刊汇总")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"[report] wrote {REPORT}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=30, help="top-N for rankings")
    args = ap.parse_args()

    if not PROC.exists():
        print(f"ERROR: {PROC} not found. Run fetch_works.py first.")
        return 1

    TABLES.mkdir(parents=True, exist_ok=True)
    df = pd.read_parquet(PROC)
    print(f"loaded {len(df):,} works across {df['journal_short'].nunique()} journals")

    # Flatten once
    authors_all = explode_authorships(df)
    topics_all = explode_topics(df, key="topics")

    stats = {
        "n_works": len(df),
        "n_journals": df["journal_short"].nunique(),
        "year_min": int(df["year"].min()),
        "year_max": int(df["year"].max()),
    }

    per_j = (
        df.groupby("journal_short")
        .agg(works=("id", "nunique"),
             year_min=("year", "min"),
             year_max=("year", "max"))
        .reset_index()
        .sort_values("works", ascending=False)
    )
    stats["per_journal"] = per_j

    # ALL-journals aggregates
    stats["top_authors_all"] = top_authors_with_lead(authors_all, args.top)
    stats["top_authors_all"].to_csv(TABLES / "top_authors__ALL.csv", index=False, encoding="utf-8-sig")

    stats["top_topics_all"] = top_topics(topics_all, args.top)
    stats["top_topics_all"].to_csv(TABLES / "top_topics__ALL.csv", index=False, encoding="utf-8-sig")

    # Per-journal
    per_journal_authors: dict[str, pd.DataFrame] = {}
    per_journal_topics: dict[str, pd.DataFrame] = {}
    for short, sub_w in df.groupby("journal_short"):
        sub_a = authors_all[authors_all["journal_short"] == short]
        sub_t = topics_all[topics_all["journal_short"] == short]

        top_a = top_authors_with_lead(sub_a, args.top)
        top_t = top_topics(sub_t, args.top)
        per_journal_authors[short] = top_a
        per_journal_topics[short] = top_t

        top_a.to_csv(TABLES / f"top_authors__{short}.csv", index=False, encoding="utf-8-sig")
        top_institutions(sub_a, args.top).to_csv(
            TABLES / f"top_institutions__{short}.csv", index=False, encoding="utf-8-sig"
        )
        top_t.to_csv(TABLES / f"top_topics__{short}.csv", index=False, encoding="utf-8-sig")
        topic_yearly(sub_t, args.top).to_csv(
            TABLES / f"topic_yearly__{short}.csv", index=False, encoding="utf-8-sig"
        )
        print(f"  [{short}] {len(sub_w):,} works -> tables written")

    stats["per_journal_authors"] = per_journal_authors
    stats["per_journal_topics"] = per_journal_topics

    write_report(stats, args.top)
    print("\nDone. See output/REPORT.md and output/tables/.")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
