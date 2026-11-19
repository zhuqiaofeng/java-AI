package com.ai.domain;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/**
 * 问答请求体。
 *
 * 校验放在这里而不是 Service：参数不合法时请求根本进不到模型，
 * 避免把无效 token 花在"空问题"上——这是第 3 周 token 成本意识的直接落地。
 */
public record ChatRequest(
        @NotBlank(message = "question 不能为空")
        @Size(max = 2000, message = "question 过长，请控制在 2000 字以内")
        String question
) {
}
