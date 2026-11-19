# -*- coding: utf-8 -*-
"""
01_env_check.py —— 环境自检：先确认"枪能打响"，再去打靶

【它检查什么】
    1. Python 解释器版本与路径
    2. requests 依赖是否安装
    3. API Key 是否读到（脱敏显示）
    4. 实际会请求的 URL / model / 参数
    5. 可选：发一次最小请求（--ping），验证 Key 真的能用（会消耗几个 token）

【为什么第一步要做这个】
    后面所有实验都会调用 HTTP 接口。如果 Key 配错、依赖没装、Python 版本太老，
    报错会以"401/404/ModuleNotFound"的形式出现在别的脚本里，排查成本翻倍。
    把所有前置条件集中检查一遍，是工程上的常规做法（类似 Spring Boot 的 Actuator health）。

【运行】
    python 01_env_check.py
    python 01_env_check.py --provider deepseek
    python 01_env_check.py --ping
"""

import json
import sys
import time
from pathlib import Path

import provider as pv

# 逐项检查，最后汇总；这种写法让问题"一次暴露完"而不是改一个跑一次
problems = []


def check_python_version() -> None:
    """本项目只用 Python 3.8+ 的标准特性，但 3.10+ 体验更好（类型注解、错误提示）。"""
    version = sys.version_info
    print(f"[1] Python 版本：{version.major}.{version.minor}.{version.micro}")
    print(f"    解释器路径：{sys.executable}")
    if version < (3, 8):
        problems.append("Python 版本低于 3.8，请升级（建议 3.12）")


def check_requests() -> None:
    """requests 是唯一的外部依赖；没装就没法发 HTTP 请求（也可以用标准库 urllib，但写起来更啰嗦）。"""
    try:
        import requests  # 放在函数里导入，才能捕获 ImportError 并给出友好提示
        print(f"[2] requests 版本：{requests.__version__}  OK")
    except ImportError:
        problems.append("缺少 requests，请执行：python -m pip install -r requirements.txt")


def check_provider(provider_name):
    """检查厂商配置与 Key。"""
    p = pv.get_provider(provider_name)
    key = p.api_key()

    print(f"[3] 当前厂商：{p.name} / {p.display_name}")
    print(f"    模型 model   ：{p.effective_model()}")
    print(f"    接口 chat_url：{p.effective_base_url().rstrip('/')}/chat/completions")
    print(f"    Key 环境变量 ：{', '.join(p.key_envs)}")
    print(f"    Key 状态     ：{pv.mask_key(key)}")
    print(f"    Key 申请地址 ：{p.apply_url}")

    if not key:
        problems.append(f"未读到 {p.display_name} 的 API Key（{', '.join(p.key_envs)}）")
    return p


def check_env_file() -> None:
    """提示 keys.env 是否存在，以及 .gitignore 是否已忽略它（防止 Key 被提交）。"""
    env_file = Path(__file__).resolve().parent / "keys.env"
    gitignore = Path(__file__).resolve().parent / ".gitignore"
    print(f"[4] keys.env 文件：{'存在' if env_file.exists() else '不存在（可用环境变量代替）'}")
    if gitignore.exists() and "keys.env" in gitignore.read_text(encoding="utf-8"):
        print("    .gitignore 已包含 keys.env  OK（Key 不会被提交）")
    else:
        problems.append(".gitignore 未忽略 keys.env，存在 Key 泄露风险")


def ping(provider) -> None:
    """发一次最小请求，验证鉴权、模型名、网络三者是否都通。

    max_tokens=1 表示只要 1 个 token 的回答，费用可以忽略；
    但"能不能连上"这个信息价值很高。
    """
    import requests

    payload = {
        "model": provider.effective_model(),
        "messages": [{"role": "user", "content": "只回复两个字：收到"}],
        "max_tokens": 1,
        "temperature": 0,
    }

    print("\n[5] 试调用（--ping）：")
    print("    请求体：" + json.dumps(payload, ensure_ascii=False))

    started = time.perf_counter()
    try:
        resp = requests.post(
            provider.chat_url(),
            headers=provider.headers(),
            json=payload,
            timeout=30,
        )
    except Exception as exc:  # 网络层错误：DNS、超时、代理、证书
        problems.append(f"网络请求失败：{exc}")
        return

    elapsed_ms = (time.perf_counter() - started) * 1000
    print(f"    HTTP {resp.status_code}，耗时 {elapsed_ms:.0f} ms")

    if resp.status_code != 200:
        # 不同厂商错误格式略有差异，统一打印响应体，方便对照文档排查
        print(f"    响应体：{resp.text[:500]}")
        problems.append(f"接口返回 {resp.status_code}，请看上方响应体（常见原因：Key 无效 / 模型名错误 / 欠费）")
        return

    data = resp.json()
    usage = data.get("usage") or {}
    print(f"    回答：{data['choices'][0]['message']['content']!r}")
    print(f"    usage：{json.dumps(usage, ensure_ascii=False)}")
    print("    OK：Key、模型名、网络三者都通")


def main() -> None:
    args, provider_name = pv.pop_provider_arg(sys.argv[1:])
    do_ping = "--ping" in args

    check_python_version()
    check_requests()
    provider = check_provider(provider_name)
    check_env_file()

    if do_ping:
        ping(provider)

    print("\n" + "=" * 60)
    if problems:
        print(f"发现 {len(problems)} 个问题：")
        for i, item in enumerate(problems, 1):
            print(f"  {i}. {item}")
        sys.exit(1)
    print("环境自检全部通过，可以开始 Day2 的实验了。")


if __name__ == "__main__":
    main()
