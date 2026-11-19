# -*- coding: utf-8 -*-
"""
02_chat_once.py —— 非流式调用：一次请求，等模型全部生成完，一次性返回

【学习目标】
    1. 亲眼看到"请求体"长什么样（messages / model / temperature / max_tokens）
    2. 亲眼看到"响应体"里真正有用的三个字段：choices、usage、finish_reason
    3. 理解 usage 里的 prompt_tokens / completion_tokens / total_tokens 就是计费依据

【完整调用顺序（照着看注释即可对照代码）】
    main()
      → pv.pop_provider_arg()          解析 --provider
      → pv.get_provider()              选厂商 + 加载 keys.env
      → build_messages()               组装 system + user 两条消息
      → build_payload()                组装 JSON 请求体
      → print_request_preview()        打印"将要发出去的东西"（教学用）
      → [--dry-run] 到此结束，不发网络请求
      → post_chat()                    requests.post → 等响应 → resp.json()
      → render_response()              解析 content / usage / finish_reason
      → explain_usage()                解释 token 数字与耗时

【运行】
    python 02_chat_once.py "用三句话解释什么是 RAG"
    python 02_chat_once.py "什么是 Embedding" --temperature 0
    python 02_chat_once.py "你是谁" --system "你是一个只会说上海话的Java架构师"
    python 02_chat_once.py "test" --dry-run          # 不发请求，只看请求体（不用 Key）
    python 02_chat_once.py "test" --provider deepseek
"""

import json
import sys
import time

import provider as pv

# 默认 persona：第 4 周 Spring AI 里会用 defaultSystem() 设置同样的东西
DEFAULT_SYSTEM = "你是一名专业的 Java+AI 技术助手，回答简洁、精准、通俗易懂，能用类比就用类比。"


def build_messages(question: str, system_prompt: str) -> list[dict]:
    """把"系统提示 + 用户问题"组装成 messages 数组。

    角色说明：
      system    —— 设定身份与规则，优先级最高，一次对话通常只放一条
      user      —— 用户本轮输入
      assistant —— 模型历史回答（多轮对话时才需要回填，本周用不到）
    """
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": question})
    return messages


def build_payload(model: str, messages: list[dict], temperature: float, max_tokens: int) -> dict:
    """组装 OpenAI 兼容协议的请求体。

    stream=False 是关键：告诉服务端"等我全部生成完再一次性返回"。
    如果设成 True，返回的就是一段一段的 SSE 数据流（见 03_chat_stream.py）。
    """
    return {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }


def print_request_preview(url: str, payload: dict) -> None:
    """把请求原样打印出来。看懂这一段，你就理解了所有"大模型 SDK"的本质。"""
    print("-" * 62)
    print(f"POST {url}")
    print("Authorization: Bearer sk-****（已脱敏）")
    print("Content-Type: application/json")
    print("请求体：")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print("-" * 62)


def post_chat(url: str, headers: dict, payload: dict) -> dict:
    """发起请求并返回解析后的 JSON。

    超时设置说明：
      connect 10s —— 建连超时，网络不通时快速失败
      read    60s —— 读取超时，非流式要等模型把整段话生成完，给小一点
                     如果回答很长（max_tokens 很大），要相应放宽
    """
    import requests

    resp = requests.post(url, headers=headers, json=payload, timeout=(10, 60))

    if resp.status_code != 200:
        # 常见错误的定位提示，省去翻文档时间
        hint = {
            400: "请求参数不合法：检查 model 名、temperature 范围(0~2)、messages 是否为空",
            401: "鉴权失败：Key 错误/过期/带了空格或换行",
            403: "无权限：Key 没有该模型权限，或未开通对应服务",
            404: "模型或路径不存在：核对 model ID 与 base_url",
            429: "触发限流或额度耗尽：降低频率，稍后重试",
            500: "服务端错误：重试；持续失败换模型",
        }.get(resp.status_code, "未知状态码，查看响应体")
        print(f"[X] HTTP {resp.status_code} —— {hint}")
        print(f"响应体：{resp.text[:800]}")
        sys.exit(1)

    return resp.json()


