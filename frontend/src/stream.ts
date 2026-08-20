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
  coursepilot_context?: unknown;
}

export interface CompletionResponse {
  choices?: Array<{
    message?: {
      content?: unknown;
    };
  }>;
  coursepilot_context?: string;
}

export interface CompletionStreamResult {
  content: string;
  coursepilotContext?: string;
}

export const MAX_SSE_FRAME_CHARS = 256 * 1024;
export const MAX_COMPLETION_CHARS = 256 * 1024;
export const MAX_COMPLETION_JSON_CHARS = 1024 * 1024;
export const MAX_COURSEPILOT_CONTEXT_CHARS = 16 * 1024;

function parseCoursepilotContext(value: unknown): string | undefined {
  if (value === undefined) return undefined;
  if (typeof value !== "string" || value.length > MAX_COURSEPILOT_CONTEXT_CHARS) {
    throw new Error("服务返回了无效的对话连续状态。");
  }
  return value;
}

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
    const parsed = JSON.parse(body) as CompletionResponse & {
      coursepilot_context?: unknown;
    };
    const coursepilotContext = parseCoursepilotContext(parsed.coursepilot_context);
    if (coursepilotContext === undefined) delete parsed.coursepilot_context;
    else parsed.coursepilot_context = coursepilotContext;
    return parsed as CompletionResponse;
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
): Promise<CompletionStreamResult> {
  if (!response.body) {
    throw new Error("浏览器未收到可读取的响应流。");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let content = "";
  let coursepilotContext: string | undefined;
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

    const nextContext = parseCoursepilotContext(event.coursepilot_context);
    if (nextContext !== undefined) coursepilotContext = nextContext;

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
    return {
      content,
      ...(coursepilotContext === undefined ? {} : { coursepilotContext }),
    };
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
