sessionStorage.removeItem("coursepilot_api_key");
sessionStorage.removeItem("coursepilot_api_base");
localStorage.removeItem("coursepilot_anonymous_user");

const state = {
  user: null,
  csrfToken: "",
  messages: [],
  coursepilotContext: null,
  controller: null,
  busy: false,
};

const elements = {
  authShell: document.querySelector("#authShell"),
  appShell: document.querySelector("#appShell"),
  loginTab: document.querySelector("#loginTab"),
  registerTab: document.querySelector("#registerTab"),
  loginForm: document.querySelector("#loginForm"),
  registerForm: document.querySelector("#registerForm"),
  authError: document.querySelector("#authError"),
  currentUsername: document.querySelector("#currentUsername"),
  logoutButton: document.querySelector("#logoutButton"),
  chatForm: document.querySelector("#chatForm"),
  messageInput: document.querySelector("#messageInput"),
  sendButton: document.querySelector("#sendButton"),
  stopButton: document.querySelector("#stopButton"),
  streamToggle: document.querySelector("#streamToggle"),
  conversation: document.querySelector("#conversation"),
  intro: document.querySelector("#intro"),
  clearButton: document.querySelector("#clearButton"),
  connectionStatus: document.querySelector("#connectionStatus"),
  inputHint: document.querySelector("#inputHint"),
};

async function errorMessage(response) {
  try {
    const body = await response.json();
    return body?.error?.message || `HTTP ${response.status}`;
  } catch {
    return `HTTP ${response.status}`;
  }
}

function setAuthMode(mode) {
  const login = mode === "login";
  elements.loginForm.hidden = !login;
  elements.registerForm.hidden = login;
  elements.loginTab.classList.toggle("active", login);
  elements.registerTab.classList.toggle("active", !login);
  elements.loginTab.setAttribute("aria-selected", String(login));
  elements.registerTab.setAttribute("aria-selected", String(!login));
  elements.authError.textContent = "";
}

function showAuth(message = "") {
  state.user = null;
  state.csrfToken = "";
  clearConversation(false);
  elements.appShell.hidden = true;
  elements.authShell.hidden = false;
  elements.authError.textContent = message;
  window.setTimeout(() => document.querySelector("#loginUsername").focus(), 0);
}

function showApp(session) {
  state.user = session.user;
  state.csrfToken = session.csrf_token;
  elements.currentUsername.textContent = session.user.username;
  elements.authShell.hidden = true;
  elements.appShell.hidden = false;
  elements.connectionStatus.className = "connection online";
  elements.connectionStatus.lastChild.textContent = " 已安全登录";
  document.title = "CoursePilot · 我的学习空间";
  window.setTimeout(() => elements.messageInput.focus(), 0);
}

async function authenticate(path, username, password) {
  const response = await fetch(path, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!response.ok) throw new Error(await errorMessage(response));
  return response.json();
}

async function restoreSession() {
  try {
    const response = await fetch("/auth/me", {
      credentials: "same-origin",
      cache: "no-store",
    });
    if (!response.ok) {
      showAuth();
      return;
    }
    showApp(await response.json());
  } catch {
    showAuth("无法连接本地服务，请稍后重试。");
  }
}

async function submitLogin(event) {
  event.preventDefault();
  elements.authError.textContent = "正在登录…";
  try {
    const session = await authenticate(
      "/auth/login",
      document.querySelector("#loginUsername").value,
      document.querySelector("#loginPassword").value,
    );
    elements.loginForm.reset();
    showApp(session);
  } catch (error) {
    elements.authError.textContent = error.message;
  }
}

async function submitRegistration(event) {
  event.preventDefault();
  const password = document.querySelector("#registerPassword").value;
  const confirmation = document.querySelector("#registerPasswordConfirm").value;
  if (password !== confirmation) {
    elements.authError.textContent = "两次输入的密码不一致。";
    return;
  }
  elements.authError.textContent = "正在创建账号…";
  try {
    const session = await authenticate(
      "/auth/register",
      document.querySelector("#registerUsername").value,
      password,
    );
    elements.registerForm.reset();
    showApp(session);
  } catch (error) {
    elements.authError.textContent = error.message;
  }
}

async function logout() {
  if (state.busy) state.controller?.abort();
  try {
    const response = await fetch("/auth/logout", {
      method: "POST",
      credentials: "same-origin",
      headers: { "X-CSRF-Token": state.csrfToken },
    });
    if (!response.ok && response.status !== 401) {
      throw new Error(await errorMessage(response));
    }
    showAuth();
  } catch (error) {
    elements.inputHint.textContent = `退出失败：${error.message}`;
  }
}

function setBusy(busy) {
  state.busy = busy;
  elements.messageInput.disabled = busy;
  elements.sendButton.hidden = busy;
  elements.stopButton.hidden = !busy;
}

function resizeInput() {
  elements.messageInput.style.height = "auto";
  elements.messageInput.style.height = `${Math.min(elements.messageInput.scrollHeight, 180)}px`;
}

