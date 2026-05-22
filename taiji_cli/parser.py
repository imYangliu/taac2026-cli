"""Argument parser wiring for the Taiji CLI."""

from __future__ import annotations

import argparse

from .auth import cmd_auth_check, cmd_auth_setup
from .evals import (
    cmd_eval_create,
    cmd_eval_files,
    cmd_eval_list,
    cmd_eval_log,
    cmd_eval_mould_delete,
    cmd_eval_moulds,
    cmd_eval_ready,
    cmd_eval_show,
    cmd_eval_template,
)
from .files import cmd_file_cat, cmd_file_get, cmd_file_put, cmd_file_snapshot
from .instances import cmd_inst_ckpt, cmd_inst_kill, cmd_inst_log, cmd_inst_metrics, cmd_inst_release, cmd_inst_show, cmd_inst_watch
from .rank import cmd_rank
from .raw import cmd_raw
from .tasks import (
    cmd_task_create,
    cmd_task_edit,
    cmd_task_instances,
    cmd_task_list,
    cmd_task_quota,
    cmd_task_show,
    cmd_task_start,
    cmd_task_template,
)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="taiji", description="TAAC2026 platform CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("auth", help="cookies management")
    asub = a.add_subparsers(dest="auth_cmd", required=True)
    asub.add_parser("setup", help="paste cookies from stdin; confirm before overwrite").set_defaults(func=cmd_auth_setup)
    asub.add_parser("check", help="ping API to verify cookies").set_defaults(func=cmd_auth_check)

    e = sub.add_parser("eval", help="evaluation tasks")
    esub = e.add_subparsers(dest="eval_cmd", required=True)
    el = esub.add_parser("list", help="list evaluations"); el.set_defaults(func=cmd_eval_list)
    el.add_argument("--limit", type=int, default=20)
    es = esub.add_parser("show", help="show evaluation detail"); es.set_defaults(func=cmd_eval_show)
    es.add_argument("id", type=int)
    es.add_argument("--json", action="store_true", help="raw JSON")
    ef = esub.add_parser("files", help="list files of an evaluation"); ef.set_defaults(func=cmd_eval_files)
    ef.add_argument("id", type=int)
    er = esub.add_parser("ready", help="show user/status/quota for evaluation creation"); er.set_defaults(func=cmd_eval_ready)
    er.add_argument("--json", action="store_true", help="raw JSON")
    et = esub.add_parser("template", help="show evaluation template infer files"); et.set_defaults(func=cmd_eval_template)
    et.add_argument("--json", action="store_true", help="raw JSON")
    em = esub.add_parser("moulds", help="list trained models available for evaluation"); em.set_defaults(func=cmd_eval_moulds)
    em.add_argument("--page", type=int, default=1)
    em.add_argument("--limit", type=int, default=20)
    em.add_argument("--search", default="")
    em.add_argument("--json", action="store_true", help="raw JSON")
    ec = esub.add_parser("create", help="create an evaluation task")
    ec.set_defaults(func=cmd_eval_create)
    ec.add_argument("--mould-id", type=int, required=True, help="model/mould id from `eval moulds`")
    ec.add_argument("--name", default=None, help="default: eval_<timestamp_ms>")
    ec.add_argument("--image-name", default="", help="default empty")
    ec.add_argument("--creator", default=None, help="default: current algo user")
    ec.add_argument("--from-dir", default=None, help="upload every non-hidden direct file in DIR")
    ec.add_argument(
        "--file",
        action="append",
        default=[],
        help="upload one infer file; use LOCAL[:REMOTE_NAME], repeatable",
    )
    ec.add_argument("--upload-dir", default=None, help="full COS prefix for uploaded files")
    ec.add_argument(
        "--force",
        action="store_true",
        help="upload local files even if they match the official template byte-for-byte",
    )
    ec.add_argument("--dry-run", action="store_true", help="print uploads and POST body only")
    emd = esub.add_parser("mould-delete", help="delete a published mould")
    emd.set_defaults(func=cmd_eval_mould_delete)
    emd.add_argument("id", type=int, help="mould id from `eval moulds`")
    emd.add_argument("-y", "--yes", action="store_true", help="skip confirmation prompt")
    elog = esub.add_parser("log", help="show event log of an evaluation"); elog.set_defaults(func=cmd_eval_log)
    elog.add_argument("id", type=int, help="evaluation task id")
    elog.add_argument("--tail", type=int, default=200, help="show last N log entries (default 200; 0 = all)")
    elog.add_argument("--grep", default=None, help="regex filter")
    elog.add_argument("--page", type=int, default=1)
    elog.add_argument("--limit", type=int, default=1000)
    elog.add_argument("--time", action="store_true", help="prefix each entry with platform event time")
    elog.add_argument("--newest-first", action="store_true", help="keep API order instead of chronological order")
    elog.add_argument("--json", action="store_true", help="raw JSON")

    t = sub.add_parser("task", help="training tasks")
    tsub = t.add_subparsers(dest="task_cmd", required=True)
    tl = tsub.add_parser("list", help="list training tasks"); tl.set_defaults(func=cmd_task_list)
    tl.add_argument("--limit", type=int, default=20)
    ts = tsub.add_parser("show", help="show task detail"); ts.set_defaults(func=cmd_task_show)
    ts.add_argument("id", type=int)
    ts.add_argument("--json", action="store_true", help="raw JSON")
    tq = tsub.add_parser("quota", help="show available GPU quota"); tq.set_defaults(func=cmd_task_quota)
    tt = tsub.add_parser("template", help="show create-task template")
    tt.set_defaults(func=cmd_task_template)
    tt.add_argument("--label", default="", help="template label filter (default empty)")
    tt.add_argument("--json", action="store_true", help="raw JSON")
    tc = tsub.add_parser("create", help="upload local files and create a training task")
    tc.set_defaults(func=cmd_task_create)
    tc.add_argument("--name", required=True, help="task name")
    tc.add_argument("--description", default=None, help="default: same as --name")
    tc.add_argument("--from-dir", default=None, help="upload every non-hidden direct file in DIR")
    tc.add_argument(
        "--file",
        action="append",
        default=[],
        help="upload one file; use LOCAL[:REMOTE_NAME], repeatable",
    )
    tc.add_argument("--label", default="", help="template label filter and task label")
    tc.add_argument("--template-id", type=int, default=None, help="default: template id")
    tc.add_argument("--model-name", default=None, help="default: template modelName")
    tc.add_argument("--train-data-name", default=None, help="default: template trainDataName")
    tc.add_argument("--gpu", type=int, default=1, help="hostGpuNum (default 1)")
    tc.add_argument("--owner", default=None, help="upload namespace, e.g. ams_2026_...")
    tc.add_argument("--upload-dir", default=None, help="full COS prefix for uploaded files")
    tc.add_argument(
        "--force",
        action="store_true",
        help="upload local files even if they match the official template byte-for-byte",
    )
    tc.add_argument("--dry-run", action="store_true", help="print uploads and POST body only")
    tc.add_argument("--no-start", action="store_true", help="create task but do not auto-start")
    te = tsub.add_parser("edit", help="update files of an existing task in-place and restart")
    te.set_defaults(func=cmd_task_edit)
    te.add_argument("id", type=int, help="numeric task id (from `task list`)")
    te.add_argument("--note", default=None, help="追加到原 description 末尾的修复说明（可选）")
    te.add_argument("--from-dir", default=None, help="upload every non-hidden direct file in DIR")
    te.add_argument(
        "--file",
        action="append",
        default=[],
        help="upload one file; use LOCAL[:REMOTE_NAME], repeatable",
    )
    te.add_argument("--owner", default=None, help="upload namespace, e.g. ams_2026_...")
    te.add_argument("--upload-dir", default=None, help="full COS prefix for uploaded files")
    te.add_argument("--force", action="store_true",
                    help="upload even if local file matches what's already in the task")
    te.add_argument("--no-start", action="store_true", help="update task but do not auto-start")
    te.add_argument("--dry-run", action="store_true", help="print uploads and PUT body only")
    tr = tsub.add_parser("start", help="start a created training task")
    tr.set_defaults(func=cmd_task_start)
    tr.add_argument("task", help="long taskId or numeric web task id")
    tr.add_argument("--dry-run", action="store_true", help="print request only")
    tr.add_argument("--json", action="store_true", help="raw JSON response")
    ti = tsub.add_parser("instances", help="list instance runs of a task")
    ti.set_defaults(func=cmd_task_instances)
    ti.add_argument("task_id", help="long taskId or numeric task id (from `task show`)")
    ti.add_argument("--limit", type=int, default=20)

    inst = sub.add_parser("inst", help="training instance (one run) ops")
    isub = inst.add_subparsers(dest="inst_cmd", required=True)
    ish = isub.add_parser("show", help="summary: ckpts + latest/best metric"); ish.set_defaults(func=cmd_inst_show)
    ish.add_argument("id", help="long taskId, numeric task id, or 32-char hex instance id")
    il = isub.add_parser("log", help="pod_log lines"); il.set_defaults(func=cmd_inst_log)
    il.add_argument("id", help="long taskId, numeric task id, or 32-char hex instance id")
    il.add_argument("--tail", type=int, default=200, help="last N lines (default 200; 0 = all)")
    il.add_argument("--grep", default=None, help="regex filter")
    im = isub.add_parser("metrics", help="tensorboard metric series"); im.set_defaults(func=cmd_inst_metrics)
    im.add_argument("id", help="long taskId, numeric task id, or 32-char hex instance id")
    im.add_argument("--tag", default=None, help="filter to one tag (e.g. AUC)")
    im.add_argument("--last", type=int, default=20, help="show last N points (0 = all)")
    ic = isub.add_parser("ckpt", help="list checkpoints"); ic.set_defaults(func=cmd_inst_ckpt)
    ic.add_argument("id", help="long taskId, numeric task id, or 32-char hex instance id")
    iw = isub.add_parser("watch", help="repeat `inst show` with interval"); iw.set_defaults(func=cmd_inst_watch)
    iw.add_argument("id", help="long taskId, numeric task id, or 32-char hex instance id")
    iw.add_argument("--interval", type=int, default=60, help="seconds between refresh")
    ik = isub.add_parser("kill", help="forcefully terminate a running instance"); ik.set_defaults(func=cmd_inst_kill)
    ik.add_argument("id", help="long taskId, numeric task id, or 32-char hex instance id")
    ik.add_argument("--yes", "-y", action="store_true", help="skip confirmation prompt")
    ir = isub.add_parser("release", help="publish a checkpoint to Model List (required before eval create)")
    ir.set_defaults(func=cmd_inst_release)
    ir.add_argument("id", help="long taskId, numeric task id, or 32-char hex instance id")
    ir.add_argument("--ckpt", default=None, help="checkpoint name; auto-detected if only one exists")
    ir.add_argument("--name", default=None, help="mould display name (default: ckpt name)")
    ir.add_argument("--desc", default=None, help="mould description")

    rk = sub.add_parser("rank", help="competition leaderboard")
    rk.set_defaults(func=cmd_rank)
    rk.add_argument("--page", type=int, default=1)
    rk.add_argument("--size", type=int, default=20)
    rk.add_argument("--all", dest="student", action="store_false", help="all participants (default: student-only)")
    rk.add_argument("--json", action="store_true")
    rk.set_defaults(student=True)

    fl = sub.add_parser("file", help="download files (COS bucket)")
    fsub = fl.add_subparsers(dest="file_cmd", required=True)
    fc = fsub.add_parser("cat", help="print file content to stdout"); fc.set_defaults(func=cmd_file_cat)
    fc.add_argument("path", help="COS object key (e.g. 2026_AMS_ALGO_Competition/...)")
    fg = fsub.add_parser("get", help="download single file"); fg.set_defaults(func=cmd_file_get)
    fg.add_argument("path")
    fg.add_argument("--out", default=None, help="local path (default: basename)")
    fp = fsub.add_parser("put", help="upload single local file to a COS key"); fp.set_defaults(func=cmd_file_put)
    fp.add_argument("local", help="local file path")
    fp.add_argument("--key", required=True, help="destination COS object key")
    fs = fsub.add_parser("snapshot", help="dump all trainFiles of a task"); fs.set_defaults(func=cmd_file_snapshot)
    fs.add_argument("task_id", type=int, help="numeric task id (e.g. 63009)")
    fs.add_argument("--out", default=None, help="output dir (default: snapshots/task_<id>_<name>)")

    raw = sub.add_parser("raw", help="hit an arbitrary endpoint (for API exploration)")
    raw.set_defaults(func=cmd_raw)
    raw.add_argument("path", help="path or full URL, e.g. /taskmanagement/api/v1/instances/<id>")
    raw.add_argument("--method", "-X", default=None, help="default GET, or POST if --data given")
    raw.add_argument("--referer", "-r", default=None)
    raw.add_argument("--data", "-d", default=None, help="JSON body (e.g. '{\"page\":0}')")

    return p


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)
