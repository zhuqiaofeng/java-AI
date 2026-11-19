# spring-ai-demo（第 4 周）

Spring AI 接入通义千问：普通问答 + SSE 流式。第 5 周起会在这个工程上继续加功能（多轮记忆、RAG、Function Calling）。

## 技术栈（2026-11 实测可用）

| 组件 | 版本 | 说明 |
|---|---|---|
| JDK | Temurin 21.0.13 | Spring Boot 4.x 要求 17+，21 是最省心的选择 |
| Spring Boot | 4.1.2 | 父 POM 统一管版本 |
| Spring AI | 2.0.2 | **2.0 起 starter 改名为 `spring-ai-starter-model-openai`**，网上的 1.x 教程写的是 `spring-ai-openai-spring-boot-starter`，照抄会拉不到依赖 |
| Maven | 3.9.16 | 装在 `D:\Tools\apache-maven-3.9.16`，本地仓库 `D:\MavenRepository` |
| 模型 | 通义千问 qwen-plus | 走 DashScope 的 OpenAI 兼容端点，换厂商只改 base-url |

## 启动

```cmd
cd D:\WorkspacesIDEA\Java-AI\spring-ai-demo
run.cmd
```

`run.cmd` 做的事：指定 JDK/Maven → 从 `..\week3-ai-basics\python-lab\keys.env` 读取 `DASHSCOPE_API_KEY` → `mvn spring-boot:run`。

**Key 不落地到代码里**：`application.yml` 写的是 `${DASHSCOPE_API_KEY}`，只从环境变量读；`keys.env` 已被根目录 `.gitignore` 忽略。

## 三个接口

| 方法 | 路径 | 用途 |
|---|---|---|
| POST | `/api/ai/chat` | 普通问答，等模型写完一次性返回 |
| GET | `/api/ai/chat/stream?question=...` | SSE 流式，浏览器 `EventSource` 可直接连 |
| POST | `/api/ai/chat/stream` | SSE 流式，问题放 JSON body，给 fetch 用 |

浏览器演示页：<http://localhost:8080/>

### 命令行自测

```powershell
# 非流式
curl.exe -s -X POST http://localhost:8080/api/ai/chat `
  -H "Content-Type: application/json; charset=utf-8" `
  --data-binary '{"question":"用三句话解释什么是 RAG"}'

# 流式（-N 关闭缓冲，才能看到逐帧输出）
curl.exe -N "http://localhost:8080/api/ai/chat/stream?question=%E4%BB%80%E4%B9%88%E6%98%AF%20SSE"
```

## 实测数据（2026-11-20，本机）

| 指标 | 非流式 | 流式 |
|---|---|---|
| 首字节 / 首帧 | 3.1 s（全部等完才返回） | **0.38 s** |
| 总耗时 | 3.1 s | 4.5 s |
| 输出形式 | 一整段 JSON | 46 个 `data:` 帧 |

结论：**总耗时几乎一样，但"看到第一个字"的时间差了 8 倍**——这才是做流式的理由。

## 代码结构

```
com.ai
├── AiApplication          启动类
├── config/AiConfig        ChatClient Bean（默认 system 人设）
├── controller/AiChatController  三个接口 + Flux→SSE 桥接
├── service/AiChatService  调模型：chat() / stream()
├── common/Result          统一响应体
├── common/GlobalExceptionHandler  异常 → 结构化 JSON
└── domain/ChatRequest     请求体 + @Valid 校验
```

## 常见问题

| 现象 | 原因 | 处理 |
|---|---|---|
| `{"status":500,"error":"Internal Server Error"}` | 进程里没有 `DASHSCOPE_API_KEY` | 用 `run.cmd` 启动，不要直接 `mvn` 起 |
| `Could not resolve dependencies ... spring-ai-openai-spring-boot-starter` | 照抄了 Spring AI 1.x 的坐标 | 2.x 用 `spring-ai-starter-model-openai` |
| 流式接口一次性吐出全部内容 | 中间有代理/Nginx 缓冲 | 本地直连一般没问题；上线要加 `proxy_buffering off` |
| 中文乱码 | 终端编码不是 UTF-8 | `chcp 65001`，或直接用浏览器演示页 |
