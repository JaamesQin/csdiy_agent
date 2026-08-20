import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from "react";

import {
  MAX_COMPLETION_CHARS,
  readCompletionJson,
  readCompletionStream,
} from "./stream";

type MessageRole = "assistant" | "user";
type MessagePresentation = "markdown" | "plain";

interface ChatMessage {
  role: MessageRole;
  content: string;
}

interface DisplayMessage {
  id: number;
  role: MessageRole;
  raw: string;
  presentation: MessagePresentation;
  streaming: boolean;
  error: boolean;
}

interface PublicUser {
  id: string;
  username: string;
  created_at: string;
}

interface SessionResponse {
  user: PublicUser;
  csrf_token: string;
}

interface ErrorEnvelope {
  error?: {
    message?: unknown;
  };
}

interface StarterPrompt {
  title: string;
  description: string;
  prompt: string;
}

const RICH_RENDER_INTERVAL_MS = 160;
const MAX_RICH_PREVIEW_CHARS = 64 * 1024;
const MAX_CONVERSATION_CHARS = 1_000_000;

const starterPrompts: StarterPrompt[] = [
  {
    title: "查看当前功能",
    description: "列出已上线能力与具体使用方式",
    prompt: "/help",
  },
  {
    title: "建立学习画像",
    description: "保存明确提供的方向、时间和基础",
    prompt: "我想学习系统方向，每周可以投入 6 小时，而且有 Python 基础。",
  },
  {
    title: "查看与纠正画像",
    description: "检查当前账号保存的最小事实",
    prompt: "查看我的学习画像",
  },
  {
    title: "删除学习画像",
    description: "清除当前账号的服务器端画像",
    prompt: "删除我的画像",
  },
  {
    title: "课程导航",
    description: "检索现有课程表并区分三类就绪状态",
    prompt: "推荐一门深度学习课程，并标明在线 StudyKit 状态。",
  },
  {
    title: "查看 StudyKit",
    description: "只读取 Schema 合法且人工批准的学习包",
    prompt: "查看 MIT 6.7960 第 2 讲的 StudyKit。",
  },
  {
    title: "课程概念解释",
    description: "按定义、直觉、误区和来源分层说明",
    prompt: "解释 MIT 6.7960 第 2 讲的反向传播。",
  },
  {
    title: "练习选择",
    description: "练习和反馈不跨会话保存或累计评分",
    prompt: "给我一道 MIT 6.7960 第 2 讲的调试练习。",
  },
  {
    title: "代码辅导",
    description: "支持 CSDIY 多语言，只做静态分析",
    prompt: [
      "请做静态代码辅导，说明诊断和验证步骤：",
      "```python",
      "def add(x, values=[]):",
      "    values.append(x)",
      "    return values",
      "```",
    ].join("\n"),
  },
];

function isSessionResponse(value: unknown): value is SessionResponse {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<SessionResponse>;
  return (
    typeof candidate.csrf_token === "string" &&
    !!candidate.user &&
    typeof candidate.user.id === "string" &&
    typeof candidate.user.username === "string" &&
    typeof candidate.user.created_at === "string"
  );
}

function isAbortError(error: unknown): boolean {
  return (
    typeof error === "object" &&
    error !== null &&
    "name" in error &&
    error.name === "AbortError"
  );
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as ErrorEnvelope;
    return typeof body.error?.message === "string"
      ? body.error.message
      : `HTTP ${response.status}`;
  } catch {
    return `HTTP ${response.status}`;
  }
}

async function authenticate(
  path: "/auth/login" | "/auth/register",
  username: string,
  password: string,
): Promise<SessionResponse> {
  const response = await fetch(path, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!response.ok) throw new Error(await errorMessage(response));
  const session: unknown = await response.json();
  if (!isSessionResponse(session)) throw new Error("登录服务返回了无效会话。");
  return session;
}

