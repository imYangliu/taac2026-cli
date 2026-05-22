"""Raw endpoint probing command."""

from __future__ import annotations

import argparse
import json

from .constants import BASE
from .session import make_session


def cmd_raw(args: argparse.Namespace) -> None:
    """Hit an arbitrary path with the cookie jar and pretty-print the response.

    Useful when a UI page calls an API we haven't wired up yet — open Network
    in DevTools, copy the path/query, and pass it here to inspect.
    """
    s = make_session()
    url = args.path if args.path.startswith("http") else f"{BASE}{args.path}"
    headers: dict[str, str] = {}
    if args.referer:
        headers["Referer"] = args.referer
    body = None
    if args.data:
        body = json.loads(args.data)
        headers["Content-Type"] = "application/json"
    method = args.method or ("POST" if body is not None else "GET")
    r = s.request(method, url, headers=headers, json=body, timeout=30)
    print(f"HTTP {r.status_code} {method}  ({len(r.content)} bytes)")
    ct = r.headers.get("content-type", "")
    print(f"Content-Type: {ct}")
    if "json" in ct:
        try:
            print(json.dumps(r.json(), indent=2, ensure_ascii=False))
            return
        except json.JSONDecodeError:
            pass
    text = r.text
    if len(text) > 4000:
        text = text[:4000] + f"\n... ({len(r.text) - 4000} more bytes)"
    print(text)
