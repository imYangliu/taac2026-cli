"""COS file download/upload commands."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from .constants import BASE, COS_BUCKET, COS_REGION
from .session import get_json, make_session


def get_cos_client(s: Any) -> Any:
    """从 Taiji 获取临时 STS 凭证，并构造 COS 客户端。"""
    try:
        from qcloud_cos import CosConfig, CosS3Client
    except ImportError:
        sys.exit("missing dependency: pip install cos-python-sdk-v5")
    tok = get_json(
        s, "/aide/api/evaluation_tasks/get_federation_token/",
        referer=f"{BASE}/training",
    )
    cfg = CosConfig(
        Region=COS_REGION,
        SecretId=tok["id"], SecretKey=tok["key"], Token=tok["Token"],
    )
    return CosS3Client(cfg)


def cos_read(client: Any, key: str) -> bytes:
    """读取 COS 对象内容，用于下载模板文件或任务快照。"""
    resp = client.get_object(Bucket=COS_BUCKET, Key=key)
    return resp["Body"].get_raw_stream().read()


def cos_write(client: Any, key: str, body: bytes) -> None:
    """上传文件内容到 COS；浏览器里的 OPTIONS 预检在 CLI/SDK 中不需要手动发送。"""
    client.put_object(Bucket=COS_BUCKET, Key=key, Body=body)


def filter_unchanged_uploads(
    s: Any,
    uploads: dict,
    template_files: list[dict[str, Any]],
) -> dict:
    """剔除和官方模板字节级一致的本地文件，避免误传"伪 diff"副本。

    模板文件有 size 字段；size 不同直接保留，size 相同时再下载内容做精确比对，
    最大限度减少 COS 读取。返回值是过滤后的 uploads 副本，原 dict 不动。
    """
    template_by_name = {f["name"]: f for f in template_files}
    kept: dict = {}
    client = None
    for name, local in uploads.items():
        tmpl = template_by_name.get(name)
        if tmpl is not None and tmpl.get("size") == local.stat().st_size:
            if client is None:
                client = get_cos_client(s)
            tmpl_bytes = cos_read(client, tmpl["path"])
            if tmpl_bytes == local.read_bytes():
                print(f"  skip {name}: identical to official template")
                continue
        kept[name] = local
    return kept


def cmd_file_cat(args: argparse.Namespace) -> None:
    s = make_session()
    client = get_cos_client(s)
    body = cos_read(client, args.path)
    sys.stdout.buffer.write(body)


def cmd_file_get(args: argparse.Namespace) -> None:
    s = make_session()
    client = get_cos_client(s)
    body = cos_read(client, args.path)
    out = args.out or Path(args.path).name
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_bytes(body)
    print(f"wrote {len(body)} bytes -> {out}")


def cmd_file_put(args: argparse.Namespace) -> None:
    """调试用的单文件上传命令；创建任务时通常用 task create 自动上传。"""
    local = Path(args.local)
    if not local.is_file():
        sys.exit(f"not a file: {local}")
    s = make_session()
    client = get_cos_client(s)
    body = local.read_bytes()
    cos_write(client, args.key, body)
    print(f"uploaded {len(body)} bytes -> {args.key}")


def cmd_file_snapshot(args: argparse.Namespace) -> None:
    """Download all trainFiles of a task to a local dir, preserving filenames."""
    s = make_session()
    task = get_json(
        s, f"/taskmanagement/api/v1/webtasks/external/task/{args.task_id}",
        referer=f"{BASE}/training",
    )
    payload = task.get("data", task)
    files = payload.get("trainFiles", [])
    if not files:
        sys.exit(f"task {args.task_id} has no trainFiles")
    out_dir = Path(args.out or f"snapshots/task_{args.task_id}_{payload.get('name', 'unnamed')}")
    out_dir.mkdir(parents=True, exist_ok=True)
    client = get_cos_client(s)
    print(f"task #{args.task_id}  {payload.get('name')}  ->  {out_dir}/")
    for f in files:
        body = cos_read(client, f["path"])
        target = out_dir / f["name"]
        target.write_bytes(body)
        custom = "*" if "/template/0/" not in f["path"] else " "
        print(f"  {custom} {f['name']:<20} {len(body):>8}  {f.get('mtime', '')}")
    print("\n* = user-modified, otherwise from official template")
    print("\n  diff against baseline:")
    print(f"    diff -ru baseline {out_dir}")
