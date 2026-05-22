"""Shared constants for the Taiji CLI."""

from pathlib import Path

BASE = "https://taiji.algo.qq.com"
ALGO_BASE = "https://algo.qq.com"
COOKIES_PATH = Path.home() / ".taiji" / "cookies.txt"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
)

COS_BUCKET = "hunyuan-external-1258344706"
COS_REGION = "ap-guangzhou"
