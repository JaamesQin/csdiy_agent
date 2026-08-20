export interface CompletionDeltaEvent {
  choices?: Array<{
    delta?: {
      content?: unknown;
      role?: unknown;
    };
    finish_reason?: unknown;
  }>;
  error?: {
    message?: unknown;
  };
}

export interface CompletionResponse {
  choices?: Array<{
    message?: {
      content?: unknown;
    };
  }>;
}

export const MAX_SSE_FRAME_CHARS = 256 * 1024;
export const MAX_COMPLETION_CHARS = 256 * 1024;
export const MAX_COMPLETION_JSON_CHARS = 1024 * 1024;

export function parseSseBlock(block: string): CompletionDeltaEvent | "[DONE]" | null {
  const data = block
    .split(/\r?\n/)
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trimStart())
    .join("\n");

  if (!data) return null;
  if (data === "[DONE]") return "[DONE]";
  return JSON.parse(data) as CompletionDeltaEvent;
}

export async function readCompletionJson(response: Response): Promise<CompletionResponse> {
  if (!response.body) {
    throw new Error("浏览器未收到可读取的 JSON 响应。");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let body = "";
  let reachedEof = false;
  try {
    const declaredLength = Number(response.headers.get("Content-Length"));
    if (Number.isFinite(declaredLength) && declaredLength > MAX_COMPLETION_JSON_CHARS) {
      throw new Error("JSON 响应超过浏览器安全上限。");
    }

    while (true) {
      const { value, done } = await reader.read();
      reachedEof = done;
      body += decoder.decode(value ?? new Uint8Array(), { stream: !done });
      if (body.length > MAX_COMPLETION_JSON_CHARS) {
        throw new Error("JSON 响应超过浏览器安全上限。");
      }
      if (done) break;
    }
    return JSON.parse(body) as CompletionResponse;
  } finally {
    if (!reachedEof) {
      try {
        await reader.cancel();
      } catch {
        // Preserve the parse/size result if cancellation itself fails.
      }
    }
    reader.releaseLock();
  }
}

export async function readCompletionStream(
  response: Response,
  onContent: (content: string) => void,
): Promise<string> {
  if (!response.body) {
    throw new Error("浏览器未收到可读取的响应流。");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let content = "";
  let completed = false;
  let reachedEof = false;

  const consumeBlock = (block: string): void => {
    const event = parseSseBlock(block);
    if (!event) return;
    if (event === "[DONE]") {
      completed = true;
      return;
    }
    if (event.error) {
      const message = event.error.message;
      throw new Error(typeof message === "string" ? message : "流式响应中断");
    }

    const delta = event.choices?.[0]?.delta;
    if (typeof delta?.content === "string") {
      if (content.length + delta.content.length > MAX_COMPLETION_CHARS) {
        throw new Error("响应内容超过浏览器安全上限，请缩小问题范围后重试。");
      }
      content += delta.content;
      onContent(delta.content);
    }
  };

  try {
    while (!completed) {
      const { value, done } = await reader.read();
      reachedEof = done;
      buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });
      const blocks = buffer.split(/\r?\n\r?\n/);
      buffer = blocks.pop() ?? "";
      if (
        buffer.length > MAX_SSE_FRAME_CHARS ||
        blocks.some((block) => block.length > MAX_SSE_FRAME_CHARS)
      ) {
        throw new Error("响应流帧超过浏览器安全上限。");
      }

      for (const block of blocks) {
        consumeBlock(block);
        if (completed) break;
      }

      if (done) {
        if (!completed && buffer.trim()) consumeBlock(buffer);
        break;
      }
    }

    if (!completed) {
      throw new Error("响应流未以 [DONE] 正常结束。");
    }
    return content;
  } finally {
    if (!reachedEof) {
      try {
        await reader.cancel();
      } catch {
        // Preserve the protocol/abort result if cancellation itself fails.
      }
    }
    reader.releaseLock();
  }
}
