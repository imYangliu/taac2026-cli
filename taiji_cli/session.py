"""HTTP session, cookie parsing, and API helpers."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import requests

from .constants import BASE, COOKIES_PATH, UA


def load_cookies(path: Path = COOKIES_PATH) -> dict[str, str]:
    if not path.exists():
        sys.exit(
            f"cookies file not found: {path}\n"
            f"run: taiji auth setup  (then paste cookies, Ctrl-D)"
        )
    cookies = parse_cookie_text(path.read_text())
    if not cookies:
        sys.exit(f"no cookies parsed from {path}")
    return cookies


def parse_cookie_text(text: str) -> dict[str, str]:
    """解析浏览器 document.cookie、curl 的 Cookie 行，或逐行 key=value 格式。"""
    cookies: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("cookie:"):
            line = line.partition(":")[2].strip()
        # document.cookie 是 "a=b; c=d"；旧格式是一行一个 "a=b"，两种都兼容。
        for part in line.split(";"):
            part = part.strip()
            if not part or "=" not in part:
                continue
            k, _, v = part.partition("=")
            k = k.strip()
            if k:
                cookies[k] = v.strip()
    return cookies


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
    })
    s.cookies.update(load_cookies())
    return s


def get_json(s: requests.Session, path: str, *, referer: str = BASE, **params: Any) -> Any:
    headers = {"Referer": referer}
    r = s.get(f"{BASE}{path}", params=params, headers=headers, timeout=30)
    if r.status_code == 401 or "login expired" in r.text[:200]:
        sys.exit("auth failed — cookies likely expired. Run: taiji auth setup")
    r.raise_for_status()
    try:
        return r.json()
    except json.JSONDecodeError:
        sys.exit(f"non-JSON response from {path}:\n{r.text[:500]}")


def _write_json(s: requests.Session, method: str, path: str, body: dict[str, Any], *, referer: str = BASE) -> Any:
    r = getattr(s, method)(
        f"{BASE}{path}",
        headers={"Origin": BASE, "Referer": referer, "Content-Type": "application/json"},
        json=body,
        timeout=30,
    )
    if r.status_code == 401 or "login expired" in r.text[:200]:
        sys.exit("auth failed — cookies likely expired. Run: taiji auth setup")
    r.raise_for_status()
    try:
        return r.json()
    except json.JSONDecodeError:
        sys.exit(f"non-JSON response from {path}:\n{r.text[:500]}")


def post_json(s: requests.Session, path: str, body: dict[str, Any], *, referer: str = BASE) -> Any:
    """发送带登录 cookie 的 JSON POST 请求，用于创建、启动任务等写操作。"""
    return _write_json(s, "post", path, body, referer=referer)


def put_json(s: requests.Session, path: str, body: dict[str, Any], *, referer: str = BASE) -> Any:
    """发送带登录 cookie 的 JSON PUT 请求，用于就地更新已有任务。"""
    return _write_json(s, "put", path, body, referer=referer)


def check_api(data: Any) -> None:
    """统一检查 Taiji API 的业务错误码，避免各命令重复判断。"""
    if isinstance(data, dict) and data.get("error", {}).get("code") not in (None, "SUCCESS"):
        sys.exit(f"API error: {data['error']}")
