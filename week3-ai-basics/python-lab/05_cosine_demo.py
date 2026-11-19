# -*- coding: utf-8 -*-
"""
05_cosine_demo.py —— 余弦相似度手算实验（不联网、不需要 API Key）

【为什么要有这个脚本】
    第 6~7 周做 RAG 时，"检索"本质上就是：
        拿问题向量，和库里每个文档向量算余弦相似度，取最高的 TopK。
    如果现在不能手算，到时候调不准参数、看不懂相似度分数是为什么。

【运行】
    python 05_cosine_demo.py

【数据流】
    两个 list[float]（模拟两个 embedding 向量）
      → dot()        点积：对应维度相乘再求和
      → norm()       模长：各维平方和开根号
      → cosine()     点积 / (模长*模长)
      → 得到 [-1, 1] 的相似度，越大越相似
"""

import math


def dot(a: list[float], b: list[float]) -> float:
    """点积：Σ a_i * b_i。

    对应 Java：
        double sum = 0;
        for (int i = 0; i < a.length; i++) sum += a[i] * b[i];
    """
    return sum(x * y for x, y in zip(a, b))


def norm(a: list[float]) -> float:
    """模长（L2 范数）：√(Σ a_i²)。"""
    return math.sqrt(sum(x * x for x in a))


def cosine(a: list[float], b: list[float]) -> float:
    """余弦相似度 = 点积 / (|a| × |b|)。

    防御：模长为 0 时直接返回 0，避免除零异常（全零向量在工程里是脏数据）。
    """
    na, nb = norm(a), norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return dot(a, b) / (na * nb)


def normalize(a: list[float]) -> list[float]:
    """把向量缩放到长度为 1。

    归一化之后：cos(a,b) == dot(a,b)，省掉两次开方。
    向量库建索引时普遍要求归一化，这是性能优化，不是数学必需。
    """
    n = norm(a)
    return [x / n for x in a] if n else a[:]


def demo_basic() -> None:
    """三组经典手算，验证"余弦只看方向"这件事。"""
    print("【1】基础性质：余弦只看方向，不看长度")
    print("-" * 60)

    cases = [
        ("完全同向", [1, 2, 2], [2, 4, 4], "B 是 A 的 2 倍长，方向一致"),
        ("正交（无关）", [1, 0], [0, 1], "两个维度互不相关"),
        ("完全反向", [1, 2], [-1, -2], "方向相反，语义对立"),
        ("接近但不同", [1, 2, 2], [1, 2, 3], "第三维略有差异"),
    ]

    for name, a, b, note in cases:
        cos = cosine(a, b)
        dist = math.dist(a, b)   # 顺便算欧氏距离做对比
        print(f"{name:<10} A={a}  B={b}")
        print(f"{'':<10} cos={cos:+.4f}  欧氏距离={dist:.4f}  （{note}）")

    print("\n注意：第一组 cos=1.0，但欧氏距离并不为 0，")
    print("      说明「方向相同」和「数值相同」是两回事——这正是检索要的。")


def demo_retrieval() -> None:
    """模拟一次检索：一个 query 向量 vs 3 个文档向量，按相似度排序。

    真实场景里这些向量是 embedding 模型给的（1024 维）；
    这里用 2 维 + 人造数据，只为把计算过程看清楚。
    """
    print("\n【2】模拟检索：给 query 打分并排序")
    print("-" * 60)

    query = [1.0, 2.0]   # 假设这是"怎么申请退款"的向量

    docs = [
        ("doc-1 退款流程说明", [1.0, 2.1]),
        ("doc-2 发票开具指南", [2.0, -0.5]),
        ("doc-3 会员等级规则", [0.3, 1.9]),
        ("doc-4 服务器运维手册", [-1.5, -1.2]),
    ]

    scores = []
    for doc_id, vec in docs:
        score = cosine(query, vec)
        scores.append((score, doc_id))

    # 按相似度从高到低排序，模拟向量库返回 TopK
    scores.sort(reverse=True)

    print(f"query 向量 = {query}\n")
    for rank, (score, doc_id) in enumerate(scores, 1):
        bar = "█" * max(1, int((score + 1) * 10))   # 粗略可视化
        print(f"  Top{rank}: {score:+.4f}  {doc_id:<18} {bar}")

    print("\n工程含义：TopK 取 3，就会把 doc-1、doc-3、doc-2 拼进 prompt；")
    print("          doc-4 相似度为负，直接被过滤——这就是'召回'。")


def demo_normalize() -> None:
    """验证归一化后可以直接用点积代替余弦，省算力。"""
    print("\n【3】归一化优化：归一化后 点积 == 余弦")
    print("-" * 60)

    a = [3.0, 4.0]
    b = [4.0, 3.0]

    cos_value = cosine(a, b)
    dot_after_norm = dot(normalize(a), normalize(b))

    print(f"cos(a,b)                = {cos_value:.6f}")
    print(f"dot(normalize(a),normalize(b)) = {dot_after_norm:.6f}")
    print("两者相等 → 生产环境可以只存归一化向量，检索时直接点积。")


def main() -> None:
    print("余弦相似度实验（无外部依赖、不联网）\n")
    demo_basic()
    demo_retrieval()
    demo_normalize()

    print("\n" + "=" * 60)
    print("留给你的两个思考题：")
    print("  1. 为什么检索用余弦，而不用欧氏距离？（提示：文本越长向量越大）")
    print("  2. 如果把 doc-2 的向量改成 [2.0, 4.0]（与 query 同向但更长），")
    print("     cos 会变成多少？这说明'长度'对相似度有没有影响？")


""" 
    1   余弦相似度‌：计算两个向量夹角的余弦值，只关注方向，不关心向量长短。两篇主题相同但长度差异很大的文章，夹角很小，相似度依然很高。
    欧氏距离‌：计算高维空间中的绝对直线距离，同时受方向和长度影响。长文档向量模长偏大，会被拉远，导致语义相近却被误判为不相似。‌
    2   doc-2 的向量改成 [2.0, 4.0]，cos 会变成 1.0 ,把向量看作箭头，余弦相似度只看箭头指向的角度，不看箭头有多长。
    说明'长度'对相似度没有影响,分母的归一化会消去长度影响。
"""

if __name__ == "__main__":
    main()
