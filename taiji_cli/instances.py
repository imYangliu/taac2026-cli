"""Training instance monitoring commands."""

from __future__ import annotations

import argparse
import re
import sys
import time
from typing import Any

from .constants import BASE
from .session import check_api, get_json, make_session, post_json
from .tasks import _find_task_by_name


def _to_task_id(s: Any, raw_id: str) -> str:
    """Resolve to long taskId: numeric id → API lookup; task name → search; passthrough otherwise."""
    if raw_id.isdigit():
        data = get_json(s, f"/taskmanagement/api/v1/webtasks/external/task/{raw_id}", referer=f"{BASE}/training")
        check_api(data)
        payload = data.get("data", data)
        task_id = payload.get("taskId") or payload.get("taskID")
        if not task_id:
            sys.exit(f"task {raw_id} has no taskId in API response")
        return task_id
    if raw_id.startswith("angel_training_") or len(raw_id) > 50:
        return raw_id
    return _find_task_by_name(s, raw_id)


def _resolve_inst_id(s: Any, raw_id: str) -> str:
    """Resolve any ID format (32-char hex / long taskId / numeric task id) to 32-char hex instance id."""
    if re.fullmatch(r"[0-9a-f]{32}", raw_id):
        return raw_id
    task_id = _to_task_id(s, raw_id)
    data = post_json(
        s,
        "/taskmanagement/api/v1/instances/list",
        {"desc": True, "orderBy": "create", "page": 0, "size": 1, "task_id": task_id},
        referer=f"{BASE}/training",
    )
    check_api(data)
    items = data.get("data") or []
    if not items:
        sys.exit(f"no instances found for task {raw_id}")
    return items[0]["id"]


def _inst_get(s: Any, inst_id: str, action: str, *, external: bool = True) -> Any:
    prefix = "/instances/external" if external else "/instances"
    data = get_json(
        s, f"/taskmanagement/api/v1{prefix}/{inst_id}/{action}",
        referer=f"{BASE}/training",
    )
    check_api(data)
    return data


def _summarize_tf_events(tfe: dict[str, Any]) -> list[tuple[str, int, float, int, float, int]]:
    """Extract (title, last_step, last_val, best_step, best_val, n_points) per series."""
    out: list[tuple[str, int, float, int, float, int]] = []
    for tag, series_list in tfe.items():
        for s_obj in series_list:
            title = (s_obj.get("title") or [tag])[0]
            steps = s_obj.get("date") or []
            values = (s_obj.get("value") or [[]])[0]
            if not steps or not values:
                continue
            last_step, last_val = steps[-1], values[-1]
            best_idx = max(range(len(values)), key=lambda i: values[i])
            best_step, best_val = steps[best_idx], values[best_idx]
            out.append((title, last_step, last_val, best_step, best_val, len(steps)))
    return out


def cmd_inst_show(args: argparse.Namespace) -> None:
    s = make_session()
    inst_id = _resolve_inst_id(s, args.id)
    ckpts = _inst_get(s, inst_id, "get_ckpt").get("data") or []
    tfe = (_inst_get(s, inst_id, "tf_events").get("data") or {}).get("data") or {}

    print(f"instance {inst_id}")
    print(f"  checkpoints ({len(ckpts)}):")
    for c in ckpts:
        sz = c.get("ckpt_file_size") or 0
        size_str = f"{sz / 1024 / 1024:.0f} MB" if sz else "—"
        flag = "✓" if c.get("status") else "✗"
        print(f"    {flag} {c.get('ckpt', '?')}  ({size_str}, {(c.get('create_time') or '')[:19]})")
    summaries = _summarize_tf_events(tfe)
    if not summaries:
        print("  metrics: (no tf_events yet)")
        return
    print("  metrics:")
    for title, last_step, last_v, best_step, best_v, n in summaries:
        print(f"    {title:<20}  last(step={last_step:>7}, v={last_v:.6f})  "
              f"best(step={best_step:>7}, v={best_v:.6f})  pts={n}")


def cmd_inst_log(args: argparse.Namespace) -> None:
    s = make_session()
    inst_id = _resolve_inst_id(s, args.id)
    data = get_json(
        s, f"/taskmanagement/api/v1/instances/{inst_id}/pod_log",
        referer=f"{BASE}/training",
    )
    check_api(data)
    lines = [ln for ln in (data.get("data") or []) if ln.strip()]
    if not lines:
        print("(no pod logs yet)")
        return
    if args.grep:
        pat = re.compile(args.grep)
        lines = [ln for ln in lines if pat.search(ln)]
    if args.tail and len(lines) > args.tail:
        lines = lines[-args.tail:]
    for ln in lines:
        print(ln)


