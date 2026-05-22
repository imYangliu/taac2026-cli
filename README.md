# taac2026-cli

Command-line tool for the [Taiji](https://taiji.algo.qq.com) training platform, built for TAAC 2026 (腾讯 × KDD 广告算法大赛).

Wraps the Taiji REST API to manage training jobs, monitor instances, publish checkpoints, create evaluations, and browse leaderboards — all from the terminal.

## Install

```bash
pip install requests cos-python-sdk-v5
```

No package install needed — just clone and run directly.

## Usage

```bash
python taiji.py --help
```

See [docs/taiji-cli.md](docs/taiji-cli.md) for the full usage guide.

## Auth

```bash
python taiji.py auth setup   # paste browser document.cookie
python taiji.py auth check
```

Cookies are stored at `~/.taiji/cookies.txt` (mode 600). **Never commit this file.**

## Quick reference

```bash
# Tasks
python taiji.py task list
python taiji.py task create --name my_exp --file model.py --dry-run
python taiji.py task edit <id> --file fixed.py
python taiji.py task start <id>

# Instances
python taiji.py inst show <id>
python taiji.py inst log <id> --tail 200 --grep 'AUC|ERROR'
python taiji.py inst watch <id>
python taiji.py inst release <id> --name my_mould

# Evals
python taiji.py eval moulds
python taiji.py eval create --mould-id <id> --dry-run
python taiji.py eval show <id>

# Misc
python taiji.py rank --size 20
python taiji.py raw /aide/api/some/path
```

## How it was built

The platform has no public API docs. The entire CLI was built by:

1. Opening Chrome DevTools, manually walking through the platform UI once
2. Copying requests as cURL from the Network tab
3. Feeding the cURLs to an AI coding assistant (Codex / Claude Code) to generate the implementation
4. Testing, finding edge cases, iterating on both the CLI and `CLAUDE.md`

Cookie auth is easiest with the [Cookie-Editor](https://cookie-editor.com/) browser extension — one click to export, paste into `python taiji.py auth setup`.

The first manual pass is worth it: you build a mental model of the platform flow and keep token costs low. Full automation is possible but only pays off once you know the terrain.

See [docs/methodology.md](docs/methodology.md) for the full walkthrough.

## Structure

```
taiji.py          # entry point
taiji_cli/
  auth.py         # auth setup & check
  session.py      # HTTP helpers (requests + cookie jar)
  tasks.py        # task create / edit / start / list / show
  instances.py    # inst show / log / metrics / watch / release
  evals.py        # eval create / list / show / log / moulds
  files.py        # file cat / get / put / snapshot (COS)
  rank.py         # leaderboard
  raw.py          # raw API explorer
  parser.py       # argparse wiring
  constants.py    # BASE URL, COS config, paths
```
