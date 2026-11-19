package com.ai.service;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Flux;

/**
 * 问答服务：把"怎么调模型"收敛到一处，Controller 只负责 HTTP 协议。
 *
 * 两种调用方式的区别（第 3 周用 Python 验证过的同一件事）：
 * - chat()  ：一次性调用，拿到完整字符串再返回，前端要等 10 秒以上；
 * - stream()：模型边生成边推，前端 1 秒内就能看到第一个字（SSE）。
 */
@Service
public class AiChatService {

    private static final Logger log = LoggerFactory.getLogger(AiChatService.class);

    private final ChatClient chatClient;

    public AiChatService(ChatClient chatClient) {
        this.chatClient = chatClient;
    }

    /**
     * 非流式问答。
     *
     * 调用链：prompt() 组装消息 → user() 放用户问题 → call() 发阻塞请求
     *        → content() 只取正文（role、usage 等被丢掉）。
     * 注意：这里把 system 提示词交给 AiConfig 的 defaultSystem，不用每次写。
     */
    public String chat(String question) {
        long start = System.currentTimeMillis();
        String answer = chatClient.prompt()
                .user(question)
                .call()
                .content();
        log.info("非流式完成，耗时 {} ms，回答长度 {} 字", System.currentTimeMillis() - start, answer == null ? 0 : answer.length());
        return answer;
    }

    /**
     * 流式问答。
     *
     * 返回 Flux<String>：每个元素是模型刚生成的一小段文本（相当于 Python 里
     * 遍历 SSE 拿到的 delta.content）。
     * 重要：这里只是"声明数据流"，真正开始请求是在有人 subscribe 的时候
     *       ——所以 Controller 必须把 Flux 交给响应体，不能提前阻塞消费。
     */
    public Flux<String> stream(String question) {
        return chatClient.prompt()
                .user(question)
                .stream()
                .content()
                .doOnSubscribe(s -> log.info("流式开始：{}", question))
                .doOnComplete(() -> log.info("流式结束"))
                .doOnError(e -> log.error("流式异常", e));
    }
}
