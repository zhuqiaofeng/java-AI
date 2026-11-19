# -*- coding: utf-8 -*-
"""
provider.py —— 大模型接入的统一配置（第 3 周 · Python 实验）

【为什么要有这个文件】
通义千问（阿里云百炼）和 DeepSeek 都提供「OpenAI 兼容」的 /chat/completions 接口：

    POST  {base_url}/chat/completions
    Header: Authorization: Bearer {api_key}
    Body:   {"model": "...", "messages": [...], "temperature": 0.7, "stream": false}

也就是说，两家厂商只差三样东西：base_url、model、api_key。
把这三样抽成 Provider 配置对象后，其余脚本就不用关心"是哪家厂商"了。

⚠️ 这个认知是后面所有内容的地基：
    第 4 周 Spring AI 之所以能用同一个 ChatClient 对接多家模型，底层逻辑和这里一模一样——
    适配层把厂商差异收敛掉，业务代码只面对统一协议。

【数据流（从上到下就是调用顺序）】
    main 脚本
      → get_provider()             读取命令行 --provider 或环境变量 LLM_PROVIDER，选出厂商
      → load_keys_env()            把同目录 keys.env 的内容注入 os.environ（本地开发便利）
      → Provider.require_key()     取 Key，取不到就直接抛异常（问题暴露在最前面）
      → Provider.chat_url()        拼出 https://.../v1/chat/completions
      → Provider.headers()         拼出 {"Authorization": "Bearer sk-xxx", "Content-Type": "application/json"}
      → requests.post(...)         真正发起网络请求（由各脚本自己调用）
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

# keys.env 与本文件放在同一目录，方便直接运行
BASE_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Provider:
    """一家大模型厂商的最小配置信息。frozen=True 表示实例创建后不可修改，避免被误改。"""

    name: str                 # 内部标识，命令行用这个
    display_name: str         # 给人看的名字
    base_url: str             # 接口根地址（不含 /chat/completions）
    model: str                # 模型 ID
    key_envs: tuple[str, ...] # 读取 API Key 时依次尝试的环境变量名（兼容厂商别名）
    apply_url: str            # 申请 Key 的控制台地址
    note: str                 # 一句话说明

    def chat_url(self) -> str:
        """拼接完整的对话接口地址。

        注意 base_url 里不能以 '/' 结尾，否则会拼出 //chat/completions。
        这里用 rstrip('/') 兜底，属于防御式写法。
        走 effective_base_url() 是为了让 QWEN_BASE_URL / DEEPSEEK_BASE_URL 环境变量能生效，
        方便切换业务空间域名或指向本地 mock 服务做测试。
        """
        return f"{self.effective_base_url().rstrip('/')}/chat/completions"

    def api_key(self) -> Optional[str]:
        """按顺序尝试多个环境变量名，返回第一个非空的 Key。

        为什么要多个环境变量名？
        阿里云官方文档用 DASHSCOPE_API_KEY，早期教程里也有用 QWEN_API_KEY 的，
        两种都认可以减少"Key 明明配了却读不到"的排查时间。
        """
        for env_name in self.key_envs:
            value = os.getenv(env_name)
            if value:
                return value.strip()
        return None

    def require_key(self) -> str:
        """必须拿到 Key，否则直接退出并给出可操作的提示。

        早失败（fail fast）比让 requests 返回一个看不懂的 401 更好排查。
        """
        key = self.api_key()
        if not key:
            env_hint = " 或 ".join(self.key_envs)
            print(f"[X] 没有读到 {self.display_name} 的 API Key。")
            print(f"    请设置环境变量 {env_hint}（或在 python-lab 目录下创建 keys.env 并填写）。")
            print(f"    申请地址：{self.apply_url}")
            sys.exit(1)
        return key

    def headers(self) -> Dict[str, str]:
        """构造 HTTP 请求头。Authorization 采用 Bearer Token 方案，和 OpenAI 一致。"""
        return {
            "Authorization": f"Bearer {self.require_key()}",
            "Content-Type": "application/json",
        }

    def effective_model(self) -> str:
        """允许用环境变量 LLM_MODEL 临时覆盖模型名，方便做同一家厂商不同模型的对比。"""
        return os.getenv("LLM_MODEL", "").strip() or self.model

    def effective_base_url(self) -> str:
        """允许用环境变量覆盖 base_url。

        2026 年起阿里云百炼部分地域改成了「业务空间」域名：
            https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1
        如果默认域名不通，把实际域名填到 QWEN_BASE_URL 即可，不用改代码。
        """
        if self.name == "qwen":
            return os.getenv("QWEN_BASE_URL", "").strip() or self.base_url
        if self.name == "deepseek":
            return os.getenv("DEEPSEEK_BASE_URL", "").strip() or self.base_url
        return self.base_url


# ---------------------------------------------------------------------------
# 厂商注册表：新增一家厂商，只在这里加一条，其余脚本零改动
# ---------------------------------------------------------------------------
PROVIDERS: Dict[str, Provider] = {
    "qwen": Provider(
        name="qwen",
        display_name="通义千问（阿里云百炼）",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model="qwen-plus",
        key_envs=("DASHSCOPE_API_KEY", "QWEN_API_KEY"),
        apply_url="https://bailian.console.aliyun.com/",
        note="国内直连、新人有免费额度，第 4 周 Spring AI 默认接这家",
    ),
    "deepseek": Provider(
        name="deepseek",
        display_name="DeepSeek",
        base_url="https://api.deepseek.com/v1",
        model="deepseek-flash",
        key_envs=("DEEPSEEK_API_KEY",),
        apply_url="https://platform.deepseek.com/",
        note="价格低、推理强，用来验证「同一份代码切厂商」",
    ),
}


def load_keys_env() -> None:
    """把同目录下的 keys.env 读进 os.environ（只做最小实现，避免额外依赖 python-dotenv）。

    规则：
      - 跳过空行和 # 开头的注释行
      - KEY=VALUE，去掉两端空白和成对的引号
      - 已经存在的系统环境变量优先，不被文件覆盖（防止本地文件覆盖生产配置）

    为什么不用硬编码？
      代码进 Git 仓库后，Key 一旦写死就等于泄露，且换环境要改代码。
    """
    env_file = BASE_DIR / "keys.env"
    if not env_file.exists():
        return

    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def get_provider(name: Optional[str] = None) -> Provider:
    """选出当前要用的厂商。

    优先级：函数参数（来自命令行 --provider） > 环境变量 LLM_PROVIDER > 默认 qwen
    """
    load_keys_env()
    chosen = (name or os.getenv("LLM_PROVIDER") or "qwen").strip().lower()
    if chosen not in PROVIDERS:
        available = ", ".join(PROVIDERS.keys())
        print(f"[X] 未知厂商：{chosen}，可选：{available}")
        sys.exit(1)
    return PROVIDERS[chosen]


def mask_key(key: Optional[str]) -> str:
    """Key 脱敏后再打印，日志里只保留前后 4 位，避免截图分享时泄露。"""
    if not key:
        return "（未配置）"
    if len(key) <= 12:
        return key[:2] + "*" * (len(key) - 2)
    return f"{key[:6]}...{key[-4:]}（长度 {len(key)}）"


def pop_provider_arg(argv: list[str]) -> tuple[list[str], Optional[str]]:
    """从命令行参数里提取 --provider xxx，返回 (剩余参数, 厂商名)。

    手写一个极简参数解析，避免为了一个参数引入 argparse 的学习成本；
    真实项目建议直接用 argparse。
    """
    rest, provider_name = [], None
    i = 0
    while i < len(argv):
        if argv[i] == "--provider" and i + 1 < len(argv):
            provider_name = argv[i + 1]
            i += 2
            continue
        rest.append(argv[i])
        i += 1
    return rest, provider_name


if __name__ == "__main__":
    # 直接运行本文件时，打印一份配置清单，方便确认环境是否正确
    load_keys_env()
    print("可用厂商配置：")
    for p in PROVIDERS.values():
        configured = "已配置" if p.api_key() else "未配置"
        print(f"  - {p.name:<9} {p.display_name:<18} model={p.effective_model():<14} key={configured}")
        print(f"    接口：{p.effective_base_url().rstrip('/')}/chat/completions")
        print(f"    说明：{p.note}")
