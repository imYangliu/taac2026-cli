# taac2026-cli

[Taiji](https://taiji.algo.qq.com) 训练平台的命令行工具，为 TAAC 2026（腾讯 × KDD 广告算法大赛）而生。

封装 Taiji REST API，在终端里完成训练任务管理、实例监控、checkpoint 发布、评估提交、排行榜查看。

## 安装

```bash
pip install requests cos-python-sdk-v5
```

无需打包安装，clone 后直接运行。

## 使用

```bash
python taiji.py --help
```

完整使用文档见 [docs/taiji-cli.md](docs/taiji-cli.md)。

## 认证

```bash
python taiji.py auth setup   # 粘贴浏览器 document.cookie
python taiji.py auth check
```

Cookie 存储在 `~/.taiji/cookies.txt`（权限 600）。**绝对不要提交此文件。**

推荐安装 [Cookie-Editor](https://cookie-editor.com/) 浏览器扩展，一键导出当前域的全部 cookie，粘贴进 `auth setup` 即可。

## 常用命令

```bash
# 训练任务
python taiji.py task list
python taiji.py task create --name my_exp --file model.py --dry-run
python taiji.py task edit <id> --file fixed.py
python taiji.py task start <id>

# 实例监控
python taiji.py inst show <id>
python taiji.py inst log <id> --tail 200 --grep 'AUC|ERROR'
python taiji.py inst watch <id>
python taiji.py inst release <id> --name my_mould

# 评估
python taiji.py eval moulds
python taiji.py eval create --mould-id <id> --dry-run
python taiji.py eval show <id>

# 其他
python taiji.py rank --size 20
python taiji.py raw /aide/api/some/path
```

## 这个 CLI 是怎么做出来的

平台没有公开 API 文档，整个 CLI 的开发流程是：

1. 打开 Chrome DevTools（CDT），在平台 UI 上手动走一遍完整流程
2. 从 Network 面板 Copy as cURL，拿到每个操作的接口信息
3. 把 cURL 喂给 AI 编码助手（Codex / Claude Code），生成 CLI 实现
4. 测试，发现边界情况，迭代 CLI 和 `CLAUDE.md`

**第一遍强烈建议手动走**：建立对平台业务流程的心智模型，后续 debug 时知道哪里可能出问题，同时把 token 消耗压到最低。走通之后再让 AI 接管重复操作。

详细步骤见 [docs/methodology.md](docs/methodology.md)。

## 目录结构

```
taiji.py          # 入口
taiji_cli/
  auth.py         # 认证 setup & check
  session.py      # HTTP 工具（requests + cookie jar）
  tasks.py        # task create / edit / start / list / show
  instances.py    # inst show / log / metrics / watch / release
  evals.py        # eval create / list / show / log / moulds
  files.py        # file cat / get / put / snapshot（COS）
  rank.py         # 排行榜
  raw.py          # 原始接口探索
  parser.py       # argparse 路由
  constants.py    # BASE URL、COS 配置、路径
```