def cmd_inst_metrics(args: argparse.Namespace) -> None:
    s = make_session()
    inst_id = _resolve_inst_id(s, args.id)
    tfe = (_inst_get(s, inst_id, "tf_events").get("data") or {}).get("data") or {}
    if not tfe:
        sys.exit("no tf_events data yet")
    for tag, series_list in tfe.items():
        if args.tag and tag != args.tag:
            continue
        for s_obj in series_list:
            title = (s_obj.get("title") or [tag])[0]
            steps = s_obj.get("date") or []
            values = (s_obj.get("value") or [[]])[0]
            if not steps:
                continue
            n = min(args.last, len(steps)) if args.last else len(steps)
            print(f"\n{title}  ({len(steps)} pts, showing last {n}):")
            for step, v in list(zip(steps, values))[-n:]:
                print(f"  step={step:>8}  val={v:.6f}")


def cmd_inst_ckpt(args: argparse.Namespace) -> None:
    s = make_session()
    inst_id = _resolve_inst_id(s, args.id)
    items = _inst_get(s, inst_id, "get_ckpt").get("data") or []
    print(f"instance {inst_id}: {len(items)} checkpoint(s)")
    for c in items:
        sz = c.get("ckpt_file_size") or 0
        size_str = f"{sz / 1024 / 1024:.0f} MB" if sz else "—"
        flag = "✓" if c.get("status") else "✗"
        print(f"  {flag} {c.get('ckpt', '?')}  ({size_str}, {(c.get('create_time') or '')[:19]})")


def cmd_inst_release(args: argparse.Namespace) -> None:
    """Release (publish) a checkpoint to the Model List so it can be evaluated."""
    s = make_session()
    inst_id = _resolve_inst_id(s, args.id)
    # Fetch available checkpoints to let user omit --ckpt when there's only one
    items = _inst_get(s, inst_id, "get_ckpt").get("data") or []
    if not items:
        sys.exit("no checkpoints found for this instance")
    ckpt_name = args.ckpt
    if not ckpt_name:
        if len(items) > 1:
            names = [c.get("ckpt", "?") for c in items]
            sys.exit(f"multiple checkpoints; specify --ckpt:\n  " + "\n  ".join(names))
        ckpt_name = items[0].get("ckpt", "")
    name = args.name or ckpt_name
    body = {"name": name, "desc": args.desc or f"{name} desc", "ckpt": ckpt_name}
    referer = f"{BASE}/training/ckpt/_/{inst_id}"
    r = s.post(
        f"{BASE}/taskmanagement/api/v1/instances/external/{inst_id}/release_ckpt",
        headers={"Origin": BASE, "Referer": referer, "Content-Type": "application/json"},
        json=body, timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    code = (data.get("error") or {}).get("code", "")
    if code == "SUCCESS":
        print(f"released: {ckpt_name!r} as {name!r}")
        print("run `eval moulds` to confirm, then `eval create --mould-id <id>`")
    else:
        msg = (data.get("error") or {}).get("message", str(data))
        print(f"note: {msg}")


def cmd_inst_kill(args: argparse.Namespace) -> None:
    """Forcefully terminate a running instance."""
    s = make_session()
    inst_id = _resolve_inst_id(s, args.id)
    if not args.yes:
        confirm = input(f"Kill instance {inst_id}? [y/N] ").strip().lower()
        if confirm != "y":
            sys.exit("aborted")
    r = s.post(
        f"{BASE}/taskmanagement/api/v1/instances/{inst_id}/kill",
        headers={"Origin": BASE, "Referer": f"{BASE}/training", "Content-Type": "application/json"},
        json={}, timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    code = (data.get("error") or {}).get("code", "")
    if code == "SUCCESS":
        print(f"killed: {inst_id}")
    else:
        msg = (data.get("error") or {}).get("message", str(data))
        print(f"response: {msg}")


def cmd_inst_watch(args: argparse.Namespace) -> None:
    """Repeatedly call inst show, sleeping `interval` seconds between."""
    s = make_session()
    args.id = _resolve_inst_id(s, args.id)
    try:
        while True:
            ts = time.strftime("%Y-%m-%d %H:%M:%S")
            print(f"=== {ts} ===")
            try:
                cmd_inst_show(args)
            except SystemExit:
                raise
            except Exception as e:  # network blips shouldn't kill the watch
                print(f"  (transient error: {e})")
            print(f"\nnext refresh in {args.interval}s (Ctrl-C to stop)\n")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nstopped.")