function MarkdownContent({ source, streaming }: { source: string; streaming: boolean }) {
  const targetRef = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    let active = true;
    void import("./renderer")
      .then(({ renderAssistantContent }) => {
        if (active && targetRef.current) renderAssistantContent(targetRef.current, source);
      })
      .catch(() => {
        if (active && targetRef.current) {
          targetRef.current.classList.add("plain-text");
          targetRef.current.replaceChildren(document.createTextNode(source));
        }
      });
    return () => {
      active = false;
    };
  }, [source]);

  return (
    <div
      ref={targetRef}
      className={`message-text markdown-body${streaming ? " streaming" : ""}`}
    />
  );
}

function ConversationMessage({ message }: { message: DisplayMessage }) {
  const classes = ["message", message.role, message.error ? "error" : ""]
    .filter(Boolean)
    .join(" ");
  return (
    <article className={classes}>
      <div className="avatar" aria-hidden="true">
        {message.role === "user" ? "你" : "C"}
      </div>
      <div className="message-content">
        <p className="message-meta">{message.role === "user" ? "你" : "CoursePilot"}</p>
        {message.role === "assistant" && message.presentation === "markdown" ? (
          <MarkdownContent source={message.raw} streaming={message.streaming} />
        ) : (
          <div
            className={`message-text plain-text${message.streaming ? " streaming" : ""}`}
          >
            {message.raw}
          </div>
        )}
      </div>
    </article>
  );
}

