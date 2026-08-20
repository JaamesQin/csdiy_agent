import DOMPurify, { type Config } from "dompurify";
import hljs from "highlight.js/lib/core";
import bash from "highlight.js/lib/languages/bash";
import c from "highlight.js/lib/languages/c";
import cpp from "highlight.js/lib/languages/cpp";
import css from "highlight.js/lib/languages/css";
import go from "highlight.js/lib/languages/go";
import java from "highlight.js/lib/languages/java";
import javascript from "highlight.js/lib/languages/javascript";
import json from "highlight.js/lib/languages/json";
import latex from "highlight.js/lib/languages/latex";
import python from "highlight.js/lib/languages/python";
import rust from "highlight.js/lib/languages/rust";
import sql from "highlight.js/lib/languages/sql";
import typescript from "highlight.js/lib/languages/typescript";
import xml from "highlight.js/lib/languages/xml";
import yaml from "highlight.js/lib/languages/yaml";
import { katex } from "@mdit/plugin-katex";
import MarkdownIt, {
  type MarkdownIt as MarkdownItInstance,
  type RendererRule,
} from "markdown-it";

const languages = {
  bash,
  c,
  cpp,
  css,
  go,
  java,
  javascript,
  json,
  latex,
  python,
  rust,
  sql,
  typescript,
  xml,
  yaml,
};

for (const [name, language] of Object.entries(languages)) {
  hljs.registerLanguage(name, language);
}

hljs.registerAliases(["console", "shell", "sh", "zsh"], { languageName: "bash" });
hljs.registerAliases(["c++", "cc", "h", "hpp"], { languageName: "cpp" });
hljs.registerAliases(["html", "mathml", "svg"], { languageName: "xml" });
hljs.registerAliases(["js", "jsx"], { languageName: "javascript" });
hljs.registerAliases(["py"], { languageName: "python" });
hljs.registerAliases(["tex"], { languageName: "latex" });
hljs.registerAliases(["ts", "tsx"], { languageName: "typescript" });
hljs.registerAliases(["yml"], { languageName: "yaml" });

function escapeHtml(source: string): string {
  return source.replace(/[&<>\"]/g, (character) => {
    const entities: Record<string, string> = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '\"': "&quot;",
    };
    return entities[character] ?? character;
  });
}

const markdown: MarkdownItInstance = new MarkdownIt({
  breaks: false,
  html: false,
  linkify: true,
  typographer: false,
  highlight(code, languageName) {
    const normalized = languageName.trim().toLowerCase();
    if (!normalized || !hljs.getLanguage(normalized)) {
      return `<pre class="code-block"><code>${escapeHtml(code)}</code></pre>`;
    }

    const highlighted = hljs.highlight(code, {
      language: normalized,
      ignoreIllegals: true,
    }).value;
    const safeName = escapeHtml(normalized);
    return `<pre class="code-block"><code class="hljs language-${safeName}">${highlighted}</code></pre>`;
  },
}).use(katex, {
  delimiters: "dollars",
  output: "mathml",
  maxSize: 20,
  strict: "ignore",
  throwOnError: false,
  trust: false,
});

markdown.validateLink = (url: string): boolean => {
  try {
    const parsed = new URL(url, "https://coursepilot.invalid/");
    return ["http:", "https:", "mailto:"].includes(parsed.protocol);
  } catch {
    return false;
  }
};

const defaultLinkOpen: RendererRule =
  markdown.renderer.rules.link_open ??
  ((tokens, index, options, _environment, renderer) =>
    renderer.renderToken(tokens, index, options));

markdown.renderer.rules.link_open = (tokens, index, options, environment, renderer) => {
  tokens[index]?.attrSet("target", "_blank");
  tokens[index]?.attrSet("rel", "noopener noreferrer");
  return defaultLinkOpen(tokens, index, options, environment, renderer);
};

markdown.renderer.rules.table_open = () => '<div class="table-scroll"><table>';
markdown.renderer.rules.table_close = () => "</table></div>";

const sanitizeOptions: Config = {
  ADD_ATTR: ["target"],
  FORBID_TAGS: [
    "button",
    "embed",
    "form",
    "iframe",
    "img",
    "input",
    "object",
    "option",
    "script",
    "select",
    "style",
    "textarea",
  ],
  FORBID_ATTR: ["srcset", "style"],
  SANITIZE_NAMED_PROPS: true,
  USE_PROFILES: { html: true, mathMl: true },
};

export function renderMarkdownToHtml(source: string): string {
  const rendered = markdown.render(source);
  return DOMPurify.sanitize(rendered, sanitizeOptions);
}

export function renderAssistantContent(target: HTMLElement, source: string): void {
  try {
    target.classList.remove("plain-text");
    target.innerHTML = renderMarkdownToHtml(source);
    decorateCodeBlocks(target);
  } catch {
    target.classList.add("plain-text");
    target.replaceChildren(document.createTextNode(source));
  }
}

export function renderPlainText(target: HTMLElement, source: string): void {
  target.replaceChildren(document.createTextNode(source));
}

function decorateCodeBlocks(target: HTMLElement): void {
  for (const code of target.querySelectorAll<HTMLElement>("pre > code")) {
    const pre = code.parentElement;
    if (!(pre instanceof HTMLPreElement) || pre.querySelector(":scope > .code-toolbar")) {
      continue;
    }

    const languageClass = [...code.classList].find((name) => name.startsWith("language-"));
    const language = languageClass?.slice("language-".length) || "text";
    const toolbar = document.createElement("span");
    toolbar.className = "code-toolbar";

    const label = document.createElement("span");
    label.className = "code-language";
    label.textContent = language;

    const copyButton = document.createElement("button");
    copyButton.className = "copy-code-button";
    copyButton.type = "button";
    copyButton.textContent = "复制";
    copyButton.setAttribute("aria-label", `复制 ${language} 代码`);
    copyButton.addEventListener("click", () => {
      void copyCode(copyButton, code.textContent ?? "");
    });

    toolbar.append(label, copyButton);
    pre.prepend(toolbar);
  }
}

async function copyCode(button: HTMLButtonElement, code: string): Promise<void> {
  const original = button.textContent || "复制";
  try {
    await navigator.clipboard.writeText(code);
    button.textContent = "已复制";
  } catch {
    button.textContent = "复制失败";
  }
  window.setTimeout(() => {
    button.textContent = original;
  }, 1_600);
}
