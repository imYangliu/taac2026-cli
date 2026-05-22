"""Authentication commands."""

from __future__ import annotations

import argparse
import sys

from .constants import COOKIES_PATH
from .session import get_json, make_session, parse_cookie_text


def cmd_auth_setup(_args: argparse.Namespace) -> None:
    COOKIES_PATH.parent.mkdir(parents=True, exist_ok=True)
    if COOKIES_PATH.exists():
        existing = parse_cookie_text(COOKIES_PATH.read_text())
        print(
            f"cookies already configured at {COOKIES_PATH} "
            f"({len(existing)} parsed). Overwrite? [y/N] ",
            end="",
            file=sys.stderr,
        )
        answer = sys.stdin.readline().strip().lower()
        if answer not in ("y", "yes"):
            print("kept existing cookies.", file=sys.stderr)
            return
    print(
        "Paste document.cookie output or key=value cookies. Ctrl-D when done:",
        file=sys.stderr,
    )
    content = sys.stdin.read()
    cookies = parse_cookie_text(content)
    if not cookies:
        sys.exit("no cookies parsed from stdin")
    # 归一化成一行一个 key=value，方便人工检查，也兼容旧版读取方式。
    normalized = "\n".join(f"{k}={v}" for k, v in cookies.items()) + "\n"
    COOKIES_PATH.write_text(normalized)
    COOKIES_PATH.chmod(0o600)
    print(f"wrote {len(cookies)} cookies -> {COOKIES_PATH}")


def cmd_auth_check(_args: argparse.Namespace) -> None:
    s = make_session()
    data = get_json(s, "/aide/api/evaluation_tasks/", pageNum=0, pageSize=1)
    count = data.get("count", "?")
    print(f"OK — {count} evaluation(s) accessible")
