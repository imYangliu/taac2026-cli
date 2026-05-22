"""Evaluation task commands."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from .constants import BASE
from .files import cos_write, filter_unchanged_uploads, get_cos_client
from .session import check_api, get_json, make_session, post_json


def _eval_summary(ev: dict[str, Any]) -> str:
    score = ev.get("score")
    score_s = f"{score:.6f}" if isinstance(score, (int, float)) else "—"
    infer = ev.get("infer_time")
    infer_s = f"{infer:>6}" if infer is not None else "     —"
    return (
        f"#{ev['id']:>5}  {ev['status']:<8}  AUC={score_s:<10}  "
        f"infer={infer_s}s  {ev['name']}  "
        f"({ev.get('update_time', '')[:19]})"
    )


def cmd_eval_list(args: argparse.Namespace) -> None:
    s = make_session()
    data = get_json(s, "/aide/api/evaluation_tasks/", page=1, page_size=args.limit)
    results = data.get("results", [])
    print(f"total: {data.get('count', len(results))}")
    for ev in results:
        print(_eval_summary(ev))

    from datetime import date
    today = date.today().isoformat()
    used = sum(
        1 for ev in results
        if (ev.get("create_time") or "").startswith(today) and ev.get("status") != "failed"
    )
    daily_limit = 3
    print(f"\nquota today ({today}): {used}/{daily_limit} used, {daily_limit - used} remaining")


def cmd_eval_show(args: argparse.Namespace) -> None:
    s = make_session()
    data = get_json(
        s,
        f"/aide/api/evaluation_tasks/{args.id}/",
        referer=f"{BASE}/evaluation/detail/{args.id}",
    )
    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return
    print(_eval_summary(data))
    print(f"  mould_id : {data.get('mould_id')}")
    print(f"  modifier : {data.get('modifier')}")
    print(f"  results  : {data.get('results')}")
    if data.get("error_msg"):
        print(f"  ERROR    : {data['error_msg']}")
    print("  files    :")
    for f in data.get("files", []):
        print(f"    - {f['name']:<20} {f['size']:>8}  {f['path']}")


def cmd_eval_files(args: argparse.Namespace) -> None:
    """Print file paths from an evaluation."""
    s = make_session()
    data = get_json(
        s,
        f"/aide/api/evaluation_tasks/{args.id}/",
        referer=f"{BASE}/evaluation/detail/{args.id}",
    )
    for f in data.get("files", []):
        print(f"{f['size']:>8}  {f['mtime']}  {f['path']}")


def cmd_eval_ready(args: argparse.Namespace) -> None:
    """Show user and competition status needed before creating evaluations."""
    s = make_session()
    user = get_json(s, "/aide/api/app/algo_user/", referer=f"{BASE}/evaluation/create")
    status = get_json(s, "/aide/api/app/check_algo_begin/", referer=f"{BASE}/evaluation/create")
    quota = get_json(
        s,
        "/taskmanagement/api/v1/webtasks/external/queryBusinessResourceStat",
        referer=f"{BASE}/evaluation/create",
    )
    check_api(quota)
    if args.json:
        print(json.dumps({"user": user, "status": status, "quota": quota}, indent=2, ensure_ascii=False))
        return
    qdata = quota.get("data") or {}
    print(f"user     : {user.get('user')} ({user.get('nick_name')})")
    print(f"synced   : {user.get('is_account_synched')}")
    print(f"begin/end: {status.get('begin')}/{status.get('end')}  {status.get('msg') or status.get('msg_en') or ''}")
    print(f"GPU quota: {qdata.get('userQuota')}  free: {qdata.get('userQuotaFree')}")


def get_eval_template(s: Any) -> dict[str, Any]:
    """读取评估创建页的 infer 模板文件；默认就是官方 baseline infer 代码。"""
    return get_json(
        s,
        "/aide/api/evaluation_tasks/get_template/",
        referer=f"{BASE}/evaluation/create",
    )


def cmd_eval_template(args: argparse.Namespace) -> None:
    s = make_session()
    data = get_eval_template(s)
    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return
    files = data.get("inferFiles") or []
    print("evaluation template files:")
    for f in files:
        print(f"  - {f['name']:<20} {f['size']:>8}  {f.get('mtime', '')}  {f['path']}")


def cmd_eval_moulds(args: argparse.Namespace) -> None:
    """List trained models (moulds) that can be evaluated."""
    s = make_session()
    data = get_json(
        s,
        "/aide/api/external/mould/",
        referer=f"{BASE}/evaluation/create",
        page=args.page,
        page_size=args.limit,
        search=args.search,
    )
    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return
    rows = data.get("results") or []
    print(f"total: {data.get('count', len(rows))}")
    for row in rows:
        print(
            f"#{row['id']:<6} {row.get('name', ''):<32} "
            f"task={row.get('task_int_id')} inst={row.get('instance_id')} "
            f"({row.get('create_time', '')})"
        )


def _infer_creator(s: Any) -> str:
    user = get_json(s, "/aide/api/app/algo_user/", referer=f"{BASE}/evaluation/create")
    creator = user.get("user")
    if not creator:
        sys.exit("cannot infer creator; pass --creator ams_2026_...")
    return creator


def _parse_file_spec(spec: str) -> tuple[Path, str]:
    local_s, _sep, remote = spec.partition(":")
    local = Path(local_s)
    if not local.is_file():
        sys.exit(f"not a file: {local}")
    return local, remote or local.name


def _collect_eval_files(from_dir: str | None, file_specs: list[str] | None) -> dict[str, Path]:
    """收集要覆盖或追加的评估文件；同名文件会覆盖模板 inferFiles。"""
    out: dict[str, Path] = {}
    if from_dir:
        root = Path(from_dir)
        if not root.is_dir():
            sys.exit(f"not a directory: {root}")
        for p in sorted(root.iterdir()):
            if p.is_file() and not p.name.startswith("."):
                out[p.name] = p
    for spec in file_specs or []:
        local, remote_name = _parse_file_spec(spec)
        if "/" in remote_name or remote_name in ("", ".", ".."):
            sys.exit(f"remote eval file name must be a basename, got: {remote_name}")
        out[remote_name] = local
    return out


def _file_meta(name: str, key: str, local: Path) -> dict[str, Any]:
    return {
        "name": name,
        "path": key,
        "mtime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(local.stat().st_mtime)),
        "size": local.stat().st_size,
    }


def cmd_eval_create(args: argparse.Namespace) -> None:
    """Create an evaluation task, optionally overriding template infer files."""
    s = make_session()
    creator = args.creator or _infer_creator(s)
    template = get_eval_template(s)
    uploads = _collect_eval_files(args.from_dir, args.file)
    if uploads and not args.force:
        uploads = filter_unchanged_uploads(s, uploads, template.get("inferFiles", []))
    upload_dir = args.upload_dir or (
        f"2026_AMS_ALGO_Competition/{creator}/infer/local--{uuid.uuid4().hex}"
    )

    # 评估模板自带官方 baseline infer 文件；这里只覆盖同名文件或追加新增文件。
    files = {f["name"]: dict(f) for f in template.get("inferFiles", [])}
    for name, local in uploads.items():
        files[name] = _file_meta(name, f"{upload_dir.rstrip('/')}/{name}", local)

    body = {
        "mould_id": args.mould_id,
        "name": args.name or f"eval_{int(time.time() * 1000)}",
        "image_name": args.image_name,
        "creator": creator,
        "files": list(files.values()),
    }

    print(f"creating evaluation {body['name']!r} for mould #{args.mould_id}")
    for name, local in uploads.items():
        print(f"  upload {local} -> {files[name]['path']}")
    if args.dry_run:
        print("\nDRY RUN payload:")
        print(json.dumps(body, indent=2, ensure_ascii=False))
        return

    if uploads:
        client = get_cos_client(s)
        for name, local in uploads.items():
            cos_write(client, files[name]["path"], local.read_bytes())

    data = post_json(
        s,
        "/aide/api/evaluation_tasks/",
        body,
        referer=f"{BASE}/evaluation/create",
    )
    print(json.dumps(data, indent=2, ensure_ascii=False))

    eval_id = data.get("id", "?")
    today = time.strftime("%Y-%m-%d")
    print("\n--- paste into docs/experiments.md ---")
    print(f"""\
