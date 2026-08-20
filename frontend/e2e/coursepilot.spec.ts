import { expect, test, type Page, type Route } from "@playwright/test";

const password = "correct-horse-battery";

function uniqueUsername(prefix: string): string {
  const suffix = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`;
  return `${prefix}${suffix}`.slice(0, 30);
}

async function register(page: Page, prefix = "render"): Promise<string> {
  const username = uniqueUsername(prefix);
  await page.goto("/");
  await page.locator("#registerTab").click();
  await page.locator("#registerUsername").fill(username);
  await page.locator("#registerPassword").fill(password);
  await page.locator("#registerPasswordConfirm").fill(password);
  await page.locator("#registerForm button[type='submit']").click();
  await expect(page.locator("#currentUsername")).toHaveText(username);
  return username;
}

function sseBody(content: string, coursepilotContext?: string): string {
  const frames = [
    { choices: [{ delta: { role: "assistant" } }] },
    { choices: [{ delta: { content } }] },
    {
      choices: [{ delta: {}, finish_reason: "stop" }],
      ...(coursepilotContext === undefined
        ? {}
        : { coursepilot_context: coursepilotContext }),
    },
  ];
  return `${frames.map((frame) => `data: ${JSON.stringify(frame)}`).join("\n\n")}\n\ndata: [DONE]\n\n`;
}

async function fulfillSse(
  route: Route,
  content: string,
  coursepilotContext?: string,
): Promise<void> {
  await route.fulfill({
    status: 200,
    contentType: "text/event-stream; charset=utf-8",
    headers: { "Cache-Control": "no-cache" },
    body: sseBody(content, coursepilotContext),
  });
}

test("clears legacy browser storage and preserves the cookie session lifecycle", async ({
  context,
  page,
}) => {
  await page.addInitScript(() => {
    sessionStorage.setItem("coursepilot_api_key", "legacy-key");
    sessionStorage.setItem("coursepilot_api_base", "https://legacy.invalid");
    localStorage.setItem("coursepilot_anonymous_user", "legacy-user");
  });

  const username = await register(page, "auth");
  await expect
    .poll(() =>
      page.evaluate(() => ({
        apiBase: sessionStorage.getItem("coursepilot_api_base"),
        apiKey: sessionStorage.getItem("coursepilot_api_key"),
        anonymousUser: localStorage.getItem("coursepilot_anonymous_user"),
      })),
    )
    .toEqual({ apiBase: null, apiKey: null, anonymousUser: null });

  const cookies = await context.cookies();
  const sessionCookie = cookies.find((cookie) => cookie.name === "coursepilot_session");
  expect(sessionCookie?.httpOnly).toBe(true);
  expect(sessionCookie?.sameSite).toBe("Strict");

  await page.reload();
  await expect(page.locator("#currentUsername")).toHaveText(username);

  await page.locator("#messageInput").fill("/help code");
  await page.locator("#chatForm").evaluate((form: HTMLFormElement) => form.requestSubmit());
  const helpReply = page.locator(".message.assistant").last();
  await expect(helpReply.getByText("请分析下面的代码，并说明诊断与验证步骤：")).toBeVisible();
  await expect(helpReply.locator("pre code.language-cpp")).toContainText(
    "int main( { return 0; }",
  );
  await expect(helpReply.locator(".code-language")).toHaveText("cpp");
  await expect(helpReply.locator("pre")).not.toContainText("```cpp");

  let logoutRequests = 0;
  let markLogoutStarted: (() => void) | undefined;
  let releaseLogout: (() => void) | undefined;
  const logoutStarted = new Promise<void>((resolve) => {
    markLogoutStarted = resolve;
  });
  const logoutGate = new Promise<void>((resolve) => {
    releaseLogout = resolve;
  });
  await page.route("**/auth/logout", async (route) => {
    logoutRequests += 1;
    markLogoutStarted?.();
    await logoutGate;
    await route.continue();
  });
  await page.locator("#logoutButton").evaluate((button: HTMLButtonElement) => {
    button.click();
    button.click();
  });
  await logoutStarted;
  await page.waitForTimeout(50);
  expect(logoutRequests).toBe(1);
  await expect(page.locator("#logoutButton")).toBeDisabled();
  await expect(page.locator("#messageInput")).toBeDisabled();
  releaseLogout?.();
  await expect(page.locator("#authShell")).toBeVisible();
  await expect(page.locator("#appShell")).toBeHidden();
  await expect(page.locator("#loginTab")).toHaveAttribute("aria-selected", "true");
  await expect(page.locator("#loginTab")).toHaveAttribute("tabindex", "0");
  await expect(page.locator("#registerTab")).toHaveAttribute("tabindex", "-1");
  await expect(page.locator("#loginUsername")).toBeFocused();
});

