# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 仓库定位

TAAC 2026 腾讯 × KDD 广告算法大赛参赛仓库。任务是 **pCVR 二分类**（正样本 = `label_type == 2`），
所有字段都已匿名化（`_<数字>`，无语义）。模型需要在同一架构下融合 4 个用户行为序列域
（a/b/c/d，长度约 682/1233/333/1990）以及 scalar/list 整数特征 + 稠密浮点 list 特征。

## 两套并行的代码根目录 — 不要混用

- `baseline/` — 官方 PCVRHyFormer 参考实现（RoPE + 混合 NS tokenizer + 多域序列编码器 +
  RankMixer）。**默认视为只读**，除非明确要求改它。入口 `baseline/train.py`，运行脚本
  `baseline/run.sh`（默认 `--ns_tokenizer_type rankmixer`；切换到 `group` tokenizer 需要
  `ns_groups.json` 并设 `--num_queries 1`，以满足 `d_model % T == 0`）。

Taiji 平台的训练模板里已经预置了 baseline 的全部文件；通过 `scripts/taiji.py task create`
上传时只会**覆盖同名文件**，未覆盖的继续走官方模板（详见下方 Taiji CLI 一节）。

## 常用命令

```bash
# 环境（shell 是 fish）
python3 -m venv .venv && source .venv/bin/activate.fish
pip install -r requirements.txt

# Sample 数据（HF）
python scripts/download_data.py

# 本地跑 baseline（需要 processed 数据）
TRAIN_DATA_PATH=./data/processed/train \
TRAIN_CKPT_PATH=./checkpoints/baseline \
TRAIN_LOG_PATH=./logs/baseline \
TRAIN_TF_EVENTS_PATH=./logs/tb \
bash baseline/run.sh

# Lint
ruff check .
```

目前没有测试套件。新增可复用模块时，在 `tests/` 下加 `test_<module>.py`；训练逻辑变动应在
sample 数据上跑 smoke test，并把结果记到 `docs/experiments.md`。

## Taiji 平台 CLI（`scripts/taiji.py`）

所有真正的训练/评估都走 Taiji 平台 —— 本地机器跑不动端到端训练。CLI 包装
`taiji.algo.qq.com`，实现拆分在 `scripts/taiji_cli/` 下
（`auth/session/parser/tasks/instances/evals/files/rank/raw`）。

认证：`python scripts/taiji.py auth setup`（粘贴浏览器 `document.cookie`）；cookie 写到
`~/.taiji/cookies.txt`，权限 600 —— **绝对不要提交 cookie 或任何平台状态**。

关键工作流：
- `task create --name X [--from-dir baseline] [--file path[:remote_name]] --dry-run` — 把本地
  文件覆盖到官方模板上；先用 `--dry-run` 检查 POST body 和 COS 路径，确认无误再去掉。
- `task edit <id> --file fixed.py [--dry-run]` — 就地更新已有任务的文件并重启（PUT），
  任务失败需修复代码时首选此命令，而非重新 create。
- `task start <id>` → `task instances <id>` → `inst show/log/metrics/ckpt/watch <id>`。
- 训练完成后，**必须先** `inst release <task_id> --name <name>` 把 ckpt publish 成 mould，
  否则 `eval moulds` 里不会出现该任务，`eval create` 会 400。
- `eval moulds` 找 `mould_id`，再 `eval create --mould-id … [--file model.py] --dry-run`。
- `file snapshot <task_id> --out snapshots/…` 下载某个训练任务的全部 `trainFiles`，便于和本地
  `baseline/` 做 diff。
- `raw <path> [-d JSON]` 用于探索 UI 上抓到的新接口（扩展 CLI 时常用）。

注意：数字 `id` 和长字符串 `taskId` 是两个不同的标识符。`task show` 接受数字 id；
`task instances` 和所有 `inst` 子命令均接受数字 id / 长 taskId / 32-char hex 实例 id，会自动解析。

**两阶段流水线**：提交一次实验 = 先跑训练任务，再跑评估任务：

```
1) 训练任务  task create / task start     训练 ~5-6h（compile_amp 底座）
   上传文件：dataset.py / model.py / train.py / trainer.py / run.sh
   产出：ckpt；训练完成后**必须手动** `inst release <task_id> --name <name>` 发布成 mould，
         才能拿到 mould_id 供评估引用（不 release 则 eval create 会 400）

2) 评估任务  eval create --mould-id <id>  评估 ~14 min（含推理 ~5 min）
   上传文件：dataset.py / model.py / infer.py（若有改动）
   产出：leaderboard AUC 分数
```

重要限制：
- 平台 quota 2 个，超出的任务排队等调度，可以提前批量提交占位
- 训练任务同一账号下可并行，但单卡显存约 40GB，OOM 会 exit 137
- torch.compile ckpt 含 `_orig_mod.` prefix，infer.py 需做 strip（已修复）
- **每日评估上限 3 次**（失败不计），超出返回 400 "You can only submit up to 3 tasks per day"；
  mould 发布后可以等到次日再 `eval create`
- **训练任务失败时优先用 `task edit`，而不是 `task create`**：
  `task edit <id> --file fixed.py` 就地 PUT 更新文件并重启，保留原任务 ID 和名字，
  不消耗新的 quota 位置。`task create` 只在需要新实验记录时才用。

完整说明见 `docs/taiji-cli.md`。

## 深入工作前值得读的文档

- [`AGENTS.md`](AGENTS.md) — 平台操作注意事项、常见坑、推荐工作流，AI Agent 上下文文档。
- `docs/roadmap.md` — 比赛阶段与每个阶段的预期产出。
- `docs/recsys-intro.md` — 推荐系统背景 + 本赛题数据/Loss/指标讲解。
- `docs/experiments.md` — 提交记录。

## 工程纪律（Code-Submission 模式）

- **每次提交前 sample sanity check**：`--train_ratio 1.0 --num_epochs 1 --batch_size 32` 跑一轮，确认不报错。省这一步就是浪费一次评测机会。
- **每次提交前 git tag**：`git tag exp-XXX-<name>` 标记当前 commit，便于回溯和 ensemble 时 checkout。
- **每个实验只动一个旋钮**：提交 → 等结果 → 写 `docs/experiments.md` → 再改下一个。
- **代码里写死超参**，不读外部配置文件，避免平台环境找不到路径。
- **stdout 是唯一调试通道**：平台看不到 tensorboard，`logging.info` 记 epoch/loss/val AUC。
- **失败提交也要记录**：报错或分数下跌都写进 experiments.md，避免重复踩坑。

## 约定

- Conventional Commits：`feat:`、`feat(cli):`、`docs:`、`refactor:`（参考 `git log`）。
- 文件 / 函数 / 变量 / 配置 key 用 snake_case；类用 PascalCase；4 空格缩进。
- `configs/` 下的 YAML 用实验重点命名，例如 `longer_seq256_focal.yaml`。
- 输出目录 `data/`、`checkpoints/`、`logs/`、`snapshots/`、`submissions/` 都在 gitignore 中 ——
  不要提交任何产物（parquet、ckpt、提交包）或 `.env` / cookie 文件。
