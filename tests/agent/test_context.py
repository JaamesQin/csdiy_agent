from __future__ import annotations

from app.agent.context import build_turn_context
from app.protocol.schemas import ChatMessage


def test_code_context_skips_labeled_error_output_fence() -> None:
    context = build_turn_context(
        [
            ChatMessage(
                role="user",
                content=(
                    "请分析：\n```cpp\nint main( { return 0; }\n```\n"
                    "```console\nmain.cpp:1:11: error: expected ')'\n```"
                ),
            )
        ]
    )

    assert context.language == "cpp"
    assert context.code == "int main( { return 0; }"
    assert "expected ')'" in (context.error_text or "")


def test_error_context_recognizes_rust_and_latex_formats() -> None:
    rust = build_turn_context(
        [
            ChatMessage(
                role="user",
                content="```rust\nfn main() {}\n```\nerror[E0308]: mismatched types",
            )
        ]
    )
    latex = build_turn_context(
        [
            ChatMessage(
                role="user",
                content="```latex\n\\badcommand\n```\n! LaTeX Error: bad command",
            )
        ]
    )

    assert rust.error_text == "error[E0308]: mismatched types"
    assert latex.error_text == "! LaTeX Error: bad command"
