import { describe, expect, it } from "vitest";

import {
  MAX_COMPLETION_CHARS,
  MAX_COMPLETION_JSON_CHARS,
  MAX_SSE_FRAME_CHARS,
  parseSseBlock,
  readCompletionJson,
  readCompletionStream,
} from "./stream";

const encoder = new TextEncoder();

function streamingResponse(chunks: string[]): Response {
  return new Response(
    new ReadableStream<Uint8Array>({
      start(controller) {
        for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
        controller.close();
      },
    }),
    { headers: { "Content-Type": "text/event-stream" } },
  );
}

describe("OpenAI-compatible SSE parsing", () => {
  it("parses CRLF and multiline data frames", () => {
    const event = parseSseBlock(
      'event: message\r\ndata: {"choices":[{"delta":\r\ndata: {"content":"你好"}}]}',
    );
    expect(event).toEqual({ choices: [{ delta: { content: "你好" } }] });
    expect(parseSseBlock("data: [DONE]")).toBe("[DONE]");
  });

  it("collects content and requires the terminal marker", async () => {
    const deltas: string[] = [];
    const response = streamingResponse([
      'data: {"choices":[{"delta":{"role":"assistant"}}]}\n\n',
      'data: {"choices":[{"delta":{"content":"# 你"}}]}\n\n',
      'data: {"choices":[{"delta":{"content":"好"}}]}\n\n',
      'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\n',
      "data: [DONE]\n\n",
    ]);

    await expect(readCompletionStream(response, (delta) => deltas.push(delta))).resolves.toBe(
      "# 你好",
    );
    expect(deltas).toEqual(["# 你", "好"]);
  });

  it("rejects a truncated stream", async () => {
    const response = streamingResponse([
      'data: {"choices":[{"delta":{"content":"partial"}}]}\n\n',
    ]);
    await expect(readCompletionStream(response, () => undefined)).rejects.toThrow(
      "响应流未以 [DONE] 正常结束。",
    );
  });

  it("surfaces a sanitized server stream error message", async () => {
    const response = streamingResponse([
      'data: {"error":{"message":"上游暂时不可用"},"choices":[{"delta":{},"finish_reason":"stop"}]}\n\n',
      "data: [DONE]\n\n",
    ]);
    await expect(readCompletionStream(response, () => undefined)).rejects.toThrow(
      "上游暂时不可用",
    );
  });

  it("cancels a response body that remains open after the terminal marker", async () => {
    let cancelled = false;
    const response = new Response(
      new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(encoder.encode("data: [DONE]\n\n"));
        },
        cancel() {
          cancelled = true;
        },
      }),
    );

    await expect(readCompletionStream(response, () => undefined)).resolves.toBe("");
    expect(cancelled).toBe(true);
  });

  it("cancels an unterminated frame before unbounded buffering", async () => {
    let pulls = 0;
    let cancelled = false;
    const chunk = encoder.encode("x".repeat(64 * 1024));
    const response = new Response(
      new ReadableStream<Uint8Array>({
        pull(controller) {
          pulls += 1;
          controller.enqueue(chunk);
        },
        cancel() {
          cancelled = true;
        },
      }),
    );

    await expect(readCompletionStream(response, () => undefined)).rejects.toThrow(
      "响应流帧超过浏览器安全上限。",
    );
    expect(cancelled).toBe(true);
    expect(pulls).toBeLessThanOrEqual(Math.ceil(MAX_SSE_FRAME_CHARS / chunk.length) + 2);
  });

  it("rejects cumulative assistant output above the browser limit", async () => {
    const delta = "x".repeat(64 * 1024);
    const frames = Array.from(
      { length: Math.ceil(MAX_COMPLETION_CHARS / delta.length) + 1 },
      () => `data: ${JSON.stringify({ choices: [{ delta: { content: delta } }] })}\n\n`,
    );
    const response = streamingResponse(frames);

    await expect(readCompletionStream(response, () => undefined)).rejects.toThrow(
      "响应内容超过浏览器安全上限，请缩小问题范围后重试。",
    );
  });

  it("reads a bounded non-stream completion response", async () => {
    const response = new Response(
      JSON.stringify({ choices: [{ message: { content: "## 完成" } }] }),
      { headers: { "Content-Type": "application/json" } },
    );

    await expect(readCompletionJson(response)).resolves.toEqual({
      choices: [{ message: { content: "## 完成" } }],
    });
  });

  it("cancels an oversized non-stream completion body", async () => {
    let pulls = 0;
    let cancelled = false;
    const chunk = encoder.encode("x".repeat(64 * 1024));
    const response = new Response(
      new ReadableStream<Uint8Array>({
        pull(controller) {
          pulls += 1;
          controller.enqueue(chunk);
        },
        cancel() {
          cancelled = true;
        },
      }),
    );

    await expect(readCompletionJson(response)).rejects.toThrow(
      "JSON 响应超过浏览器安全上限。",
    );
    expect(cancelled).toBe(true);
    expect(pulls).toBeLessThanOrEqual(
      Math.ceil(MAX_COMPLETION_JSON_CHARS / chunk.length) + 2,
    );
  });
});
