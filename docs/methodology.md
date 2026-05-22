# 这个 CLI 是怎么做出来的

这份文档记录构建 taac2026-cli 的完整开发思路，供想要用同样方式给其他平台做 CLI 的人参考。

## 核心思路

**不写文档、不读文档——直接抓包。**

平台没有公开 API 文档，也没有 SDK。但浏览器已经知道所有接口：打开 Chrome DevTools（CDT），
在 UI 上手动操作一遍，Network 面板里的每一条请求就是完整的 API spec——URL、method、header、
body、response 结构，一目了然。

把抓到的 cURL 直接喂给 AI 编码助手（Codex / Claude Code），让它生成 CLI 实现，
测试，发现问题，迭代。整个流程几乎不需要自己写代码。

---

## 第一步：手动走一遍平台流程

**强烈建议第一遍完全手动操作**，不要急着让 AI 自动化。原因：

- 你会建立对平台业务流程的心智模型（训练 → 发布 mould → 评估），后续 debug 时知道哪里可能出问题。
- 手动操作量很小（点几个按钮），而让 AI 盲目自动化会产生大量无效 token 消耗。
- 第一次走通之后，后续所有重复操作才适合交给 CLI / AI Agent 来做。

要走通的流程：

1. 登录平台，查看训练任务列表
2. 创建一个训练任务（选模板、上传文件）
3. 启动任务，等待调度，查看实例日志
4. 训练完成后，发布 checkpoint 为 mould
5. 用 mould 创建评估任务，查看评估结果

每一步都在 CDT Network 面板里观察对应的请求。

---

## 第二步：用 CDT 抓 cURL

打开 CDT → Network 面板，执行平台操作，找到对应请求，右键 → **Copy as cURL**。

例如查询任务列表的请求大概长这样：

```bash
curl 'https://taiji.algo.qq.com/aide/api/training/task/list?limit=20&offset=0' \
  -H 'Cookie: ...' \
  -H 'Content-Type: application/json'
```

创建任务的 POST 请求：

```bash
curl 'https://taiji.algo.qq.com/aide/api/training/task/create' \
  -X POST \
  -H 'Cookie: ...' \
  -H 'Content-Type: application/json' \
  --data-raw '{"taskName":"my_exp","templateId":...}'
```

把每个核心操作的 cURL 都抓下来，按功能分组保存（训练 / 实例 / 评估 / 文件）。

---

## 第三步：把 cURL 喂给 AI，生成 CLI

把抓到的 cURL 和你的需求描述一起发给 AI 编码助手（Codex、Claude Code 等）：

```
以下是 Taiji 平台的几个接口：

[粘贴 cURL]

帮我写一个 Python CLI，用 argparse，实现：
- task list --limit N
- task show <id>
- task create --name X --file a.py --dry-run

认证用 ~/.taiji/cookies.txt，复用 requests.Session。
```

AI 会根据 cURL 推断出请求结构、响应格式，直接生成可用的代码。

---

## 第四步：测试 → 迭代

跑起来之后对着平台 UI 验证输出是否正确，常见问题：

- **数字 id vs 长字符串 taskId**：平台用两套 id，要在 CLI 里自动区分（正则判断长度 / 格式）。
- **COS 文件上传**：不是直接 POST 到平台，而是先拿预签名 URL，再 PUT 到腾讯 COS。
- **torch.compile ckpt key 前缀**：带 `_orig_mod.`，infer.py 加载时需要 strip。
- **模板文件去重**：上传前和官方模板做字节级比对，跳过未改动文件，避免 UI 出现伪 `*` 标记。

每发现一类问题，同步更新 `AGENTS.md` 里对应的注意事项——这样 AI Agent 下次操作时就知道要避坑。

---

## Cookie 管理

推荐安装 **[Cookie-Editor](https://cookie-editor.com/)** 浏览器扩展（Chrome / Firefox 均有），
可以一键导出当前域的所有 cookie 为文本，直接粘贴给：

```bash
python taiji.py auth setup
```

`auth setup` 会把 cookie 写到 `~/.taiji/cookies.txt`（权限 600），后续所有请求自动带上。

如果不装扩展，也可以在 CDT Console 里执行 `document.cookie` 手动复制，效果一样，只是麻烦一点。

---

## 为什么不直接让 AI 全程自动化？

理论上可以：让 AI 打开 CDT、操作 UI、抓包、写代码、测试，一条龙自动完成。
但对于第一次接触一个平台的情况，**不推荐**，原因：

1. **token 消耗大**：AI 需要不断截图、分析页面，每一步都消耗大量上下文。
2. **容易走弯路**：AI 对平台的业务逻辑没有先验，抓到无关请求的概率很高。
3. **你不了解流程**：一旦 CLI 出问题，你不知道哪个环节错了。

**正确姿势**：自己手动走一遍（20 分钟），熟悉流程，抓好核心 cURL，
再让 AI 做实现——这样 AI 只需要做它最擅长的部分（写代码），你也保留了 debug 能力。

---

## 迭代节奏

```
手动操作 → 抓 cURL → AI 实现 → 测试 → 发现问题
                                              ↓
                               更新 CLI + 更新 AGENTS.md
                                              ↓
                                       下次 AI Agent 操作不再踩坑
```

`AGENTS.md` 是给 AI Agent 看的上下文文档，记录平台的坑、注意事项、推荐操作顺序。
每次发现新问题都更新它，它会随着迭代越来越准确，AI 操作的成功率也会越来越高。