test("ignores a stale session-restore response after interactive registration", async ({
  page,
}) => {
  let registrationRequests = 0;
  page.on("request", (request) => {
    if (request.url().endsWith("/auth/register") && request.method() === "POST") {
      registrationRequests += 1;
    }
  });
  let markRestoreStarted: (() => void) | undefined;
  let releaseRestore: (() => void) | undefined;
  let markRestoreFinished: (() => void) | undefined;
  const restoreStarted = new Promise<void>((resolve) => {
    markRestoreStarted = resolve;
  });
  const restoreGate = new Promise<void>((resolve) => {
    releaseRestore = resolve;
  });
  const restoreFinished = new Promise<void>((resolve) => {
    markRestoreFinished = resolve;
  });
  await page.route("**/auth/me", async (route) => {
    markRestoreStarted?.();
    await restoreGate;
    await route.fulfill({
      status: 401,
      contentType: "application/json",
      body: JSON.stringify({ error: { message: "stale restore" } }),
    });
    markRestoreFinished?.();
  });

  const username = uniqueUsername("race");
  await page.goto("/");
  await restoreStarted;
  await page.locator("#registerTab").click();
  await page.locator("#registerUsername").fill(username);
  await page.locator("#registerPassword").fill(password);
  await page.locator("#registerPasswordConfirm").fill(password);
  await page.locator("#registerForm").evaluate((form: HTMLFormElement) => {
    form.requestSubmit();
    form.requestSubmit();
  });
  await expect(page.locator("#currentUsername")).toHaveText(username);
  expect(registrationRequests).toBe(1);

  releaseRestore?.();
  await restoreFinished;
  await expect(page.locator("#appShell")).toBeVisible();
  await expect(page.locator("#currentUsername")).toHaveText(username);
});

