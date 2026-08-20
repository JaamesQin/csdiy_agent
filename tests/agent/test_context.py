from __future__ import annotations

from app.agent.context import build_turn_context
from app.agent.contracts import CodeTutorMode, SemanticCodeArtifact
from app.agent.understanding import (
    explicit_language_from_text,
    infer_code_tutor_mode,
    validate_model_code,
)
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


def test_generation_request_extracts_mode_and_language_without_code() -> None:
    context = build_turn_context(
        [ChatMessage(role="user", content="给我一段完整的cpp示例代码")]
    )

    assert context.code == ""
    assert context.code_request.mode is CodeTutorMode.GENERATE_EXAMPLE
    assert context.code_request.target_language == "cpp"
    assert context.code_request.language_inferred is False


def test_code_tutor_modes_cover_v1_operations() -> None:
    assert infer_code_tutor_mode("逐行解释这段代码") is CodeTutorMode.EXPLAIN
    assert infer_code_tutor_mode("修好下面的代码") is CodeTutorMode.REPAIR
    assert infer_code_tutor_mode("重构这段代码") is CodeTutorMode.REFACTOR
    assert infer_code_tutor_mode("做一次代码审阅") is CodeTutorMode.REVIEW
    assert infer_code_tutor_mode("为这个函数设计单元测试") is CodeTutorMode.DESIGN_TESTS
    assert infer_code_tutor_mode("看看代码哪里错了") is CodeTutorMode.DIAGNOSE
    assert infer_code_tutor_mode("修复课程目录") is None
    assert infer_code_tutor_mode("重构课程结构") is None
    assert explicit_language_from_text("请生成 Rust 代码") == "rust"
    assert explicit_language_from_text("How do I go about writing example code?") is None
    assert explicit_language_from_text("请用 Go 写一个示例") == "go"


def test_explicit_reference_reuses_recent_assistant_code_only_in_memory() -> None:
    context = build_turn_context(
        [
            ChatMessage(
                role="assistant",
                content="示例：\n```cpp\nint main() { return 0; }\n```",
            ),
            ChatMessage(role="user", content="把上面的例子重构一下"),
        ]
    )

    assert context.code == "int main() { return 0; }"
    assert context.language == "cpp"
    assert context.code_source == "assistant_reference"
    assert context.code_request.mode is CodeTutorMode.REFACTOR


def test_unreferenced_generation_does_not_reuse_old_assistant_code() -> None:
    context = build_turn_context(
        [
            ChatMessage(
                role="assistant",
                content="```cpp\nint main() { return 0; }\n```",
            ),
            ChatMessage(role="user", content="给我一个新的 Rust 示例代码"),
        ]
    )

    assert context.code == ""
    assert context.code_request.target_language == "rust"


def test_generation_reuses_only_recent_verified_language_not_old_code_body() -> None:
    context = build_turn_context(
        [
            ChatMessage(
                role="user",
                content="请分析：```cpp\nint main() { return 0; }\n```",
            ),
            ChatMessage(role="user", content="再给我一个完整示例代码"),
        ]
    )

    assert context.code == ""
    assert context.code_request.mode is CodeTutorMode.GENERATE_EXAMPLE
    assert context.code_request.target_language == "cpp"
    assert context.code_request.language_inferred is True


def test_spec_based_test_design_does_not_attach_unreferenced_old_code() -> None:
    context = build_turn_context(
        [
            ChatMessage(role="user", content="```rust\nfn main() {}\n```"),
            ChatMessage(role="user", content="按这个规格设计单元测试：空输入返回错误"),
        ]
    )

    assert context.code == ""
    assert context.code_request.mode is CodeTutorMode.DESIGN_TESTS
    assert context.code_request.target_language == "rust"
    assert context.code_request.language_inferred is True


def test_explicit_explanation_reference_reuses_recent_user_code() -> None:
    context = build_turn_context(
        [
            ChatMessage(role="user", content="```cpp\nint main() { return 0; }\n```"),
            ChatMessage(role="user", content="解释上面的代码"),
        ]
    )

    assert context.code == "int main() { return 0; }"
    assert context.code_request.mode is CodeTutorMode.EXPLAIN
    assert context.code_request.references_existing_code is True
