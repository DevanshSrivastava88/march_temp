#!/usr/bin/env python3
"""
Fetch the top 5 Hacker News stories via the official HN Firebase API
and save results as hn_<DATE>.json.

Usage:
    python fetch_hn.py

Requires: Python 3.8+ (stdlib only)
"""

import json
import urllib.request

HN_BASE = "https://hacker-news.firebaseio.com/v0"
DATE     = "2026-03-30"
OUT_FILE = f"hn_{DATE}.json"
TOP_N    = 5


def fetch_json(url: str) -> object:
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.loads(resp.read().decode())


def main() -> None:
    print("Fetching top story IDs ...")
    top_ids = fetch_json(f"{HN_BASE}/topstories.json")[:TOP_N]

    stories = []
    for story_id in top_ids:
        print(f"  Fetching item {story_id} ...")
        item = fetch_json(f"{HN_BASE}/item/{story_id}.json")
        stories.append({
            "title":  item.get("title"),
            "url":    item.get("url"),
            "score":  item.get("score"),
            "author": item.get("by"),
            "time":   item.get("time"),
        })

    with open(OUT_FILE, "w", encoding="utf-8") as fh:
        json.dump(stories, fh, indent=2, ensure_ascii=False)

    print(f"\nSaved {TOP_N} stories -> {OUT_FILE}")
    for i, s in enumerate(stories, 1):
        print(f"  {i}. [{s['score']} pts] {s['title']}")


if __name__ == "__main__":
    main()
