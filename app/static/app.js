function getOrCreateAnonymousUserId() {
  const stored = localStorage.getItem("coursepilot_anonymous_user");
  if (stored) return stored;
  const suffix = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`;
  const userId = `local-${suffix}`;
  localStorage.setItem("coursepilot_anonymous_user", userId);
  return userId;
}

const state = {
  apiBase: sessionStorage.getItem("coursepilot_api_base") || "",
  apiKey: sessionStorage.getItem("coursepilot_api_key") || "",
  userId: getOrCreateAnonymousUserId(),
  messages: [],
  controller: null,
  busy: false,
};

const elements = {
  chatForm: document.querySelector("#chatForm"),
  messageInput: document.querySelector("#messageInput"),
  sendButton: document.querySelector("#sendButton"),
  stopButton: document.querySelector("#stopButton"),
  streamToggle: document.querySelector("#streamToggle"),
  conversation: document.querySelector("#conversation"),
  intro: document.querySelector("#intro"),
  clearButton: document.querySelector("#clearButton"),
  settingsButton: document.querySelector("#settingsButton"),
  settingsDialog: document.querySelector("#settingsDialog"),
  settingsForm: document.querySelector("#settingsForm"),
  apiBaseInput: document.querySelector("#apiBaseInput"),
  apiKeyInput: document.querySelector("#apiKeyInput"),
  settingsError: document.querySelector("#settingsError"),
  connectionStatus: document.querySelector("#connectionStatus"),
  inputHint: document.querySelector("#inputHint"),
};

function apiUrl(path) {
  const base = state.apiBase.replace(/\/+$/, "");
  return `${base}${path}`;
}

function setConnection(status, text) {
  elements.connectionStatus.className = `connection ${status}`;
  elements.connectionStatus.lastChild.textContent = text;
  elements.inputHint.textContent = text;
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

function showError(message) {
  const text = createMessage("assistant", "", "error");
  text.textContent = `请求失败：${message}`;
}

async function validateConnection(apiKey, apiBase) {
  const base = apiBase.replace(/\/+$/, "");
  const response = await fetch(`${base}/v1/models`, {
    headers: { Authorization: `Bearer ${apiKey}` },
  });
  if (!response.ok) {
    let message = `HTTP ${response.status}`;
    try {
      const body = await response.json();
      message = body?.error?.message || message;
    } catch {
      // The status code is enough when the response is not JSON.
    }
    throw new Error(message);
  }
}

async function saveSettings(event) {
  event.preventDefault();
  const submitter = event.submitter;
  if (submitter?.value === "cancel") {
    elements.settingsDialog.close();
    return;
  }

  const apiKey = elements.apiKeyInput.value.trim();
  const apiBase = elements.apiBaseInput.value.trim();
  if (!apiKey) {
    elements.settingsError.textContent = "请输入 Bearer 密钥。";
    return;
  }

  elements.settingsError.textContent = "正在验证连接…";
  try {
    await validateConnection(apiKey, apiBase);
    state.apiKey = apiKey;
    state.apiBase = apiBase;
    sessionStorage.setItem("coursepilot_api_key", apiKey);
    sessionStorage.setItem("coursepilot_api_base", apiBase);
    setConnection("online", "本地服务已连接");
    elements.settingsDialog.close();
    elements.messageInput.focus();
  } catch (error) {
    elements.settingsError.textContent = `验证失败：${error.message}`;
    setConnection("error", "连接验证失败");
  }
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

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    const blocks = buffer.split(/\r?\n\r?\n/);
    buffer = blocks.pop() || "";

    for (const block of blocks) {
      const event = parseSseBlock(block);
      if (!event) continue;
      if (event === "[DONE]") return;
      if (event.error) throw new Error(event.error.message || "流式响应中断");

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
  if (!message || state.busy) return;
  if (!state.apiKey) {
    openSettings();
    return;
  }

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
    const response = await fetch(apiUrl("/v1/chat/completions"), {
      method: "POST",
      headers: {
        Authorization: `Bearer ${state.apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: "coursepilot-probe",
        messages: state.messages,
        stream,
        user: state.userId,
      }),
      signal: state.controller.signal,
    });

    if (!response.ok) {
      let message = `HTTP ${response.status}`;
      try {
        const body = await response.json();
        message = body?.error?.message || message;
      } catch {
        // Preserve the status-based message for non-JSON errors.
      }
      throw new Error(message);
    }

    if (stream) {
      await readStream(response, output);
    } else {
      const body = await response.json();
      output.textContent = body.choices?.[0]?.message?.content || "";
    }

    if (!output.textContent) {
      throw new Error("服务返回了空回复。");
    }
    state.messages.push({ role: "assistant", content: output.textContent });
    setConnection("online", "本地服务已连接");
  } catch (error) {
    if (error.name === "AbortError") {
      output.textContent ||= "生成已停止。";
    } else {
      output.textContent = `请求失败：${error.message}`;
      output.closest(".message").classList.add("error");
      setConnection("error", "最近一次请求失败");
    }
  } finally {
    output.classList.remove("streaming");
    state.controller = null;
    setBusy(false);
    elements.messageInput.focus();
  }
}

function clearConversation() {
  if (state.busy) state.controller?.abort();
  state.messages = [];
  elements.conversation.replaceChildren();
  elements.intro.hidden = false;
  elements.messageInput.focus();
}

function openSettings() {
  elements.apiBaseInput.value = state.apiBase;
  elements.apiKeyInput.value = state.apiKey;
  elements.settingsError.textContent = "";
  elements.settingsDialog.showModal();
  window.setTimeout(() => elements.apiKeyInput.focus(), 0);
}

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

elements.stopButton.addEventListener("click", () => state.controller?.abort());
elements.clearButton.addEventListener("click", clearConversation);
elements.settingsButton.addEventListener("click", openSettings);
elements.settingsForm.addEventListener("submit", saveSettings);

document.querySelectorAll(".starter").forEach((button) => {
  button.addEventListener("click", () => {
    elements.messageInput.value = button.dataset.prompt || "";
    resizeInput();
    elements.messageInput.focus();
  });
});

if (state.apiKey) {
  validateConnection(state.apiKey, state.apiBase)
    .then(() => setConnection("online", "本地服务已连接"))
    .catch(() => setConnection("error", "请重新验证密钥"));
} else {
  window.setTimeout(openSettings, 250);
}