## EXP-XXX: {body['name']}
- date: {today}
- evaluation_id: {eval_id}
- mould_id: {args.mould_id}
- leaderboard AUC: (待出分)
- inference_time: (待出分)
- config diff vs baseline:
  - (填写)
- notes: (填写)
""")


def cmd_eval_mould_delete(args: argparse.Namespace) -> None:
    """Delete a published mould by id."""
    s = make_session()
    if not args.yes:
        confirm = input(f"Delete mould #{args.id}? [y/N] ").strip().lower()
        if confirm != "y":
            sys.exit("aborted")
    data = post_json(s, "/aide/api/external/mould/delete/", {"id": args.id},
                     referer=f"{BASE}/model")
    if data.get("code") == "success":
        print(f"deleted mould #{args.id}")
    else:
        sys.exit(f"unexpected response: {data}")


def cmd_eval_log(args: argparse.Namespace) -> None:
    """Print event_log lines for an evaluation task."""
    s = make_session()
    data = get_json(
        s,
        "/aide/api/evaluation_tasks/event_log/",
        referer=f"{BASE}/evaluation",
        task_id=args.id,
        page=args.page,
        limit=args.limit,
    )
    if data.get("code") not in (None, 0):
        raise SystemExit(f"API error: {data.get('msg') or data}")
    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return

    payload = data.get("data") or {}
    items = payload.get("list") or []
    if args.grep:
        pat = re.compile(args.grep)
        items = [
            item for item in items
            if pat.search(item.get("message") or "") or pat.search(item.get("reason") or "")
        ]

    # 接口默认按时间倒序返回；CLI 默认按日志阅读习惯改成正序。
    if not args.newest_first:
        items = list(reversed(items))
        if args.tail and len(items) > args.tail:
            items = items[-args.tail:]
    elif args.tail and len(items) > args.tail:
        items = items[:args.tail]

    for item in items:
        msg = (item.get("message") or item.get("reason") or "").rstrip("\n")
        if args.time:
            print(f"[{item.get('time', '')}] {msg}")
        else:
            print(msg)
