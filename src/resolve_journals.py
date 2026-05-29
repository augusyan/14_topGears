"""
Validate journals.yaml against OpenAlex.

For each entry with source=openalex:
  - look up by ISSN (preferred) or by name
  - print resolved source_id, works_count, host_organization
  - warn if no match

Usage:
    python src/resolve_journals.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml
import pyalex
from pyalex import Sources

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "journals.yaml"


def load_config() -> dict:
    with CONFIG.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def resolve_one(entry: dict) -> dict | None:
    issn = entry.get("issn")
    name = entry.get("name")
    short = entry.get("short")

    try:
        if issn:
            hits = Sources().filter(issn=issn).get()
        else:
            hits = Sources().search(name).get(per_page=5)
    except Exception as exc:
        print(f"  [ERROR] {short}: {exc}")
        return None

    if not hits:
        print(f"  [MISS]  {short}: no OpenAlex source for issn={issn!r} name={name!r}")
        return None

    top = hits[0]
    info = {
        "short": short,
        "openalex_id": top["id"].split("/")[-1],
        "display_name": top.get("display_name"),
        "issn_l": top.get("issn_l"),
        "issn": top.get("issn"),
        "works_count": top.get("works_count"),
        "host_org": (top.get("host_organization_name") or ""),
    }
    print(
        f"  [OK]    {short:<8} -> {info['openalex_id']:<14} "
        f"works={info['works_count']:>6}  {info['display_name']}"
    )
    return info


def main() -> int:
    cfg = load_config()
    email = cfg.get("openalex_email") or None
    if email:
        pyalex.config.email = email
    else:
        print("[warn] openalex_email is empty in journals.yaml — using public pool")

    print(f"\nResolving {len(cfg['journals'])} journals against OpenAlex...\n")

    ok, miss, skip = 0, 0, 0
    for entry in cfg["journals"]:
        src = entry.get("source", "openalex")
        if src != "openalex":
            print(f"  [SKIP]  {entry['short']}: source={src} (not OpenAlex)")
            skip += 1
            continue
        info = resolve_one(entry)
        if info is None:
            miss += 1
        else:
            ok += 1

    print(f"\nSummary: ok={ok}  miss={miss}  skip={skip}")
    return 0 if miss == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