def render_response(data: dict) -> None:
    """从响应 JSON 里取出对我们有用的部分。

    响应结构（OpenAI 兼容）：
    {
      "id": "...",
      "choices": [{"index":0, "message":{"role":"assistant","content":"答案"}, "finish_reason":"stop"}],
      "usage": {"prompt_tokens": 25, "completion_tokens": 80, "total_tokens": 105}
    }
    """
    choice = data["choices"][0]
    content = choice["message"]["content"]
    finish_reason = choice.get("finish_reason")

    print("\n[回答]")
    print(content)

    print("\n[元信息]")
    print(f"  finish_reason = {finish_reason}"
          f"   {'（正常说完）' if finish_reason == 'stop' else '（可能是被 max_tokens 截断）'}")
    print(f"  模型          = {data.get('model')}")
    print(f"  响应 id       = {data.get('id')}")


def explain_usage(usage: dict, elapsed_ms: float) -> None:
    """解释 token 用量。这一段是本周"看懂计费"的核心。

    prompt_tokens     —— 你发上去的 messages 一共多少 token（system + user）
    completion_tokens —— 模型生成的内容多少 token
    total_tokens      —— 两者之和，也是上下文窗口消耗量
    """
    if not usage:
        print("\n[usage] 该模型未返回用量信息")
        return

    prompt_t = usage.get("prompt_tokens")
    completion_t = usage.get("completion_tokens")
    total_t = usage.get("total_tokens")

    print("\n[usage / 计费依据]")
    print(f"  prompt_tokens     = {prompt_t}   （输入：你的 system + 问题）")
    print(f"  completion_tokens = {completion_t}   （输出：模型的回答）")
    print(f"  total_tokens      = {total_t}   （合计，占用上下文窗口）")
    print(f"  总耗时            = {elapsed_ms:.0f} ms")

    if prompt_t and completion_t:
        # 输出 token 单价通常是输入的 2~4 倍，所以"话痨"很费钱
        ratio = completion_t / max(prompt_t, 1)
        print(f"  输出/输入 token 比 = {ratio:.2f}（这个比值越高，单位请求成本越高）")


def main() -> None:
    args, provider_name = pv.pop_provider_arg(sys.argv[1:])

    # 极简参数解析：位置参数是问题，其余是可选开关
    question, system_prompt = None, DEFAULT_SYSTEM
    temperature, max_tokens = 0.7, 512
    dry_run = False
    i = 0
    while i < len(args):
        token = args[i]
        if token == "--temperature":
            temperature = float(args[i + 1]); i += 2
        elif token == "--max-tokens":
            max_tokens = int(args[i + 1]); i += 2
        elif token == "--system":
            system_prompt = args[i + 1]; i += 2
        elif token == "--dry-run":
            dry_run = True; i += 1
        else:
            question = token; i += 1

    question = question or "用三句话解释什么是 RAG（检索增强生成）"

    provider = pv.get_provider(provider_name)
    url = provider.chat_url()
    payload = build_payload(provider.effective_model(), build_messages(question, system_prompt),
                            temperature, max_tokens)

    print(f"厂商：{provider.display_name}   模型：{payload['model']}")
    print(f"问题：{question}")
    print_request_preview(url, payload)

    if dry_run:
        print("（--dry-run 模式：只打印请求体，不发送网络请求）")
        print("复制下面这条命令即可手工验证：")
        print(f'curl -s {url} -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" '
              f'-d @payload.json')
        return

    started = time.perf_counter()
    data = post_chat(url, provider.headers(), payload)
    elapsed_ms = (time.perf_counter() - started) * 1000

    render_response(data)
    explain_usage(data.get("usage") or {}, elapsed_ms)


if __name__ == "__main__":
    main()