test("renders streamed Markdown, native MathML, highlighted code, and safe links", async ({
  context,
  page,
}) => {
  const consoleErrors: string[] = [];
  const remoteRequests: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("request", (request) => {
    if (request.url().startsWith("https://attacker.example")) {
      remoteRequests.push(request.url());
    }
  });
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await register(page, "rich");
  consoleErrors.length = 0;

  const richReply = [
    "# Lecture 2 学习卡",
    "",
    "> 下面的内容来自已审核 StudyKit。",
    "",
    "- 理解梯度",
    "- 完成验证",
    "",
    "| 阶段 | 状态 |",
    "| --- | --- |",
    "| 反向传播 | ready |",
    "",
    String.raw`行内公式 $\theta_{k+1}=\theta_k-\eta\nabla J(\theta_k)$。`,
    "",
    String.raw`$$\nabla_\theta J=0$$`,
    "",
    "```python",
    "def train(step):",
    "    return step + 1",
    "```",
    "",
    "[课程主页](https://example.com/course)",
    "",
    "![tracking](https://attacker.example/pixel.png)",
    "",
    '<img src=x onerror="window.__coursepilotXss = true"><script>window.__coursepilotXss = true</script>',
  ].join("\n");

  let chatRequestCount = 0;
  await page.route("**/v1/chat/completions", async (route) => {
    chatRequestCount += 1;
    const request = route.request();
    const headers = request.headers();
    const body = request.postDataJSON() as Record<string, unknown>;
    expect(headers.authorization).toBeUndefined();
    expect(headers["x-csrf-token"]).toBeTruthy();
    expect(body.user).toBeUndefined();
    expect(body.model).toBe("coursepilot-probe");
    expect(body.stream).toBe(true);
    if (chatRequestCount === 1) {
      expect(body.coursepilot_context).toBeUndefined();
      await fulfillSse(route, richReply, "signed-browser-context");
    } else if (chatRequestCount === 2) {
      expect(body.coursepilot_context).toBe("signed-browser-context");
      await fulfillSse(route, "## 上下文已续接");
    } else {
      expect(body.coursepilot_context).toBeUndefined();
      await fulfillSse(route, "## 上下文已清空");
    }
  });

  await page.getByRole("button", { name: "查看 StudyKit" }).click();
  await expect(page.locator("#messageInput")).toHaveValue(
    "查看 MIT 6.7960 第 2 讲的 StudyKit。",
  );
  expect(chatRequestCount).toBe(0);
  await page.locator("#chatForm").evaluate((form: HTMLFormElement) => form.requestSubmit());

  const reply = page.locator(".message.assistant").last();
  await expect(reply.locator("h1")).toHaveText("Lecture 2 学习卡");
  await expect(reply.locator(".table-scroll > table")).toContainText("反向传播");
  await expect(reply.locator("code.hljs.language-python")).toContainText("def train");
  await expect(reply.locator(".katex math")).toHaveCount(2);
  await expect(reply.locator("annotation")).toHaveCount(0);
  await expect(reply.locator("img, script")).toHaveCount(0);
  await expect(reply.locator("a")).toHaveAttribute("target", "_blank");
  await expect(reply.locator("a")).toHaveAttribute("rel", "noopener noreferrer");
  await reply.locator(".copy-code-button").click();
  await expect(reply.locator(".copy-code-button")).toHaveText("已复制");

  expect(await page.evaluate(() => (window as Window & { __coursepilotXss?: boolean }).__coursepilotXss)).not.toBe(
    true,
  );
  expect(remoteRequests).toEqual([]);
  expect(consoleErrors).toEqual([]);

  await page.locator("#messageInput").fill("继续当前上下文");
  await page.locator("#chatForm").evaluate((form: HTMLFormElement) => form.requestSubmit());
  await expect(page.locator(".message.assistant h2").last()).toHaveText("上下文已续接");

  await page.locator("#clearButton").click();
  await page.locator("#messageInput").fill("清空后重新开始");
  await page.locator("#chatForm").evaluate((form: HTMLFormElement) => form.requestSubmit());
  await expect(page.locator(".message.assistant h2").last()).toHaveText("上下文已清空");
});

test("keeps raw assistant Markdown in multi-turn non-streaming history", async ({ page }) => {
  await register(page, "history");
  await page.locator(".stream-toggle").click();
  await expect(page.locator("#streamToggle")).not.toBeChecked();

  const requestBodies: Array<Record<string, unknown>> = [];
  await page.route("**/v1/chat/completions", async (route) => {
    requestBodies.push(route.request().postDataJSON() as Record<string, unknown>);
    const reply =
      requestBodies.length === 1
        ? "**第一轮原始回复**"
        : requestBodies.length === 2
          ? "## 第二轮"
          : "x".repeat(256 * 1024 + 1);
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        choices: [{ message: { role: "assistant", content: reply } }],
      }),
    });
  });

  await page.locator("#messageInput").fill('<img src=x onerror="alert(1)"> 第一问');
  await page.locator("#chatForm").evaluate((form: HTMLFormElement) => form.requestSubmit());
  await expect(page.locator(".message.assistant strong")).toHaveText("第一轮原始回复");
  await expect(page.locator(".message.user img")).toHaveCount(0);

  await page.locator("#messageInput").fill("第二问");
  await page.locator("#chatForm").evaluate((form: HTMLFormElement) => form.requestSubmit());
  await expect(page.locator(".message.assistant h2")).toHaveText("第二轮");

  const secondMessages = requestBodies[1]?.messages as Array<Record<string, unknown>>;
  expect(secondMessages).toEqual([
    { role: "user", content: '<img src=x onerror="alert(1)"> 第一问' },
    { role: "assistant", content: "**第一轮原始回复**" },
    { role: "user", content: "第二问" },
  ]);

  await page.locator("#messageInput").fill("测试非流式响应上限");
  await page.locator("#chatForm").evaluate((form: HTMLFormElement) => form.requestSubmit());
  const oversizedReply = page.locator(".message.assistant.error").last();
  await expect(oversizedReply.locator(".message-text")).toHaveText(
    "请求失败：响应内容超过浏览器安全上限，请缩小问题范围后重试。",
  );
  await expect(oversizedReply.locator("a, strong, img")).toHaveCount(0);
});

