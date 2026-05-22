"""Training task commands."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from .constants import BASE
from .files import cos_write, filter_unchanged_uploads, get_cos_client
from .session import check_api, get_json, make_session, post_json, put_json


def _task_summary(t: dict[str, Any]) -> str:
    status = t.get("status") or t.get("jzStatus") or "—"
    name = t.get("name") or "—"
    return (
        f"#{t['id']:>5}  {status:<10}  {name:<28}  "
        f"({t.get('createTime', '')[:19]})  {t.get('description', '')}"
    )


def cmd_task_list(args: argparse.Namespace) -> None:
    s = make_session()
    data = get_json(
        s,
        "/taskmanagement/api/v1/webtasks/external/task",
        referer=f"{BASE}/training",
        pageNum=0,
        pageSize=args.limit,
    )
    check_api(data)
    items = data.get("data", [])
    print(f"total: {data.get('totalCount', len(items))}")
    for t in items:
        print(_task_summary(t))


def cmd_task_show(args: argparse.Namespace) -> None:
    s = make_session()
    data = get_json(
        s,
        f"/taskmanagement/api/v1/webtasks/external/task/{args.id}",
        referer=f"{BASE}/training",
    )
    payload = data.get("data", data)
    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return
    print(_task_summary(payload))
    print(f"  taskId    : {payload.get('taskId')}")
    print(f"  template  : {payload.get('templateId')}")
    print(f"  GPU       : {payload.get('hostGpuNum')}/{payload.get('totalHostGpuNum')}")
    print(f"  data      : {payload.get('trainDataName')}")
    print("  files     :")
    for f in payload.get("trainFiles", []):
        custom = "*" if "/template/0/" not in f.get("path", "") else " "
        print(f"    {custom} {f['name']:<20} {f['size']:>8}  {f.get('mtime', '')}")
    print("    (* = user-modified, otherwise from official template)")


def get_template(s: Any, label: str = "") -> dict[str, Any]:
    """读取创建训练任务页面使用的官方模板和默认 trainFiles。"""
    data = get_json(
        s,
        "/taskmanagement/api/v1/webtasks/external/template",
        referer=f"{BASE}/training/create",
        label=label,
    )
    check_api(data)
    return data.get("data", data)


def cmd_task_quota(_args: argparse.Namespace) -> None:
    """查询当前账号的 GPU 总配额和空闲配额。"""
    s = make_session()
    data = get_json(
        s,
        "/taskmanagement/api/v1/webtasks/external/queryBusinessResourceStat",
        referer=f"{BASE}/training/create",
    )
    check_api(data)
    payload = data.get("data", data)
    print(f"GPU quota: {payload.get('userQuota')}  free: {payload.get('userQuotaFree')}")


def cmd_task_template(args: argparse.Namespace) -> None:
    """展示训练任务模板，便于确认默认代码文件和数据集名称。"""
    s = make_session()
    payload = get_template(s, args.label)
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return
    print(f"template #{payload.get('id')}  {payload.get('name')}")
    print(f"  model    : {payload.get('modelName')}")
    print(f"  data     : {payload.get('trainDataName')}")
    print(f"  GPU      : {payload.get('hostGpuNum')}/{payload.get('totalHostGpuNum')}")
    print(f"  label    : {payload.get('label')}")
    print("  files    :")
    for f in payload.get("trainFiles", []):
        print(f"    - {f['name']:<20} {f['size']:>8}  {f.get('mtime', '')}  {f['path']}")


def _infer_owner(s: Any) -> str:
    """从已有任务中推断 COS 上传路径里的账号命名空间。"""
    data = get_json(
        s,
        "/taskmanagement/api/v1/webtasks/external/task",
        referer=f"{BASE}/training",
        pageNum=0,
        pageSize=1,
    )
    check_api(data)
    for task in data.get("data", []):
        if task.get("creator"):
            return task["creator"]
        groups = task.get("userGroup") or []
        if groups:
            return groups[0]
    sys.exit("cannot infer upload owner; pass --owner ams_2026_...")


def _parse_file_spec(spec: str) -> tuple[Path, str]:
    local_s, _sep, remote = spec.partition(":")
    local = Path(local_s)
    if not local.is_file():
        sys.exit(f"not a file: {local}")
    return local, remote or local.name


def _collect_task_files(from_dir: str | None, file_specs: list[str] | None) -> dict[str, Path]:
    """收集本次要覆盖上传的训练文件；同名文件以后传的为准。"""
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
            sys.exit(f"remote task file name must be a basename, got: {remote_name}")
        out[remote_name] = local
    return out


def _file_meta(name: str, key: str, local: Path) -> dict[str, Any]:
    return {
        "name": name,
        "path": key,
        "mtime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(local.stat().st_mtime)),
        "size": local.stat().st_size,
    }


def cmd_task_create(args: argparse.Namespace) -> None:
    """上传本地代码文件，并把上传后的 COS key 写入新任务的 trainFiles。"""
    s = make_session()
    template = get_template(s, args.label)
    uploads = _collect_task_files(args.from_dir, args.file)
    if not uploads:
        sys.exit("no local files selected; use --from-dir DIR or --file LOCAL[:NAME]")

    if not args.force:
        uploads = filter_unchanged_uploads(s, uploads, template.get("trainFiles", []))
        if not uploads:
            print("nothing to upload: all selected files match the official template")
            return

    upload_dir = args.upload_dir or (
        f"2026_AMS_ALGO_Competition/{args.owner or _infer_owner(s)}/train/local--{uuid.uuid4().hex}"
    )
    # Taiji 创建任务的模板里自带官方 baseline 文件。
    # 每次提交只需要覆盖改过的同名文件，或追加新增文件；未覆盖的文件继续使用模板 baseline。
    train_files = {f["name"]: dict(f) for f in template.get("trainFiles", [])}
    for name, local in uploads.items():
        train_files[name] = _file_meta(name, f"{upload_dir.rstrip('/')}/{name}", local)

    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL
        ).strip().decode()
        name_with_commit = f"{args.name}-{commit}"
        try:
            commit_msg = subprocess.check_output(
                ["git", "log", "-1", "--pretty=%s", commit], stderr=subprocess.DEVNULL
            ).strip().decode()
        except Exception:
            commit_msg = ""
    except Exception:
        name_with_commit = args.name
        commit_msg = ""

    changed = ", ".join(sorted(uploads.keys()))
    parts = []
    if commit_msg:
        parts.append(commit_msg)
    if args.description:
        parts.append(args.description)
    parts.append(f"files: {changed}")
    description = "; ".join(parts)

    body = {
        "templateId": args.template_id or template.get("id"),
        "name": name_with_commit,
        "description": description,
        "modelName": args.model_name or template.get("modelName") or "Baseline Model Name",
        "trainDataName": args.train_data_name or template.get("trainDataName") or "TencentGR",
        "hostGpuNum": args.gpu,
        "label": args.label,
        "trainFiles": list(train_files.values()),
    }

    print(f"creating task {name_with_commit!r} with {len(uploads)} uploaded file(s)")
    for name, local in uploads.items():
        print(f"  upload {local} -> {train_files[name]['path']}")
    if args.dry_run:
        print("\nDRY RUN payload:")
        print(json.dumps(body, indent=2, ensure_ascii=False))
        return

    client = get_cos_client(s)
    for name, local in uploads.items():
        cos_write(client, train_files[name]["path"], local.read_bytes())

    data = post_json(
        s,
        "/taskmanagement/api/v1/webtasks/external/task",
        body,
        referer=f"{BASE}/training/create",
    )
    check_api(data)
    payload = data.get("data", data)
    print("created:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))

    if not args.no_start:
        task_id = payload.get("taskId") or payload.get("taskID")
        if task_id:
            time.sleep(3)
            start_data = post_json(s, f"/taskmanagement/api/v1/webtasks/{task_id}/start",
                                   {}, referer=f"{BASE}/training")
            check_api(start_data)
            print(f"started: {task_id}")


def cmd_task_edit(args: argparse.Namespace) -> None:
    """上传修复后的文件，就地 PUT 更新已有任务的 trainFiles，而不创建新任务。"""
    s = make_session()
    data = get_json(
        s,
        f"/taskmanagement/api/v1/webtasks/external/task/{args.id}",
        referer=f"{BASE}/training/edit/{args.id}",
    )
    check_api(data)
    payload = data.get("data", data)

    uploads = _collect_task_files(args.from_dir, args.file)
    if not uploads:
        sys.exit("no local files selected; use --from-dir DIR or --file LOCAL[:NAME]")

    if not args.force:
        uploads = filter_unchanged_uploads(s, uploads, payload.get("trainFiles", []))
        if not uploads:
            print("nothing to upload: all selected files already match the task")
            return

    upload_dir = args.upload_dir or (
        f"2026_AMS_ALGO_Competition/{args.owner or _infer_owner(s)}/train/local--{uuid.uuid4().hex}"
    )
    train_files = {f["name"]: dict(f) for f in payload.get("trainFiles", [])}
    for name, local in uploads.items():
        train_files[name] = _file_meta(name, f"{upload_dir.rstrip('/')}/{name}", local)

    _WRITABLE = {"templateId", "name", "description", "modelName",
                 "trainDataName", "hostGpuNum", "label"}
    body = {k: payload[k] for k in _WRITABLE if k in payload}
    body["trainFiles"] = list(train_files.values())
    if args.note:
        body["description"] = (payload.get("description") or "") + f"；修复：{args.note}"

    print(f"editing task #{args.id} {payload.get('name')!r} with {len(uploads)} file(s)")
    for name, local in uploads.items():
        print(f"  upload {local} -> {train_files[name]['path']}")
    if args.dry_run:
        print("\nDRY RUN payload:")
        print(json.dumps(body, indent=2, ensure_ascii=False))
        return

    client = get_cos_client(s)
    for name, local in uploads.items():
        cos_write(client, train_files[name]["path"], local.read_bytes())

    check_api(put_json(s, f"/taskmanagement/api/v1/webtasks/external/task/{args.id}",
                       body, referer=f"{BASE}/training/edit/{args.id}"))
    print("updated.")

    if not args.no_start:
        task_id = payload.get("taskId") or payload.get("taskID")
        if task_id:
            time.sleep(1)
            start_data = post_json(s, f"/taskmanagement/api/v1/webtasks/{task_id}/start",
                                   {}, referer=f"{BASE}/training")
            check_api(start_data)
            print(f"started: {task_id}")


def _find_task_by_name(s: Any, name: str) -> str:
    """Search task list for an exact name match; return long taskId or exit."""
    page = 0
    while True:
        data = get_json(s, "/taskmanagement/api/v1/webtasks/external/task",
                        referer=f"{BASE}/training", pageNum=page, pageSize=50)
        check_api(data)
        items = data.get("data") or []
        for t in items:
            if t.get("name") == name:
                task_id = t.get("taskId") or t.get("taskID")
                if not task_id:
                    sys.exit(f"task {name!r} found but has no taskId")
                return task_id
        total = data.get("totalCount", 0)
        if (page + 1) * 50 >= total or not items:
            sys.exit(f"no task named {name!r}")
        page += 1


def _resolve_task_id(s: Any, task: str) -> str:
    """Accept numeric id, long taskId, or task name; return long taskId."""
    if task.isdigit():
        data = get_json(s, f"/taskmanagement/api/v1/webtasks/external/task/{task}",
                        referer=f"{BASE}/training")
        check_api(data)
        payload = data.get("data", data)
        task_id = payload.get("taskId") or payload.get("taskID")
        if not task_id:
            sys.exit(f"task {task} has no taskId in API response")
        return task_id
    if task.startswith("angel_training_") or len(task) > 50:
        return task
    return _find_task_by_name(s, task)


def cmd_task_start(args: argparse.Namespace) -> None:
    """调用 start 接口启动已创建的训练任务。"""
    s = make_session()
    task_id = _resolve_task_id(s, args.task)
    path = f"/taskmanagement/api/v1/webtasks/{task_id}/start"
    if args.dry_run:
        print(f"DRY RUN: POST {path} body={{}}")
        return
    data = post_json(s, path, {}, referer=f"{BASE}/training")
    check_api(data)
    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return
    payload = data.get("data", data)
    print(f"started task: {task_id}")
    if payload not in (None, {}, []):
        print(json.dumps(payload, indent=2, ensure_ascii=False))


def _instance_summary(inst: dict[str, Any]) -> str:
    end = inst.get("current_status_start_date", "")
    return (
        f"  {inst['id']}  {inst.get('inner_status', '?'):<8}  "
        f"start={inst.get('start_date', '?')}  end={end}  "
        f"result={inst.get('result') or '—'}"
    )


def cmd_task_instances(args: argparse.Namespace) -> None:
    s = make_session()
    task_id = _resolve_task_id(s, args.task_id)
    body = {"desc": True, "orderBy": "create", "page": 0, "size": args.limit, "task_id": task_id}
    data = post_json(
        s,
        "/taskmanagement/api/v1/instances/list",
        body,
        referer=f"{BASE}/training",
    )
    check_api(data)
    items = data.get("data", [])
    print(f"task {task_id}")
    print(f"total instances: {data.get('totalCount', len(items))}")
    for inst in items:
        print(_instance_summary(inst))
