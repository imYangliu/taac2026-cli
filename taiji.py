"""TAAC2026 / Taiji platform CLI.

Client for taiji.algo.qq.com — list / inspect evaluations and training tasks,
monitor running instances, and create training tasks from uploaded code files.

Cookies live at ``~/.taiji/cookies.txt`` (mode 600). ``auth setup`` accepts
either ``document.cookie`` output or one ``key=value`` per line.

Usage:
    taiji auth setup        # paste cookies from stdin
    taiji auth check        # ping API to verify cookies still valid

    taiji eval list [--limit N]
    taiji eval show <id>
    taiji eval files <id>
    taiji eval moulds [--search NAME]
    taiji eval create --mould-id ID [--file LOCAL[:NAME]]
    taiji eval log <id> [--tail N] [--grep PATTERN]

    taiji task list [--limit N]
    taiji task show <id>
    taiji task quota                  # GPU quota/free quota
    taiji task template [--label L]    # training template + default files
    taiji task create --name NAME [--from-dir DIR] [--file LOCAL[:NAME]]
    taiji task start <task_id|id>       # start a created training task
    taiji task instances <task_id>     # list runs of a task (taskId is the long string)

    taiji inst show <inst_id>          # summary: ckpt + last AUC
    taiji inst log <inst_id> [--tail N] [--grep PATTERN]
    taiji inst metrics <inst_id> [--tag AUC] [--last N]
    taiji inst ckpt <inst_id>
    taiji inst watch <inst_id> [--interval 60]    # repeat inst show

    taiji rank [--page 1] [--size 20]  # competition leaderboard (algo.qq.com)

    taiji file cat <path>              # print file content to stdout
    taiji file get <path> [--out FILE] # download a single file
    taiji file put <local> --key <path> # upload a single file to COS
    taiji file snapshot <task_id> [--out DIR]  # dump all trainFiles of a task

    taiji raw <path> [-d JSON] [-X METHOD] [-r REFERER]   # debug helper
"""

from __future__ import annotations

from taiji_cli.parser import main


if __name__ == "__main__":
    main()