test("keeps a stream error as plain text when rich rendering is already queued", async ({
  page,
}) => {
  await register(page, "streamerror");
  const body = [
    `data: ${JSON.stringify({ choices: [{ delta: { content: "[unsafe](https://attacker.example/link)" } }] })}`,
    `data: ${JSON.stringify({ error: { message: "**上游失败**" } })}`,
    "data: [DONE]",
    "",
  ].join("\n\n");
  await page.route("**/v1/chat/completions", (route) =>
    route.fulfill({
      status: 200,
      contentType: "text/event-stream; charset=utf-8",
      body,
    }),
  );

  await page.locator("#messageInput").fill("触发流错误");
  await page.locator("#chatForm").evaluate((form: HTMLFormElement) => form.requestSubmit());

  const reply = page.locator(".message.assistant.error").last();
  await expect(reply).toBeVisible();
  await page.evaluate(
    () =>
      new Promise<void>((resolve) => {
        requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
      }),
  );
  await expect(reply.locator(".message-text")).toHaveText("请求失败：**上游失败**");
  await expect(reply.locator("a, strong")).toHaveCount(0);
});

test("stops an active stream without adding a partial assistant turn to history", async ({
  page,
}) => {
  await register(page, "stop");
  const requestBodies: Array<Record<string, unknown>> = [];
  let callCount = 0;

  await page.route("**/v1/chat/completions", async (route) => {
    callCount += 1;
    requestBodies.push(route.request().postDataJSON() as Record<string, unknown>);
    if (callCount === 1) {
      await new Promise((resolve) => setTimeout(resolve, 500));
      try {
        await fulfillSse(route, "这段回复应被丢弃");
      } catch {
        // The browser request was intentionally aborted by the Stop button.
      }
      return;
    }
    await fulfillSse(route, "## 已恢复");
  });

  await page.locator("#messageInput").fill("请停止这一轮");
  await page.locator("#chatForm").evaluate((form: HTMLFormElement) => form.requestSubmit());
  await expect(page.locator("#stopButton")).toBeVisible();
  await expect(page.locator("#messageInput")).toBeDisabled();
  await page.locator("#stopButton").click();
  await expect(page.locator(".message.assistant").last()).toContainText("生成已停止。");
  await expect(page.locator("#messageInput")).toBeEnabled();

  await page.locator("#messageInput").fill("继续下一轮");
  await page.locator("#chatForm").evaluate((form: HTMLFormElement) => form.requestSubmit());
  await expect(page.locator(".message.assistant h2")).toHaveText("已恢复");

  const secondMessages = requestBodies[1]?.messages as Array<Record<string, unknown>>;
  expect(secondMessages).toEqual([
    { role: "user", content: "请停止这一轮" },
    { role: "user", content: "继续下一轮" },
  ]);
});

test("contains wide learning content on a mobile viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await register(page, "mobile");

  const wideReply = [
    "| very long heading | another long heading | third heading |",
    "| --- | --- | --- |",
    `| ${"table-value-".repeat(18)} | content | content |`,
    "",
    String.raw`$$\sum_{i=1}^{100}\frac{\partial J(\theta_i)}{\partial \theta_i}=\alpha_1+\alpha_2+\alpha_3+\alpha_4+\alpha_5+\alpha_6$$`,
    "",
    "```typescript",
    `const value = "${"unbroken-code-".repeat(25)}";`,
    "```",
    "",
    `[${"long-link-label-".repeat(20)}](https://example.com/${"path".repeat(30)})`,
  ].join("\n");

  await page.route("**/v1/chat/completions", (route) => fulfillSse(route, wideReply));
  await page.locator("#messageInput").fill("移动端渲染测试");
  await page.locator("#chatForm").evaluate((form: HTMLFormElement) => form.requestSubmit());
  await expect(page.locator(".message.assistant table")).toBeVisible();

  const widths = await page.evaluate(() => ({
    client: document.documentElement.clientWidth,
    scroll: document.documentElement.scrollWidth,
  }));
  expect(widths.scroll).toBeLessThanOrEqual(widths.client + 1);
  await expect(page.locator("#chatForm")).toBeVisible();
});
