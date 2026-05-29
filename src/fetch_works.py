"""
Fetch all works for every (journal, year) shard configured in journals.yaml.

- One JSONL file per shard at data/raw/{short}_{year}.jsonl
- Resumable: existing non-empty shards are skipped unless --force is passed
- After fetching, a single flat parquet is built at data/processed/works.parquet

Each work record is flattened to the fields we actually need for analysis:
  id, doi, title, year, type, language, cited_by_count, journal_short,
  authorships (list of {author_id, author_name, institution_id, institution_name, country}),
  topics (list of {id, display_name, score}),
  concepts (list of {id, display_name, level, score})

Usage:
    python src/fetch_works.py                # fetch all journals x years
    python src/fetch_works.py --only TII AEI # subset
    python src/fetch_works.py --force        # re-fetch even if shard exists
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml
import pyalex
from pyalex import Works
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "journals.yaml"
RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"


def load_config() -> dict:
    with CONFIG.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def flatten_work(w: dict, journal_short: str) -> dict:
    authorships = []
    for a in w.get("authorships") or []:
        author = a.get("author") or {}
        insts = a.get("institutions") or []
        inst = insts[0] if insts else {}
        authorships.append({
            "author_id": (author.get("id") or "").split("/")[-1],
            "author_name": author.get("display_name"),
            "institution_id": (inst.get("id") or "").split("/")[-1],
            "institution_name": inst.get("display_name"),
            "country": inst.get("country_code"),
            "position": a.get("author_position"),
        })

    topics = [{
        "id": (t.get("id") or "").split("/")[-1],
        "display_name": t.get("display_name"),
        "score": t.get("score"),
    } for t in (w.get("topics") or [])]

    concepts = [{
        "id": (c.get("id") or "").split("/")[-1],
        "display_name": c.get("display_name"),
        "level": c.get("level"),
        "score": c.get("score"),
    } for c in (w.get("concepts") or [])]

    return {
        "id": (w.get("id") or "").split("/")[-1],
        "doi": w.get("doi"),
        "title": w.get("title"),
        "year": w.get("publication_year"),
        "type": w.get("type"),
        "language": w.get("language"),
        "cited_by_count": w.get("cited_by_count"),
        "journal_short": journal_short,
        "authorships": authorships,
        "topics": topics,
        "concepts": concepts,
    }


def fetch_shard(issn: str, year: int, journal_short: str, out: Path) -> int:
    pager = (
        Works()
        .filter(primary_location={"source": {"issn": issn}})
        .filter(publication_year=year)
        .paginate(per_page=200, n_max=None)
    )
    count = 0
    with out.open("w", encoding="utf-8") as f:
        for page in pager:
            for w in page:
                f.write(json.dumps(flatten_work(w, journal_short), ensure_ascii=False) + "\n")
                count += 1
    return count


def build_parquet() -> None:
    import pandas as pd

    rows = []
    for shard in sorted(RAW.glob("*.jsonl")):
        with shard.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    if not rows:
        print("[parquet] no rows — skipping")
        return

    df = pd.DataFrame(rows)
    PROC.mkdir(parents=True, exist_ok=True)
    out = PROC / "works.parquet"
    df.to_parquet(out, index=False)
    print(f"[parquet] wrote {len(df):,} rows -> {out}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=None, help="filter by journal short codes")
    ap.add_argument("--force", action="store_true", help="re-fetch even if shard exists")
    ap.add_argument("--skip-parquet", action="store_true")
    args = ap.parse_args()

    cfg = load_config()
    email = cfg.get("openalex_email") or None
    if email:
        pyalex.config.email = email

    yr_start, yr_end = cfg["year_range"]
    RAW.mkdir(parents=True, exist_ok=True)

    targets = [j for j in cfg["journals"] if j.get("source", "openalex") == "openalex"]
    if args.only:
        wanted = set(args.only)
        targets = [j for j in targets if j["short"] in wanted]

    print(f"Fetching {len(targets)} journals x {yr_end - yr_start + 1} years")
    total = 0
    for j in targets:
        short, issn = j["short"], j["issn"]
        for year in tqdm(range(yr_start, yr_end + 1), desc=f"{short:<8}", leave=False):
            out = RAW / f"{short}_{year}.jsonl"
            if out.exists() and out.stat().st_size > 0 and not args.force:
                continue
            try:
                n = fetch_shard(issn, year, short, out)
                total += n
            except Exception as exc:
                # leave partial/empty file? remove so we can retry cleanly
                if out.exists() and out.stat().st_size == 0:
                    out.unlink()
                print(f"\n[ERROR] {short} {year}: {exc}", file=sys.stderr)

    print(f"\nFetched {total:,} new works")

    if not args.skip_parquet:
        build_parquet()

    return 0


if __name__ == "__main__":
    sys.exit(main())
