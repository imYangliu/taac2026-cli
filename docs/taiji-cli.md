# Taiji 平台 CLI 用法

`scripts/taiji.py` 是 taiji.algo.qq.com 的命令行包装，用于管理本比赛的平台工作流：查看训练任务、创建训练任务、监控实例、创建评估、查看评估日志、下载/上传平台文件，以及查看 leaderboard。

## 认证

```bash
python scripts/taiji.py auth setup
python scripts/taiji.py auth check
```

`auth setup` 支持直接粘贴浏览器控制台的 `document.cookie`，也支持 `Cookie: a=b; c=d` 或逐行 `key=value`。cookie 会写入 `~/.taiji/cookies.txt`，如果已存在会询问是否覆盖。不要把 cookie 提交到仓库。

## 训练任务

```bash
python scripts/taiji.py task quota
python scripts/taiji.py task template
python scripts/taiji.py task list --limit 20
python scripts/taiji.py task show <numeric_task_id>
python scripts/taiji.py task start <numeric_task_id_or_long_taskId>
python scripts/taiji.py task instances <numeric_task_id_or_long_taskId>
```

创建训练任务时，平台模板已包含官方 baseline 文件：`dataset.py`、`model.py`、`train.py`、`trainer.py`、`utils.py`、`run.sh`、`ns_groups.json`。CLI 会先读取模板 `trainFiles`，再用本地同名文件覆盖，或追加新增文件；未覆盖的文件继续使用官方模板。

> **自动跳过未改动文件**：`task create` / `eval create` 在上传前会和官方模板做字节级比对，
> 与模板完全一致的本地文件会被自动跳过（输出 `skip <name>: identical to official template`），
> 避免在 `task show` 里产生伪 `*` user-modified 标记。如需强制重传，加 `--force`。

```bash
# 只覆盖 run.sh，其余文件沿用官方模板
python scripts/taiji.py task create \
  --name my_train_0507 \
  --file baseline/run.sh \
  --dry-run

# 上传目录下所有直接文件并创建任务
python scripts/taiji.py task create \
  --name my_full_baseline \
  --from-dir baseline
```

建议先使用 `--dry-run` 检查 POST body 和 COS 路径，确认无误后再去掉。

## 训练实例监控

所有 `inst` 命令都接受以下三种 ID 格式，会自动解析：
- 数字 task id（最常用，如 `71202`）
- 长 taskId 字符串（如 `angel_training_ams_2026_...`，来自 `task show`）
- 32-char hex 实例 id（如 `95a8cfc4...`，来自 `task instances`）

```bash
python scripts/taiji.py inst show <id>
python scripts/taiji.py inst metrics <id> --tag AUC --last 10
python scripts/taiji.py inst log <id> --tail 200 --grep 'AUC|Epoch|ERROR'
python scripts/taiji.py inst ckpt <id>
python scripts/taiji.py inst watch <id> --interval 60
python scripts/taiji.py inst release <id> [--name mould_name]
```

`inst show` 汇总 checkpoint 和 TensorBoard 指标；`inst log` 读取 pod 日志（自动拿最近一次实例）；`inst watch` 适合长时间训练监控。

`inst release` 把训练完成的 ckpt 发布到 Model List（平台限额 20 个），发布后才能在 `eval moulds` 看到并创建评估任务。ckpt 若未发布，平台会在约 24 小时后自动删除，务必及时操作。

## 评估任务

完整流程：

```bash
# 1. 训练完成后发布 ckpt → 生成 mould
python scripts/taiji.py inst release <task_id> --name my_exp

# 2. 确认 mould 已出现（记下 mould #id）
python scripts/taiji.py eval moulds

# 3. 创建评估（先 --dry-run 确认，再去掉）
python scripts/taiji.py eval create \
  --mould-id <id> \
  --name my_exp_eval \
  --file baseline/dataset.py \
  --dry-run

# 4. 查看结果
python scripts/taiji.py eval show <evaluation_id>
python scripts/taiji.py eval list --limit 20
python scripts/taiji.py eval log <evaluation_id> --tail 100 --grep 'ERROR|failed' --time
```

评估模板默认包含 `dataset.py`、`model.py`、`infer.py`；CLI 只覆盖同名本地文件，未覆盖文件继续使用官方模板。训练时修改了 `dataset.py` 的话，评估也需要 `--file baseline/dataset.py` 保持一致。

> **⚠ 使用 `--use_compile` 训练时必须附带 `--file baseline/infer.py`**
> `torch.compile()` 保存的 checkpoint 所有 key 带 `_orig_mod.` 前缀，官方模板旧版 infer.py
> 不处理该前缀，会导致 strict load 失败。`baseline/infer.py` 已修复此问题，eval create 时
> 始终加 `--file baseline/infer.py`。

## 文件与快照

```bash
python scripts/taiji.py file cat <cos_key>
python scripts/taiji.py file get <cos_key> --out local.py
python scripts/taiji.py file put local.py --key <cos_key>
python scripts/taiji.py file snapshot <numeric_task_id> --out snapshots/task_xxx
```

`file snapshot` 会下载某个训练任务的所有 `trainFiles`，便于和本地 `baseline/` 做 diff。

## Leaderboard 与原始接口调试

```bash
python scripts/taiji.py rank --size 20
python scripts/taiji.py raw /aide/api/some/path
python scripts/taiji.py raw /some/path -d '{"key":"val"}'
```

`raw` 用于临时探索 UI 新接口；抓到浏览器 Network 里的 path/query 后可直接传给它。
