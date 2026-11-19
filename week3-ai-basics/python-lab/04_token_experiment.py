# -*- coding: utf-8 -*-
"""
04_token_experiment.py —— Token 实验：把"计费单位"从抽象概念变成具体数字

【三个实验】
    实验 A：本地估算 vs 接口真实 usage —— 校准你的"心算能力"
    实验 B：同一段意思，中文 vs 英文，谁更省 token
    实验 C：4000 字长文档到底占多少 token —— 理解"为什么必须切片"

【为什么值得做】
    1. 产品问"这个功能一个月多少钱"，你要能在 1 分钟内估出来
    2. 长文档问答失败，80% 是 token 超窗口或切片不合理
    3. 输出 token 单价通常是输入的 2~4 倍，"让模型少说废话"是真实降本手段

【运行】
    python 04_token_experiment.py
    python 04_token_experiment.py --offline        # 不联网，只做本地估算
    python 04_token_experiment.py --provider deepseek

⚠️ 价格用环境变量 PRICE_IN / PRICE_OUT 覆盖，默认值是"示例单价"，单位为 元/百万 token。
   真实价格以厂商官网为准，本脚本只演示计算方式，不作为报价依据。
"""

import json
import os
import sys

import provider as pv

# 示例单价（元 / 100 万 token），请按厂商官网调整
DEFAULT_PRICE_IN = 2.0
DEFAULT_PRICE_OUT = 6.0


# ---------------------------------------------------------------------------
# 本地估算器
# ---------------------------------------------------------------------------
def count_cjk(text: str) -> int:
    """统计中日韩统一表意文字（即汉字）的个数。"""
    return sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")


def estimate_tokens(text: str) -> int:
    """粗略估算 token 数。

    下面的系数不是拍脑袋定的，而是 2026-11-19 用 qwen-plus 实测反推出来的：
        · 152 个汉字的样本 → 纯文本约 117 token  →  0.77 token/汉字，取 0.8
        · 623 个英文字符的样本 → 纯文本约 133 token → 4.7 字符/token，取 4.7

    ⚠️ 注意：不同厂商分词器不同，换 DeepSeek / GLM 后系数会变，
       正确做法是重跑本脚本的实验 A 重新校准（这就是"测量 → 校准"的闭环）。

    真正准确的值只有一个来源：接口返回的 usage。本地估算只用于心算量级，误差约 ±10%。
    """
    cjk = count_cjk(text)
    others = len(text) - cjk
    return max(1, round(cjk * 0.8 + others / 4.7))


def text_profile(text: str) -> dict:
    """给一段文本做"体检"，输出各种计数，方便对比。"""
    return {
        "总字符数": len(text),
        "汉字数": count_cjk(text),
        "本地估算 token": estimate_tokens(text),
    }


# ---------------------------------------------------------------------------
# 调用接口拿真实 usage
# ---------------------------------------------------------------------------
def real_prompt_tokens(provider, text: str) -> dict | None:
    """把 text 作为 user 消息发一次极小请求，从 usage 里读出真实的 prompt_tokens。

    ⚠️ 注意：这里的 prompt_tokens 包含 system 提示和指令本身的 token，
    所以它会比"纯文本"的 token 数略大一点点（通常 10~20 个）。这是正常的。
    """
    import requests

    payload = {
        "model": provider.effective_model(),
        "messages": [
            {"role": "system", "content": "你是一个计数器，只回复用户要求的固定内容。"},
            {"role": "user", "content": text + "\n\n请只回复两个字：收到"},
        ],
        "temperature": 0,
        "max_tokens": 8,
        "stream": False,
    }

    try:
        resp = requests.post(provider.chat_url(), headers=provider.headers(),
                             json=payload, timeout=(10, 60))
    except Exception as exc:
        print(f"    [网络错误] {exc}")
        return None

    if resp.status_code != 200:
        print(f"    [HTTP {resp.status_code}] {resp.text[:300]}")
        return None

    return resp.json().get("usage")


