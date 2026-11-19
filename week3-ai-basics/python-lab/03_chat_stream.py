# -*- coding: utf-8 -*-
"""
03_chat_stream.py —— 流式调用（SSE）：模型边生成边推送，前端逐字显示

【为什么要有流式】
    非流式要等整段话生成完（可能 5~30 秒），用户盯着转圈；流式在第一个 token 出来时就能显示，
    体感从"卡住"变成"打字"。代价是实现更复杂：要处理分块、粘包、异常断开、计费统计。

【SSE 报文长什么样（用 --raw 可以看到原始内容）】
    HTTP/1.1 200 OK
    Content-Type: text/event-stream

    data: {"choices":[{"delta":{"content":"你"}}]}      ← 一条事件，两个换行结束
    data: {"choices":[{"delta":{"content":"好"}}]}
    data: [DONE]                                        ← 结束标记

    解析要点：
      1. 只处理以 "data:" 开头的行，忽略空行和 ": ping" 之类的注释行
      2. 每行的 JSON 里取 choices[0].delta.content（注意是 delta，不是 message）
      3. 收到 [DONE] 就跳出循环

【完整调用顺序】
    main()
      → 解析参数（--raw / --with-usage / --provider / --temperature）
      → pv.get_provider()  取厂商与 Key
      → build_payload()    stream=True
      → stream_chat()      requests.post(stream=True) → iter_lines() → 逐块解析 JSON → 打印 delta
      → print_stats()      TTFT / 总耗时 / 块数 / 字每秒

【运行】
    python 03_chat_stream.py "写一段 200 字的 Spring Boot 启动流程说明"
    python 03_chat_stream.py --raw "什么是 SSE"
    python 03_chat_stream.py --with-usage "解释一下 Token"
"""

import json
import sys
import time

import provider as pv

DEFAULT_SYSTEM = "你是一名专业的 Java+AI 技术助手，回答简洁、精准、通俗易懂。"


def build_payload(model: str, question: str, system_prompt: str,
                  temperature: float, max_tokens: int, with_usage: bool) -> dict:
    """构造流式请求体。

    与非流式（02 号脚本）唯一的区别就是：
        "stream": true

    stream_options.include_usage = True 时，部分厂商会在最后一个 chunk 里补上 usage，
    这样流式调用也能统计 token。不是所有厂商都支持，用 --with-usage 显式开启。
    """
    messages = [{"role": "system", "content": system_prompt},
                {"role": "user", "content": question}]
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }
    if with_usage:
        payload["stream_options"] = {"include_usage": True}
    return payload


