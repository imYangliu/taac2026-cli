"""Leaderboard commands."""

from __future__ import annotations

import argparse
import json
import sys

from .constants import ALGO_BASE
from .session import make_session


def cmd_rank(args: argparse.Namespace) -> None:
    s = make_session()
    body = {"isStudent": args.student, "pageNo": args.page, "pageSize": args.size}
    r = s.post(
        f"{ALGO_BASE}/api/algo/getCompetitionRank",
        headers={
            "Origin": ALGO_BASE,
            "Referer": f"{ALGO_BASE}/leaderboard",
            "Content-Type": "application/json",
        },
        json=body, timeout=30,
    )
    if r.status_code == 401:
        sys.exit("auth failed — cookies likely expired. Run: taiji auth setup")
    r.raise_for_status()
    data = r.json()
    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return
    payload = data.get("data") or data
    rows = payload.get("list") or payload.get("rows") or payload.get("data") or []
    if not rows and isinstance(payload, list):
        rows = payload
    if not rows:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return
    print(f"leaderboard {'(student)' if args.student else '(all)'} — page {args.page}, "
          f"showing {len(rows)} entries:")
    for i, row in enumerate(rows, start=1):
        rank = row.get("rank") or row.get("ranking") or i
        name = row.get("teamName") or row.get("name") or row.get("user") or "?"
        score = row.get("score") or row.get("auc") or row.get("bestScore") or "—"
        print(f"  #{rank:<4}  {score!s:<12}  {name}")
