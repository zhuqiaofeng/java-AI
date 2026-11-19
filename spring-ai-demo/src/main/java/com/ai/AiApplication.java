package com.ai;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * 第 4 周入口：Spring AI 接大模型。
 *
 * 启动顺序（读代码时按这个顺序看）：
 * 1. 本类启动 Spring 容器，自动装配 application.yml 里的 spring.ai.openai.* 配置；
 * 2. AiConfig 用自动装配好的 ChatClient.Builder 造一个 ChatClient Bean；
 * 3. Controller 收到 HTTP 请求 → Service 调 ChatClient → 模型返回 → 包装成 Result。
 */
@SpringBootApplication
public class AiApplication {

    public static void main(String[] args) {
        SpringApplication.run(AiApplication.class, args);
    }
}
