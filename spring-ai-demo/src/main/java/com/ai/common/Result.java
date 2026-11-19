package com.ai.common;

/**
 * 统一响应体。
 *
 * 为什么不直接返回字符串？
 * - 前端/脚本要能区分"成功但内容为空"和"调用失败"；
 * - 后续周次加 traceId、耗时、token 用量时，只需在这里加字段，接口结构不变。
 *
 * @param code 业务码：0 成功，非 0 失败
 * @param msg  提示信息
 * @param data 业务数据
 */
public record Result<T>(int code, String msg, T data) {

    public static <T> Result<T> ok(T data) {
        return new Result<>(0, "ok", data);
    }

    public static <T> Result<T> fail(String msg) {
        return new Result<>(500, msg, null);
    }

    /** 业务码与 HTTP 状态对齐，方便前端统一处理（400 参数错误、500 服务端错误）。 */
    public static <T> Result<T> fail(int code, String msg) {
        return new Result<>(code, msg, null);
    }
}
