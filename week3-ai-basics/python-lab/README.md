# python-lab · 第 3 周大模型调用实验

本目录是第 3 周"极简 Python 调接口"的实操代码。目标只有一个：**亲手调通一次大模型 API，看懂请求体、响应体和 token 用量。**

---

## 一、目录结构

```
python-lab/
├── provider.py              # 厂商配置中心（base_url / model / key），其余脚本共用
├── 01_env_check.py          # 环境自检（Python、依赖、Key、接口地址），可 --ping 验证 Key
├── 02_chat_once.py          # 非流式调用，打印 content + usage（计费依据）
├── 03_chat_stream.py        # 流式调用（SSE），打字机效果 + TTFT/速率统计
├── 04_token_experiment.py   # Token 实验（估算 vs 真实、中英对比、长文切片）
├── requirements.txt         # 依赖清单（只有 requests）
├── keys.env.example         # Key 配置模板，复制成 keys.env 后填写
├── .gitignore               # 忽略 keys.env / 缓存
└── README.md                # 本文件
```

---

## 二、三步准备

### 第 0 步：确认 Python 可用

```powershell
python --version
```

- 有输出（3.10 以上）→ 跳过。
- 提示"不是内部或外部命令" / 打开的是微软商店 → 回到上一级目录，双击 **`00-安装Python.cmd`**，它会自动下载 Python 3.12 并安装到 `D:\Tools\Python312`（不占 C 盘），同时写入用户 PATH。装完**重开一个 PowerShell 窗口**再验证。

### 第 1 步：安装依赖

```powershell
cd D:\WorkspacesIDEA\Java-AI\week3-ai-basics\python-lab
python -m pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
```

> 用阿里云镜像是因为官方 PyPI 在国内经常超时。

### 第 2 步：配置 API Key（二选一）

**方式 A：本地文件（推荐，方便）**

```powershell
Copy-Item keys.env.example keys.env
notepad keys.env
```

把 `sk-xxxx` 换成真实 Key。`keys.env` 已被 `.gitignore` 忽略，不会进仓库。

**方式 B：系统环境变量（更接近生产）**

```powershell
[Environment]::SetEnvironmentVariable('DASHSCOPE_API_KEY','sk-你的key','User')
# 设置后需要重开终端才生效；想临时生效用：
$env:DASHSCOPE_API_KEY = "sk-你的key"
```

> 通义千问（百炼）：<https://bailian.console.aliyun.com/> （首次开通有新人免费额度）
> DeepSeek：<https://platform.deepseek.com/>

### 第 3 步：自检

```powershell
python 01_env_check.py            # 只看配置
python 01_env_check.py --ping     # 真发一次最小请求，验证 Key 可用（消耗几个 token）
```

期望看到：Python 版本、requests OK、Key 脱敏显示、接口地址，"环境自检全部通过"。

---

## 三、四个实验脚本

### 1. 非流式：看懂请求与响应

```powershell
python 02_chat_once.py "用三句话解释什么是 RAG"
```

重点看输出里的四块：
1. `请求体` —— messages / model / temperature / max_tokens / stream
2. `[回答]` —— 模型输出
3. `[usage]` —— prompt_tokens / completion_tokens / total_tokens（**计费依据**）
4. `finish_reason` —— `stop` 表示正常结束，`length` 表示被 max_tokens 截断

对照实验（不用改代码）：

```powershell
# 换人设：system prompt 决定回答风格
python 02_chat_once.py "解释一下多线程" --system "你给小学生讲编程，用生活比喻"

# 温度 0 vs 1：同一问题各跑 3 次，观察稳定性
python 02_chat_once.py "给猫起个名字" --temperature 0
python 02_chat_once.py "给猫起个名字" --temperature 1

# 不花钱看请求体（不需要 Key）
python 02_chat_once.py "test" --dry-run

# 换厂商：同一份代码
python 02_chat_once.py "什么是 Embedding" --provider deepseek
```

### 2. 流式：SSE 与打字机

```powershell
python 03_chat_stream.py "写一段 200 字的 Spring Boot 启动流程说明"
```

输出会逐字出现，结束后给出统计：

```
  TTFT（首 token 延迟） = 680 ms
  总耗时                = 6200 ms
  数据块数              = 180
  平均速率              = 32.4 字/秒
```

想看清 SSE 协议本身：

```powershell
python 03_chat_stream.py --raw "什么是 SSE"
```

会逐行打印 `data: {...}` 原始帧，你能看到 `delta.content` 每次只推一两个字。

### 3. Token 实验

```powershell
python 04_token_experiment.py
python 04_token_experiment.py --offline    # 不联网，只做本地估算与长文分析
```

三个实验：
- **A** 本地估算 vs 接口真实 `usage`（校准心算，偏差多少）
- **B** 同一段意思中文 vs 英文的 token 差异
- **C** 4000 字文档占多少 token、切片后能省多少（第 6~7 周前置）

---

## 四、常见问题

| 报错 | 原因 | 处理 |
|---|---|---|
| `401` / `InvalidApiKey` | Key 错误、带空格换行、未生效 | 重新复制；`01_env_check.py --ping` 复验 |
| `404` / `model not found` | 模型名不对 | 改成控制台里的准确 model id，或用 `LLM_MODEL` 覆盖 |
| `429` | 限流 / 额度耗尽 | 降低频率；控制台看免费额度余量 |
| `ModuleNotFoundError: requests` | 依赖没装 | `python -m pip install -r requirements.txt` |
| 中文乱码 | 编码未指定 | 脚本已设 `resp.encoding='utf-8'`，若仍乱码检查终端编码 |
| 流式不"逐字" | 代理/网关缓冲 | 本脚本直连 API，若经代理需关 buffering |
| `python` 打不开 | 未装或 PATH 未生效 | 跑 `00-安装Python.cmd`，重开终端 |

规模化排查时，先跑 `01_env_check.py --ping`，它能一次性区分"环境问题"和"账号问题"。

---

## 五、安全须知

1. **Key 不进代码、不进 Git、不发截图原图**。`keys.env` 已在 `.gitignore` 中。
2. 日志里打印 Key 一律脱敏（本目录用 `provider.mask_key()`）。
3. 生产环境用密钥管理服务（KMS / 环境变量注入），不要用配置文件。
4. 免费额度只够练习；接业务前先算清 token 成本（见 `04_token_experiment.py` 的成本演示）。

---

## 六、与第 4 周的衔接

本周跑通的这套东西，下周会被 Spring AI 原样"翻译"成 Java：

| 本周 Python | 第 4 周 Java / Spring AI |
|---|---|
| `POST {base_url}/chat/completions` | `ChatClient.prompt().call()` |
| `messages` 数组 | `.system(...)` / `.user(...)` |
| `stream=True` + `iter_lines` | 返回 `Flux<String>` + `produces=TEXT_EVENT_STREAM_VALUE` |
| `temperature` | `ChatOptions` / `application.yml` 里的 `chat.options` |
| `provider.py` 切厂商 | Spring AI starter 换依赖 + 改 yml（业务代码不变） |
| `usage` 统计 | 自定义 Advisor / 拦截器记录 token（第 11 周） |

> 一句话：**协议是同一套协议，你下周要做的只是换一门语言写同样的请求。**
