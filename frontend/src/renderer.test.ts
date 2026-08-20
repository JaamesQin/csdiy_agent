import { describe, expect, it, vi } from "vitest";

import {
  renderAssistantContent,
  renderMarkdownToHtml,
  renderPlainText,
} from "./renderer";

describe("assistant Markdown rendering", () => {
  it("renders headings, lists, tables, links, and fenced code", () => {
    const target = document.createElement("div");
    renderAssistantContent(
      target,
      [
        "# 学习路径",
        "",
        "- 先读讲义",
        "- 再做练习",
        "",
        "| 阶段 | 状态 |",
        "| --- | --- |",
        "| Lecture 2 | ready |",
        "",
        "[课程主页](https://example.com/course)",
        "",
        "```python",
        "def train():",
        "    return True",
        "```",
      ].join("\n"),
    );

    expect(target.querySelector("h1")?.textContent).toBe("学习路径");
    expect(target.querySelectorAll("li")).toHaveLength(2);
    expect(target.querySelector("table")?.textContent).toContain("Lecture 2");
    expect(target.querySelector(".table-scroll > table")).not.toBeNull();
    expect(target.querySelector("a")?.getAttribute("rel")).toBe("noopener noreferrer");
    expect(target.querySelector("a")?.getAttribute("target")).toBe("_blank");
    expect(target.querySelector("code")?.classList.contains("hljs")).toBe(true);
    expect(target.querySelector(".copy-code-button")?.textContent).toBe("复制");
  });

  it("renders inline and display LaTeX with KaTeX", () => {
    const target = document.createElement("div");
    renderAssistantContent(
      target,
      String.raw`梯度更新为 $\theta_{k+1}=\theta_k-\eta\nabla J(\theta_k)$。

$$\nabla_\theta J=0$$`,
    );

    expect(target.querySelectorAll(".katex math").length).toBeGreaterThanOrEqual(2);
    expect(target.querySelector("math[display='block']")).not.toBeNull();
  });

  it("caps pathological model-supplied TeX dimensions", () => {
    const target = document.createElement("div");
    renderAssistantContent(target, String.raw`$\kern1000000000em x$`);

    expect(target.querySelector("mspace")?.getAttribute("width")).toBe("20em");
  });

  it("does not create executable model-supplied HTML or unsafe links", () => {
    const target = document.createElement("div");
    renderAssistantContent(
      target,
      [
        '<img src=x onerror="window.__coursepilotXss = true">',
        "",
        "[script](javascript:alert(1))",
        "",
        "[embedded](data:image/png;base64,AAAA)",
      ].join("\n"),
    );

    expect(target.querySelector("img")).toBeNull();
    expect(target.querySelector("a")).toBeNull();
    expect((window as Window & { __coursepilotXss?: boolean }).__coursepilotXss).not.toBe(
      true,
    );
  });

  it("forbids Markdown images and inline styles", () => {
    const target = document.createElement("div");
    renderAssistantContent(
      target,
      "![tracking pixel](https://attacker.example/pixel.png)\n\n$\\color{red}{x}$",
    );

    expect(target.querySelector("img")).toBeNull();
    expect(target.querySelector("[style]")).toBeNull();
  });

  it("falls back to text when rendering fails", () => {
    const target = document.createElement("div");
    const innerHtml = vi.spyOn(target, "innerHTML", "set").mockImplementation(() => {
      throw new Error("synthetic DOM failure");
    });

    renderAssistantContent(target, "**still readable**");

    expect(target.textContent).toBe("**still readable**");
    expect(target.classList.contains("plain-text")).toBe(true);
    innerHtml.mockRestore();
  });

  it("keeps user and error content as literal text", () => {
    const target = document.createElement("div");
    renderPlainText(target, '<img src=x onerror="alert(1)"> **literal**');

    expect(target.querySelector("img")).toBeNull();
    expect(target.textContent).toContain("<img");
    expect(target.textContent).toContain("**literal**");
  });

  it("returns sanitized HTML as a standalone helper", () => {
    const html = renderMarkdownToHtml("## Safe\n\n<script>alert(1)</script>");
    expect(html).toContain("<h2>Safe</h2>");
    expect(html).not.toContain("<script>");
  });
});
