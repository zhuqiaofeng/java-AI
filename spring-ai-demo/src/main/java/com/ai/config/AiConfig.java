package com.ai.config;

import org.springframework.ai.chat.client.ChatClient;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * AI 配置。
 *
 * 数据流：application.yml 的 spring.ai.openai.* → Spring AI 自动装配 OpenAiChatModel
 *        → 自动提供 ChatClient.Builder → 这里 build 成 ChatClient 单例。
 *
 * 为什么要自己造 ChatClient Bean？
 * - 默认 system 提示词只写一次，避免每个接口里重复拼；
 * - 之后要加 Advisor（记忆、日志、RAG）时，集中在这里改，接口层不用动。
 */
@Configuration
public class AiConfig {

    /** 默认人设：所有走这个 ChatClient 的调用都会自动带上，追问时不用重复交代身份。 */
    private static final String DEFAULT_SYSTEM_PROMPT = """
            你是 Java+AI 学习助教。
            回答要求：
            1. 先给结论，再给理由；
            2. 涉及概念时用一个生活类比；
            3. 代码只给关键片段，并说明数据怎么流转；
            4. 不确定的地方明确说不确定，不要编造。
            """;

    @Bean
    public ChatClient chatClient(ChatClient.Builder builder) {
        return builder
                .defaultSystem(DEFAULT_SYSTEM_PROMPT)
                .build();
    }
}