# ---------------------------------------------------------------------------
# 实验主体
# ---------------------------------------------------------------------------
CHINESE_TEXT = (
    "企业知识库问答的核心难点在于：大模型本身并不知道公司内部的规定、流程和产品细节，"
    "如果直接问它，它往往会编造一个看似合理但完全错误的答案。"
    "检索增强生成的做法是先把这些文档切分、向量化并存入向量数据库，"
    "用户提问时先检索出最相关的几段原文，再把它们和问题一起拼进提示词，"
    "要求模型只依据这些资料作答，从而把开卷考试的资料递到模型手里。"
)

ENGLISH_TEXT = (
    "The core difficulty of enterprise knowledge base QA is that the model itself does not know "
    "the company's internal policies, workflows, or product details. If you ask it directly, it "
    "often fabricates a plausible but completely wrong answer. Retrieval-Augmented Generation "
    "splits these documents, embeds them into vectors, and stores them in a vector database. "
    "When a user asks a question, it first retrieves the most relevant passages, then puts them "
    "and the question into the prompt, and requires the model to answer only based on this "
    "material, effectively handing the reference book to the model during an open-book exam."
)


def experiment_a(provider, offline: bool) -> None:
    """实验 A：本地估算 vs 真实 usage。"""
    print("\n" + "=" * 66)
    print("实验 A：本地估算 vs 接口真实 usage（校准你的心算）")
    print("=" * 66)

    for label, text in (("中文样本", CHINESE_TEXT), ("英文样本", ENGLISH_TEXT)):
        profile = text_profile(text)
        print(f"\n{label}：{json.dumps(profile, ensure_ascii=False)}")

        if offline:
            print("    （--offline：跳过真实调用）")
            continue

        usage = real_prompt_tokens(provider, text)
        if not usage:
            continue

        real = usage.get("prompt_tokens", 0)
        estimate = profile["本地估算 token"]
        diff = (estimate - real) / real * 100 if real else 0
        print(f"    真实 prompt_tokens = {real}（含 system 与指令，约 10~20 个额外 token）")
        print(f"    本地估算           = {estimate}")
        print(f"    估算偏差           = {diff:+.1f}%")


def experiment_b(provider, offline: bool) -> None:
    """实验 B：中文 vs 英文的 token 效率（同一段意思）。"""
    print("\n" + "=" * 66)
    print("实验 B：同一段意思，中文和英文谁更费 token")
    print("=" * 66)

    cn = text_profile(CHINESE_TEXT)
    en = text_profile(ENGLISH_TEXT)

    print(f"中文：{cn['总字符数']} 字符，估算 {cn['本地估算 token']} token")
    print(f"英文：{en['总字符数']} 字符，估算 {en['本地估算 token']} token")

    cn_tokens = cn["本地估算 token"]
    en_tokens = en["本地估算 token"]
    if cn_tokens:
        print(f"以中文为基准，英文 token 量是中文的 {en_tokens / cn_tokens:.2f} 倍")

    print("\n结论（写进你的笔记）：")
    print("  · 系数必须实测校准：Qwen 下约 1.25 个汉字 / token、4.7 个英文字符 / token")
    print("  · 同一段内容的中英 token 量差距通常不大（1~1.5 倍），以接口实测为准，别凭感觉估")
    print("  · 真正能省 token 的是：去掉冗余 Prompt、限制 max_tokens、RAG 只带相关片段")


