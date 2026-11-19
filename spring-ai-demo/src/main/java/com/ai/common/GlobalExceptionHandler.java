package com.ai.common;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestControllerAdvice;

/**
 * 全局异常处理：把 500 堆栈变成结构化 JSON。
 *
 * 为什么必须有：
 * - 第 1 次启动忘了配 Key 时，Spring 只返回 {"status":500,"error":"Internal Server Error"}，
 *   看不出原因；有了这层就能直接看到"模型调用失败 + 具体原因"；
 * - 前端拿到统一结构，不用为错误单独写解析逻辑。
 */
@RestControllerAdvice
public class GlobalExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    /** 参数校验失败（@Valid 触发），属于客户端错误。 */
    @ExceptionHandler(MethodArgumentNotValidException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public Result<Void> handleInvalid(MethodArgumentNotValidException e) {
        String msg = e.getBindingResult().getFieldErrors().stream()
                .map(err -> err.getField() + ": " + err.getDefaultMessage())
                .reduce((a, b) -> a + "; " + b)
                .orElse("参数不合法");
        return Result.fail(400, msg);
    }

    /** 模型调用失败（Key 错误、超时、限流等），属于服务端外部依赖问题。 */
    @ExceptionHandler(Exception.class)
    @ResponseStatus(HttpStatus.INTERNAL_SERVER_ERROR)
    public Result<Void> handleOther(Exception e) {
        log.error("接口异常", e);
        String reason = e.getMessage() == null ? e.getClass().getSimpleName() : e.getMessage();
        // 截断过长的堆栈式信息，避免把内部细节整段抛给前端
        if (reason.length() > 200) {
            reason = reason.substring(0, 200) + "...";
        }
        return Result.fail("调用模型失败：" + reason);
    }
}