export default function App() {
  const [session, setSession] = useState<SessionResponse | null>(null);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [authError, setAuthError] = useState("");
  const [authBusy, setAuthBusy] = useState(false);
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [streamEnabled, setStreamEnabled] = useState(true);
  const [busy, setBusy] = useState(false);
  const [logoutBusy, setLogoutBusy] = useState(false);
  const [inputHint, setInputHint] = useState("画像按账号隔离");

  const sessionRef = useRef<SessionResponse | null>(null);
  const authBusyRef = useRef(false);
  const logoutBusyRef = useRef(false);
  const historyRef = useRef<ChatMessage[]>([]);
  const controllerRef = useRef<AbortController | null>(null);
  const authGenerationRef = useRef(0);
  const chatGenerationRef = useRef(0);
  const nextMessageIdRef = useRef(1);
  const renderDraftsRef = useRef(new Map<number, string>());
  const renderFramesRef = useRef(new Map<number, number>());
  const lastRichRenderRef = useRef(new Map<number, number>());
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const loginUsernameRef = useRef<HTMLInputElement>(null);
  const loginPasswordRef = useRef<HTMLInputElement>(null);
  const registerUsernameRef = useRef<HTMLInputElement>(null);
  const registerPasswordRef = useRef<HTMLInputElement>(null);
  const registerPasswordConfirmRef = useRef<HTMLInputElement>(null);
  const conversationRef = useRef<HTMLElement>(null);

  const commitSession = useCallback((value: SessionResponse | null) => {
    sessionRef.current = value;
    setSession(value);
  }, []);

  const cancelScheduledRender = useCallback((messageId: number) => {
    const frame = renderFramesRef.current.get(messageId);
    if (frame !== undefined) window.cancelAnimationFrame(frame);
    renderFramesRef.current.delete(messageId);
    renderDraftsRef.current.delete(messageId);
    lastRichRenderRef.current.delete(messageId);
  }, []);

  const cancelAllScheduledRenders = useCallback(() => {
    for (const frame of renderFramesRef.current.values()) {
      window.cancelAnimationFrame(frame);
    }
    renderFramesRef.current.clear();
    renderDraftsRef.current.clear();
    lastRichRenderRef.current.clear();
  }, []);

  const updateDisplayMessage = useCallback(
    (messageId: number, update: Partial<Omit<DisplayMessage, "id" | "role">>) => {
      setMessages((current) =>
        current.map((message) =>
          message.id === messageId ? { ...message, ...update } : message,
        ),
      );
    },
    [],
  );

  const scheduleRichPreview = useCallback((messageId: number, raw: string) => {
    renderDraftsRef.current.set(messageId, raw);
    if (renderFramesRef.current.has(messageId)) return;

    const renderWhenDue = (now: number): void => {
      const last = lastRichRenderRef.current.get(messageId) ?? -Infinity;
      if (now - last < RICH_RENDER_INTERVAL_MS) {
        renderFramesRef.current.set(
          messageId,
          window.requestAnimationFrame(renderWhenDue),
        );
        return;
      }

      renderFramesRef.current.delete(messageId);
      lastRichRenderRef.current.set(messageId, now);
      const next = renderDraftsRef.current.get(messageId);
      renderDraftsRef.current.delete(messageId);
      if (next === undefined) return;
      setMessages((current) =>
        current.map((message) =>
          message.id === messageId && message.presentation === "markdown"
            ? { ...message, raw: next }
            : message,
        ),
      );
    };

    renderFramesRef.current.set(messageId, window.requestAnimationFrame(renderWhenDue));
  }, []);

  const finalizeDisplayMessage = useCallback(
    (
      messageId: number,
      raw: string,
      presentation: MessagePresentation,
      error = false,
    ) => {
      cancelScheduledRender(messageId);
      updateDisplayMessage(messageId, {
        raw,
        presentation,
        streaming: false,
        error,
      });
    },
    [cancelScheduledRender, updateDisplayMessage],
  );

  const clearConversation = useCallback(
    (focus = true) => {
      chatGenerationRef.current += 1;
      controllerRef.current?.abort();
      controllerRef.current = null;
      cancelAllScheduledRenders();
      historyRef.current = [];
      setMessages([]);
      setBusy(false);
      setDraft("");
      if (focus && sessionRef.current) {
        window.setTimeout(() => textareaRef.current?.focus(), 0);
      }
    },
    [cancelAllScheduledRenders],
  );

  const showAuth = useCallback(
    (message = "") => {
      authGenerationRef.current += 1;
      clearConversation(false);
      commitSession(null);
      setAuthMode("login");
      authBusyRef.current = false;
      logoutBusyRef.current = false;
      setAuthBusy(false);
      setLogoutBusy(false);
      setAuthError(message);
    },
    [clearConversation, commitSession],
  );

  const showApp = useCallback(
    (nextSession: SessionResponse, clearExistingConversation = false) => {
      if (clearExistingConversation) clearConversation(false);
      logoutBusyRef.current = false;
      setLogoutBusy(false);
      commitSession(nextSession);
      setAuthError("");
      setInputHint("画像按账号隔离");
    },
    [clearConversation, commitSession],
  );

  useEffect(() => {
    const generation = ++authGenerationRef.current;
    const controller = new AbortController();

    void (async () => {
      try {
        const response = await fetch("/auth/me", {
          credentials: "same-origin",
          cache: "no-store",
          signal: controller.signal,
        });
        if (generation !== authGenerationRef.current) return;
        if (!response.ok) {
          showAuth();
          return;
        }
        const restored: unknown = await response.json();
        if (!isSessionResponse(restored)) throw new Error("invalid session response");
        if (generation !== authGenerationRef.current) return;
        showApp(restored);
      } catch (error) {
        if (generation !== authGenerationRef.current || isAbortError(error)) return;
        showAuth("无法连接本地服务，请稍后重试。");
      }
    })();

    return () => controller.abort();
  }, [showApp, showAuth]);

  useEffect(
    () => () => {
      controllerRef.current?.abort();
      for (const frame of renderFramesRef.current.values()) {
        window.cancelAnimationFrame(frame);
      }
    },
    [],
  );

  useLayoutEffect(() => {
    document.title = session ? "CoursePilot · 我的学习空间" : "CoursePilot · 登录";
    if (session) textareaRef.current?.focus();
    else if (authMode === "login") loginUsernameRef.current?.focus();
    else registerUsernameRef.current?.focus();
  }, [authMode, session]);

  useLayoutEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.rows = 1;
    const lineHeight = 26;
    const verticalPadding = 20;
    const rows = Math.ceil((textarea.scrollHeight - verticalPadding) / lineHeight);
    textarea.rows = Math.max(1, Math.min(rows, 7));
  }, [draft]);

  useEffect(() => {
    const article = conversationRef.current?.lastElementChild;
    if (!(article instanceof HTMLElement)) return;
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    article.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "end" });
  }, [messages]);

  async function submitLogin(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (authBusyRef.current || logoutBusyRef.current) return;
    authBusyRef.current = true;
    const form = event.currentTarget;
    const generation = ++authGenerationRef.current;
    setAuthBusy(true);
    setAuthError("正在登录…");
    try {
      const nextSession = await authenticate(
        "/auth/login",
        loginUsernameRef.current?.value ?? "",
        loginPasswordRef.current?.value ?? "",
      );
      if (generation !== authGenerationRef.current) return;
      form.reset();
      showApp(nextSession, true);
    } catch (error) {
      if (generation !== authGenerationRef.current) return;
      setAuthError(error instanceof Error ? error.message : "登录失败。");
    } finally {
      if (generation === authGenerationRef.current) {
        authBusyRef.current = false;
        setAuthBusy(false);
      }
    }
  }

  async function submitRegistration(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (authBusyRef.current || logoutBusyRef.current) return;
    const form = event.currentTarget;
    const password = registerPasswordRef.current?.value ?? "";
    if (password !== (registerPasswordConfirmRef.current?.value ?? "")) {
      setAuthError("两次输入的密码不一致。");
      return;
    }

    authBusyRef.current = true;
    const generation = ++authGenerationRef.current;
    setAuthBusy(true);
    setAuthError("正在创建账号…");
    try {
      const nextSession = await authenticate(
        "/auth/register",
        registerUsernameRef.current?.value ?? "",
        password,
      );
      if (generation !== authGenerationRef.current) return;
      form.reset();
      showApp(nextSession, true);
    } catch (error) {
      if (generation !== authGenerationRef.current) return;
      setAuthError(error instanceof Error ? error.message : "注册失败。");
    } finally {
      if (generation === authGenerationRef.current) {
        authBusyRef.current = false;
        setAuthBusy(false);
      }
    }
  }

  async function logout(): Promise<void> {
    const currentSession = sessionRef.current;
    if (!currentSession || logoutBusyRef.current) return;
    logoutBusyRef.current = true;
    setLogoutBusy(true);
    const generation = ++authGenerationRef.current;
    controllerRef.current?.abort();
    try {
      const response = await fetch("/auth/logout", {
        method: "POST",
        credentials: "same-origin",
        headers: { "X-CSRF-Token": currentSession.csrf_token },
      });
      if (generation !== authGenerationRef.current) return;
      if (!response.ok && response.status !== 401) {
        throw new Error(await errorMessage(response));
      }
      showAuth();
    } catch (error) {
      if (generation !== authGenerationRef.current) return;
      const message = error instanceof Error ? error.message : "未知错误";
      setInputHint(`退出失败：${message}`);
    } finally {
      if (generation === authGenerationRef.current) {
        logoutBusyRef.current = false;
        setLogoutBusy(false);
      }
    }
  }

  async function sendMessage(rawMessage: string): Promise<void> {
    const message = rawMessage.trim();
    const currentSession = sessionRef.current;
    if (
      !message ||
      busy ||
      logoutBusyRef.current ||
      controllerRef.current ||
      !currentSession
    ) return;
    const pendingHistorySize = historyRef.current.reduce(
      (total, item) => total + item.content.length,
      message.length,
    );
    if (pendingHistorySize > MAX_CONVERSATION_CHARS) {
      setInputHint("当前对话已达到浏览器安全上限，请清空对话后继续。");
      return;
    }

    const generation = ++chatGenerationRef.current;
    const controller = new AbortController();
    controllerRef.current = controller;
    const requestHistory = [...historyRef.current, { role: "user" as const, content: message }];
    historyRef.current = requestHistory;
    const userMessageId = nextMessageIdRef.current++;
    const assistantMessageId = nextMessageIdRef.current++;
    setMessages((current) => [
      ...current,
      {
        id: userMessageId,
        role: "user",
        raw: message,
        presentation: "plain",
        streaming: false,
        error: false,
      },
      {
        id: assistantMessageId,
        role: "assistant",
        raw: "",
        presentation: "markdown",
        streaming: true,
        error: false,
      },
    ]);
    setDraft("");
    setBusy(true);
    let outputRaw = "";
    let richPreviewLimited = false;

    try {
      const response = await fetch("/v1/chat/completions", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": currentSession.csrf_token,
        },
        body: JSON.stringify({
          model: "coursepilot-probe",
          messages: requestHistory,
          stream: streamEnabled,
        }),
        signal: controller.signal,
      });

      if (generation !== chatGenerationRef.current) return;
      if (response.status === 401) {
        showAuth("登录已过期，请重新登录。");
        return;
      }
      if (!response.ok) throw new Error(await errorMessage(response));

      if (streamEnabled) {
        const streamed = await readCompletionStream(response, (delta) => {
          if (generation !== chatGenerationRef.current) return;
          outputRaw += delta;
          if (outputRaw.length <= MAX_RICH_PREVIEW_CHARS) {
            scheduleRichPreview(assistantMessageId, outputRaw);
          } else if (!richPreviewLimited) {
            richPreviewLimited = true;
            cancelScheduledRender(assistantMessageId);
            updateDisplayMessage(assistantMessageId, {
              raw: `${outputRaw.slice(0, MAX_RICH_PREVIEW_CHARS)}\n\n…正在接收较长回复，完成后再渲染…`,
              presentation: "plain",
            });
          }
        });
        if (streamed !== outputRaw) outputRaw = streamed;
      } else {
        const body = await readCompletionJson(response);
        const content = body.choices?.[0]?.message?.content;
        outputRaw = typeof content === "string" ? content : "";
      }

      if (generation !== chatGenerationRef.current) return;
      if (outputRaw.length > MAX_COMPLETION_CHARS) {
        throw new Error("响应内容超过浏览器安全上限，请缩小问题范围后重试。");
      }
      if (!outputRaw.trim()) throw new Error("服务返回了空回复。");
      finalizeDisplayMessage(assistantMessageId, outputRaw, "markdown");
      historyRef.current = [
        ...requestHistory,
        { role: "assistant", content: outputRaw },
      ];
      setInputHint("画像按账号隔离");
    } catch (error) {
      if (generation !== chatGenerationRef.current) return;
      if (isAbortError(error)) {
        if (outputRaw) {
          finalizeDisplayMessage(assistantMessageId, outputRaw, "markdown");
        } else {
          finalizeDisplayMessage(assistantMessageId, "生成已停止。", "plain");
        }
      } else {
        const messageText = error instanceof Error ? error.message : "未知错误";
        finalizeDisplayMessage(
          assistantMessageId,
          `请求失败：${messageText}`,
          "plain",
          true,
        );
        setInputHint("最近一次请求失败");
      }
    } finally {
      if (controllerRef.current === controller) {
        controllerRef.current = null;
        setBusy(false);
        if (sessionRef.current) window.setTimeout(() => textareaRef.current?.focus(), 0);
      }
    }
  }

  function handleMessageKeyDown(event: KeyboardEvent<HTMLTextAreaElement>): void {
    if (
      event.key === "Enter" &&
      !event.shiftKey &&
      !event.nativeEvent.isComposing
    ) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  }

  const loggedIn = session !== null;
  const loginMode = authMode === "login";

  return (
    <>
      <section className="auth-shell" id="authShell" aria-labelledby="authTitle" hidden={loggedIn}>
        <a className="brand auth-brand" href="/" aria-label="CoursePilot 首页">
          <span className="brand-mark" aria-hidden="true">C</span>
          <span>
            <strong>CoursePilot</strong>
            <small>循证学习 Agent</small>
          </span>
        </a>

        <div className="auth-card">
          <p className="eyebrow">YOUR LEARNING SPACE</p>
          <h1 id="authTitle">登录后继续你的学习。</h1>
          <p className="auth-copy">
            每个账号拥有独立的学习画像。CoursePilot 不保存完整对话或你粘贴的代码。
          </p>

          <div className="auth-tabs" role="tablist" aria-label="账号操作">
            <button
              className={`auth-tab${loginMode ? " active" : ""}`}
              id="loginTab"
              type="button"
              role="tab"
              aria-selected={loginMode}
              tabIndex={loginMode ? 0 : -1}
              disabled={authBusy}
              onClick={() => {
                if (authBusyRef.current || logoutBusyRef.current) return;
                authGenerationRef.current += 1;
                setAuthMode("login");
                setAuthError("");
              }}
            >
              登录
            </button>
            <button
              className={`auth-tab${loginMode ? "" : " active"}`}
              id="registerTab"
              type="button"
              role="tab"
              aria-selected={!loginMode}
              tabIndex={loginMode ? -1 : 0}
              disabled={authBusy}
              onClick={() => {
                if (authBusyRef.current || logoutBusyRef.current) return;
                authGenerationRef.current += 1;
                setAuthMode("register");
                setAuthError("");
              }}
            >
              注册
            </button>
          </div>

          <form
            className="auth-form"
            id="loginForm"
            hidden={!loginMode}
            onSubmit={(event) => void submitLogin(event)}
          >
            <label className="field">
              <span>用户名</span>
              <input
                ref={loginUsernameRef}
                id="loginUsername"
                name="username"
                autoComplete="username"
                minLength={3}
                maxLength={32}
                required
              />
            </label>
            <label className="field">
              <span>密码</span>
              <input
                ref={loginPasswordRef}
                id="loginPassword"
                name="password"
                type="password"
                autoComplete="current-password"
                minLength={12}
                maxLength={128}
                required
              />
            </label>
            <button className="button primary auth-submit" type="submit" disabled={authBusy}>
              登录
            </button>
          </form>

          <form
            className="auth-form"
            id="registerForm"
            hidden={loginMode}
            onSubmit={(event) => void submitRegistration(event)}
          >
            <label className="field">
              <span>用户名</span>
              <input
                ref={registerUsernameRef}
                id="registerUsername"
                name="username"
                autoComplete="username"
                minLength={3}
                maxLength={32}
                pattern={"[A-Za-z0-9][A-Za-z0-9._\\-]{2,31}"}
                required
              />
              <small>3–32 位字母、数字、点、下划线或连字符。</small>
            </label>
            <label className="field">
              <span>密码</span>
              <input
                ref={registerPasswordRef}
                id="registerPassword"
                name="password"
                type="password"
                autoComplete="new-password"
                minLength={12}
                maxLength={128}
                required
              />
              <small>至少 12 个字符。</small>
            </label>
            <label className="field">
              <span>确认密码</span>
              <input
                ref={registerPasswordConfirmRef}
                id="registerPasswordConfirm"
                type="password"
                autoComplete="new-password"
                minLength={12}
                maxLength={128}
                required
              />
            </label>
            <button className="button primary auth-submit" type="submit" disabled={authBusy}>
              创建账号
            </button>
          </form>

          <p className="auth-error" id="authError" role="alert">{authError}</p>
        </div>
      </section>

      <div className="page-shell" id="appShell" hidden={!loggedIn}>
        <header className="topbar">
          <a className="brand" href="/" aria-label="CoursePilot 首页">
            <span className="brand-mark" aria-hidden="true">C</span>
            <span>
              <strong>CoursePilot</strong>
              <small>个人 Agent 学习空间</small>
            </span>
          </a>

          <div className="topbar-actions">
            <span className="connection online" id="connectionStatus">
              <i aria-hidden="true" />
              {" 已安全登录"}
            </span>
            <span className="user-chip" id="currentUsername">{session?.user.username ?? ""}</span>
            <button className="button ghost" id="clearButton" type="button" disabled={logoutBusy} onClick={() => clearConversation()}>
              清空对话
            </button>
            <button className="button ghost" id="logoutButton" type="button" disabled={logoutBusy} onClick={() => void logout()}>
              退出登录
            </button>
          </div>
        </header>

        <main className="workspace">
          <section className="intro" id="intro" hidden={messages.length > 0}>
            <p className="eyebrow">PRIVATE LEARNING PROFILE</p>
            <h1>从一次真实对话开始。</h1>
            <p>
              页面通过账号会话调用本机的 <code>/v1/chat/completions</code>；学习画像只属于当前账号，
              并可体验课程导航、已审核 StudyKit 学习、多语言静态代码辅导，以及 Markdown、公式与代码高亮的 SSE 流式输出。
            </p>
            <div className="starter-grid">
              {starterPrompts.map((starter) => (
                <button
                  className="starter"
                  type="button"
                  data-prompt={starter.prompt}
                  key={starter.title}
                  onClick={() => {
                    setDraft(starter.prompt);
                    window.setTimeout(() => textareaRef.current?.focus(), 0);
                  }}
                >
                  <span>{starter.title}</span>
                  <small>{starter.description}</small>
                </button>
              ))}
            </div>
          </section>

          <section
            ref={conversationRef}
            className="conversation"
            id="conversation"
            aria-live="polite"
            aria-label="对话记录"
          >
            {messages.map((message) => (
              <ConversationMessage message={message} key={message.id} />
            ))}
          </section>
        </main>

        <footer className="composer-wrap">
          <form
            className="composer"
            id="chatForm"
            onSubmit={(event) => {
              event.preventDefault();
              void sendMessage(draft);
            }}
          >
            <label className="sr-only" htmlFor="messageInput">输入消息</label>
            <textarea
              ref={textareaRef}
              id="messageInput"
              rows={1}
              maxLength={10_000}
              placeholder="输入消息，Enter 发送，Shift + Enter 换行"
              value={draft}
              disabled={busy || logoutBusy}
              onChange={(event) => setDraft(event.currentTarget.value)}
              onKeyDown={handleMessageKeyDown}
            />
            <div className="composer-footer">
              <label className="stream-toggle">
                <input
                  id="streamToggle"
                  type="checkbox"
                  checked={streamEnabled}
                  disabled={logoutBusy}
                  onChange={(event) => setStreamEnabled(event.currentTarget.checked)}
                />
                <span aria-hidden="true" />
                流式输出
              </label>
              <span className="hint" id="inputHint">{inputHint}</span>
              <button className="send-button" id="sendButton" type="submit" hidden={busy} disabled={logoutBusy}>
                <span>发送</span>
                <svg viewBox="0 0 20 20" aria-hidden="true">
                  <path d="M3 10h13M11 5l5 5-5 5" />
                </svg>
              </button>
              <button
                className="stop-button"
                id="stopButton"
                type="button"
                hidden={!busy}
                onClick={() => controllerRef.current?.abort()}
              >
                停止
              </button>
            </div>
          </form>
          <p className="privacy-note">
            会话凭据保存在 HttpOnly Cookie；完整对话和粘贴的代码仅存在于当前页面内存，
            学习画像按账号写入本机 SQLite，并可随时删除。
          </p>
        </footer>
      </div>
    </>
  );
}