def experiment_c() -> None:
    """实验 C：长文档的 token 量，直观理解"为什么必须切片"。"""
    print("\n" + "=" * 66)
    print("实验 C：4000 字长文档占多少 token（为什么 RAG 必须切片）")
    print("=" * 66)

    # 用重复段落模拟一份 4000 字左右的产品文档
    paragraph = ("系统支持多租户隔离，每个租户拥有独立的知识库空间和独立的向量索引；"
                 "管理员可以按部门分配配额，并设置文档的可见范围与保留期限。")
    # 重复次数按"凑满 4000 字"计算，避免硬编码 40 导致实际长度不足
    repeat = 4000 // len(paragraph) + 1
    long_text = (paragraph * repeat)[:4000]

    tokens = estimate_tokens(long_text)
    print(f"文档长度：{len(long_text)} 字，估算 {tokens} token")

    windows = [("常见轻量模型 32K", 32_000), ("主流长上下文 128K", 128_000), ("超长上下文 1M", 1_000_000)]
    for name, size in windows:
        ratio = tokens / size * 100
        print(f"  占 {name} 窗口的 {ratio:.1f}%")

    print("\n如果把整篇文档直接塞进 Prompt 会怎样：")
    print(f"  · 每次提问都要为这 {tokens} 个输入 token 付费（问 100 次就是 {tokens * 100} token）")
    print("  · 中间内容容易被模型忽略（著名的 lost in the middle 现象）")
    print("  · 一旦超出窗口直接报错")

    # 切片后的对比
    chunk_size, overlap = 500, 50
    step = chunk_size - overlap
    chunks = max(1, (tokens - overlap) // step + 1)
    per_query = 3   # TopK 取 3 块
    print(f"\n按 chunk_size={chunk_size}、overlap={overlap} 切片：")
    print(f"  · 共约 {chunks} 块")
    print(f"  · 每次问答只带 Top{per_query} 块 ≈ {chunk_size * per_query} token")
    print(f"  · 相比全文直塞，输入 token 降到约 "
          f"{chunk_size * per_query / tokens * 100:.1f}%，这就是 RAG 省钱的地方")


def cost_demo(usage_example: dict) -> None:
    """用一次真实调用的 usage 演示成本计算方式。"""
    print("\n" + "=" * 66)
    print("附：成本怎么算（示例单价，非报价）")
    print("=" * 66)

    price_in = float(os.getenv("PRICE_IN", DEFAULT_PRICE_IN))
    price_out = float(os.getenv("PRICE_OUT", DEFAULT_PRICE_OUT))

    prompt_t = usage_example.get("prompt_tokens", 0)
    completion_t = usage_example.get("completion_tokens", 0)

    cost = prompt_t / 1_000_000 * price_in + completion_t / 1_000_000 * price_out
    print(f"  单价假设：输入 {price_in} 元/百万 token，输出 {price_out} 元/百万 token")
    print(f"  本次：输入 {prompt_t} token + 输出 {completion_t} token")
    print(f"  单次成本 ≈ {cost:.6f} 元")
    if cost > 0:
        print(f"  每天 1000 次调用 ≈ {cost * 1000:.2f} 元；每月 ≈ {cost * 1000 * 30:.0f} 元")
    print("  计算方式：输入token/1e6×输入单价 + 输出token/1e6×输出单价")


def main() -> None:
    args, provider_name = pv.pop_provider_arg(sys.argv[1:])
    offline = "--offline" in args

    provider = pv.get_provider(provider_name)

    print("Token 实验")
    print(f"厂商：{provider.display_name}   模型：{provider.effective_model()}   "
          f"离线模式：{'是' if offline else '否'}")

    experiment_a(provider, offline)
    experiment_b(provider, offline)
    experiment_c()

    if not offline:
        usage = real_prompt_tokens(provider, "你好")
        if usage:
            cost_demo(usage)

    print("\n" + "=" * 66)
    print("请把下面 3 条结论补充到你的《AI核心术语笔记》：")
    print("  1. 我实测中文约 __ 字 ≈ 1 token，英文约 __ 字符 ≈ 1 token")
    print("  2. 4000 字文档约 __ token，占 128K 窗口的 __%")
    print("  3. 所以长文档问答必须做切片 + TopK 召回，而不是全文直塞")


if __name__ == "__main__":
    main()
