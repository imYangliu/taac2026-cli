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