function createMessage(role, content = "", extraClass = "") {
  elements.intro.hidden = true;
  const article = document.createElement("article");
  article.className = `message ${role} ${extraClass}`.trim();
  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.textContent = role === "user" ? "你" : "C";
  const body = document.createElement("div");
  body.className = "message-content";
  const meta = document.createElement("p");
  meta.className = "message-meta";
  meta.textContent = role === "user" ? "你" : "CoursePilot";
  const text = document.createElement("p");
  text.className = "message-text";
  text.textContent = content;
  body.append(meta, text);
  article.append(avatar, body);
  elements.conversation.append(article);
  article.scrollIntoView({ behavior: "smooth", block: "end" });
  return text;
}

function parseSseBlock(block) {
  const data = block
    .split("\n")
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trimStart())
    .join("\n");
  if (!data) return null;
  if (data === "[DONE]") return "[DONE]";
  return JSON.parse(data);
}

async function readStream(response, output) {
  if (!response.body) throw new Error("浏览器未收到可读取的响应流。");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let nextContext;
  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    const blocks = buffer.split(/\r?\n\r?\n/);
    buffer = blocks.pop() || "";
    for (const block of blocks) {
      const event = parseSseBlock(block);
      if (!event) continue;
      if (event === "[DONE]") return nextContext;
      if (event.error) throw new Error(event.error.message || "流式响应中断");
      if (typeof event.coursepilot_context === "string") {
        nextContext = event.coursepilot_context;
      }
      const delta = event.choices?.[0]?.delta;
      if (typeof delta?.content === "string") {
        output.textContent += delta.content;
        output.scrollIntoView({ behavior: "smooth", block: "end" });
      }
    }
    if (done) break;
  }
  throw new Error("响应流未以 [DONE] 正常结束。");
}

async function sendMessage(rawMessage) {
  const message = rawMessage.trim();
  if (!message || state.busy || !state.user) return;
  state.messages.push({ role: "user", content: message });
  createMessage("user", message);
  elements.messageInput.value = "";
  resizeInput();
  const output = createMessage("assistant");
  output.classList.add("streaming");
  setBusy(true);
  state.controller = new AbortController();
  try {
    const stream = elements.streamToggle.checked;
    const response = await fetch("/v1/chat/completions", {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": state.csrfToken,
      },
      body: JSON.stringify({
        model: "coursepilot-probe",
        messages: state.messages,
        stream,
        coursepilot_context: state.coursepilotContext || undefined,
      }),
      signal: state.controller.signal,
    });
    if (response.status === 401) {
      showAuth("登录已过期，请重新登录。");
      return;
    }
    if (!response.ok) throw new Error(await errorMessage(response));
    if (stream) {
      const nextContext = await readStream(response, output);
      if (typeof nextContext === "string") {
        state.coursepilotContext = nextContext;
      }
    } else {
      const body = await response.json();
      output.textContent = body.choices?.[0]?.message?.content || "";
      if (typeof body.coursepilot_context === "string") {
        state.coursepilotContext = body.coursepilot_context;
      }
    }
    if (!output.textContent) throw new Error("服务返回了空回复。");
    state.messages.push({ role: "assistant", content: output.textContent });
    elements.inputHint.textContent = "画像按账号隔离";
  } catch (error) {
    state.coursepilotContext = null;
    if (error.name === "AbortError") {
      output.textContent ||= "生成已停止。";
    } else {
      output.textContent = `请求失败：${error.message}`;
      output.closest(".message").classList.add("error");
      elements.inputHint.textContent = "最近一次请求失败";
    }
  } finally {
    output.classList.remove("streaming");
    state.controller = null;
    setBusy(false);
    if (state.user) elements.messageInput.focus();
  }
}

function clearConversation(focus = true) {
  if (state.busy) state.controller?.abort();
  state.messages = [];
  state.coursepilotContext = null;
  elements.conversation.replaceChildren();
  elements.intro.hidden = false;
  if (focus && state.user) elements.messageInput.focus();
}

elements.loginTab.addEventListener("click", () => setAuthMode("login"));
elements.registerTab.addEventListener("click", () => setAuthMode("register"));
elements.loginForm.addEventListener("submit", submitLogin);
elements.registerForm.addEventListener("submit", submitRegistration);
elements.logoutButton.addEventListener("click", logout);
elements.clearButton.addEventListener("click", () => clearConversation());
elements.stopButton.addEventListener("click", () => state.controller?.abort());
elements.chatForm.addEventListener("submit", (event) => {
  event.preventDefault();
  sendMessage(elements.messageInput.value);
});
elements.messageInput.addEventListener("input", resizeInput);
elements.messageInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    elements.chatForm.requestSubmit();
  }
});
document.querySelectorAll(".starter").forEach((button) => {
  button.addEventListener("click", () => {
    elements.messageInput.value = button.dataset.prompt || "";
    resizeInput();
    elements.messageInput.focus();
  });
});

restoreSession();