def stream_chat(url: str, headers: dict, payload: dict, show_raw: bool) -> None:
    """核心：一边读流一边解析，实现打字机效果。"""
    import requests

    print("[开始流式输出]\n")

    started = time.perf_counter()
    first_token_at = None      # 首个内容 token 到达的时刻
    chunk_count = 0            # 收到的数据块数量
    char_count = 0             # 累计字符数（用来算字/秒）
    reasoning_chars = 0        # 思考模式的思维链字符数（不打印，只统计）
    usage = None               # 部分厂商会在最后一块返回用量
    finish_reason = None

    # stream=True 是关键：requests 不会把响应体一次性读完，而是保留连接，
    # 让我们可以 iter_lines() 一行行消费。timeout 的 read 给大一些（流会持续较久）。
    with requests.post(url, headers=headers, json=payload, stream=True,
                       timeout=(10, 300)) as resp:

        if resp.status_code != 200:
            print(f"[X] HTTP {resp.status_code}")
            print(resp.text[:800])
            sys.exit(1)

        # 显式指定编码：SSE 包含中文时，不设置可能乱码
        resp.encoding = "utf-8"

        # iter_lines 会按 \n 切行；SSE 的每个事件是 "data: {...}\n\n"
        for line in resp.iter_lines(decode_unicode=True):
            if line is None or line == "":
                continue                      # 空行是事件分隔符，直接跳过

            if show_raw:
                print(f"\n[raw] {line}")

            if not line.startswith("data:"):
                continue                      # 兼容 ": ping" 之类的注释行

            data_str = line[len("data:"):].strip()
            if data_str == "[DONE]":
                break                         # 服务端明确表示结束

            try:
                chunk = json.loads(data_str)
            except json.JSONDecodeError:
                continue                      # 个别厂商会插入非 JSON 的心跳帧

            # 有些厂商在最后一块返回 usage（此时 choices 可能为空数组）
            if chunk.get("usage"):
                usage = chunk["usage"]

            choices = chunk.get("choices") or []
            if not choices:
                continue

            choice = choices[0]
            if choice.get("finish_reason"):
                finish_reason = choice["finish_reason"]

            delta = choice.get("delta") or {}

            # 思考模式（如 DeepSeek 的 thinking）会先推 reasoning_content，
            # 这部分通常不直接展示给用户，只做统计
            reasoning = delta.get("reasoning_content")
            if reasoning:
                reasoning_chars += len(reasoning)

            content = delta.get("content")
            if not content:
                continue                      # 第一块往往只有 role，没有内容

            if first_token_at is None:
                first_token_at = time.perf_counter()   # 记录首 token 时刻

            chunk_count += 1
            char_count += len(content)

            # end="" + flush=True：不换行、立刻刷新缓冲区，才有逐字出现的效果
            print(content, end="", flush=True)

    total_ms = (time.perf_counter() - started) * 1000
    ttft_ms = (first_token_at - started) * 1000 if first_token_at else -1

    print("\n")
    print("[统计]")
    print(f"  TTFT（首 token 延迟） = {ttft_ms:.0f} ms   ← 用户感觉快不快，主要取决于它")
    print(f"  总耗时                = {total_ms:.0f} ms")
    print(f"  数据块数              = {chunk_count}")
    print(f"  输出字符数            = {char_count}")
    if total_ms > 0:
        print(f"  平均速率              = {char_count / (total_ms / 1000):.1f} 字/秒")
    if ttft_ms > 0 and char_count:
        # 生成阶段的速率（排除排队和首 token 等待）更能反映模型真实吞吐
        gen_ms = total_ms - ttft_ms
        if gen_ms > 0:
            print(f"  生成阶段速率          = {char_count / (gen_ms / 1000):.1f} 字/秒（排除首 token 等待）")
    if reasoning_chars:
        print(f"  思维链字符数          = {reasoning_chars}（思考模式，未展示）")
    if finish_reason:
        print(f"  finish_reason         = {finish_reason}")
    if usage:
        print(f"  usage                 = {json.dumps(usage, ensure_ascii=False)}")
    else:
        print("  usage                 = 未返回（加 --with-usage 可尝试获取）")


def main() -> None:
    args, provider_name = pv.pop_provider_arg(sys.argv[1:])

    question, system_prompt, temperature, max_tokens = None, DEFAULT_SYSTEM, 0.7, 512
    show_raw, with_usage = False, False

    i = 0
    while i < len(args):
        token = args[i]
        if token == "--raw":
            show_raw = True; i += 1
        elif token == "--with-usage":
            with_usage = True; i += 1
        elif token == "--temperature":
            temperature = float(args[i + 1]); i += 2
        elif token == "--max-tokens":
            max_tokens = int(args[i + 1]); i += 2
        elif token == "--system":
            system_prompt = args[i + 1]; i += 2
        else:
            question = token; i += 1

    question = question or "用 200 字说明 Spring Boot 的自动配置原理"

    provider = pv.get_provider(provider_name)
    payload = build_payload(provider.effective_model(), question, system_prompt,
                            temperature, max_tokens, with_usage)

    print(f"厂商：{provider.display_name}   模型：{payload['model']}   stream=True")
    print(f"问题：{question}")
    print()

    stream_chat(provider.chat_url(), provider.headers(), payload, show_raw)

    print("\n提示：把这段输出接到前端，就是聊天页面的打字机效果；")
    print("      第 4 周 Java 侧返回 Flux<String>，浏览器端用 EventSource 接收，协议完全一样。")


if __name__ == "__main__":
    main()
