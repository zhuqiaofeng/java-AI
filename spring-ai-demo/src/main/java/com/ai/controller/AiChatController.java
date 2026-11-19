package com.ai.controller;

import com.ai.common.Result;
import com.ai.domain.ChatRequest;
import com.ai.service.AiChatService;
import jakarta.validation.Valid;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;

/**
 * AI 接口层。
 *
 * 提供三个入口，覆盖第 4 周要求：
 * 1. POST /api/ai/chat        普通问答（一次拿到完整回答）
 * 2. GET  /api/ai/chat/stream SSE 流式（浏览器 EventSource 可直接用）
 * 3. POST /api/ai/chat/stream SSE 流式（POST + JSON，给前端 fetch 用）
 *
 * 为什么流式要两个？
 * - EventSource 只支持 GET，所以浏览器演示页面走 GET + 查询参数；
 * - 真实前端通常用 fetch + ReadableStream 发 POST，问题放在请求体里更规范。
 */
@RestController
@RequestMapping("/api/ai")
public class AiChatController {

    private final AiChatService aiChatService;

    public AiChatController(AiChatService aiChatService) {
        this.aiChatService = aiChatService;
    }

    /** 普通问答：同步返回，适合短回答或后台任务。 */
    @PostMapping("/chat")
    public Result<String> chat(@Valid @RequestBody ChatRequest request) {
        return Result.ok(aiChatService.chat(request.question()));
    }

    /** 流式问答（GET，方便浏览器 EventSource 直接连）。 */
    @GetMapping(value = "/chat/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter streamByGet(@RequestParam("question") String question) {
        return toSseEmitter(aiChatService.stream(question));
    }

    /** 流式问答（POST，问题放在请求体里，和普通问答结构一致）。 */
    @PostMapping(value = "/chat/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter streamByPost(@Valid @RequestBody ChatRequest request) {
        return toSseEmitter(aiChatService.stream(request.question()));
    }

    /**
     * 把模型的数据流接到 HTTP 响应流上。
     *
     * 数据流（关键，逐行看）：
     * 1. 构造 SseEmitter，超时设 0 表示不设上限（长回答可能超过默认 30 秒）；
     * 2. 订阅 Flux：模型每产出一段文本就回调 onNext；
     * 3. onNext 里 send(event().data(chunk))：Spring 会自动加上 "data:" 前缀和空行，
     *    浏览器 EventSource 每收到一帧就触发一次 onmessage；
     * 4. onComplete/onError 时关闭连接，否则前端会一直挂着等。
     */
    private SseEmitter toSseEmitter(reactor.core.publisher.Flux<String> flux) {
        SseEmitter emitter = new SseEmitter(0L);
        flux.subscribe(
                chunk -> {
                    try {
                        emitter.send(SseEmitter.event().data(chunk));
                    } catch (IOException e) {
                        // 客户端主动断开（关浏览器）时这里会抛异常，属于正常情况
                        emitter.completeWithError(e);
                    }
                },
                emitter::completeWithError,
                emitter::complete
        );
        return emitter;
    }
}
