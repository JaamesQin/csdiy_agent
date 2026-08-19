from __future__ import annotations

from app.agent.context import build_turn_context
from app.agent.contracts import SemanticCodeArtifact
from app.agent.understanding import validate_model_code
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


def test_context_extracts_inline_quoted_cpp_without_closing_quote() -> None:
    context = build_turn_context(
        [
            ChatMessage(
                role="user",
                content=(
                    "这段代码有什么问题：“include<stdio.h> "
                    "int main(){int a,b; cin>>a>>b; cout<<a+b; return 0;}"
                ),
            )
        ]
    )

    assert context.code.startswith("include<stdio.h>")
    assert context.language == "cpp"
    assert context.language_inferred is True
    assert context.code_source == "inline"


def test_context_extracts_chat_flattened_fence() -> None:
    context = build_turn_context(
        [
            ChatMessage(
                role="user",
                content="请分析 ```cpp   include<stdio.h> int main(){return 0;}   ```",
            )
        ]
    )

    assert context.language == "cpp"
    assert context.code == "include<stdio.h> int main(){return 0;}"
    assert context.code_source == "fence"


def test_model_code_must_be_grounded_in_a_user_message() -> None:
    messages = [ChatMessage(role="user", content="帮我看代码：int main(){return 0;}")]
    valid = validate_model_code(
        messages,
        SemanticCodeArtifact(
            content="int main(){return 0;}",
            language="cpp",
            source_message_index=0,
        ),
    )
    invented = validate_model_code(
        messages,
        SemanticCodeArtifact(
            content="int main(){dangerous_call();}",
            language="cpp",
            source_message_index=0,
        ),
    )

    assert valid.content == "int main(){return 0;}"
    assert valid.language == "cpp"
    assert invented.content == ""
