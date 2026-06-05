from __future__ import annotations

from benchmark.v12_on_visrag import (
    DEFAULT_BACKEND,
    GENERATOR_BACKENDS,
    build_minicpm_messages,
    build_qwen2vl_messages,
    default_model_for_backend,
)


class DummyImage:
    pass


def test_default_backend_is_qwen2vl_bnb4_for_teammate_alignment() -> None:
    # docs/VisRAG Multi Page Compression.pptx slide 10 baseline uses Qwen2-VL-7B,
    # so the workspace default backend must produce comparable numbers.
    # bitsandbytes 4-bit is used instead of AWQ because AutoAWQ's triton kernel
    # is incompatible with torch>=2.4.
    assert DEFAULT_BACKEND == "qwen2vl7b_bnb4"
    assert default_model_for_backend("qwen2vl7b") == "Qwen/Qwen2-VL-7B-Instruct"
    # bnb4 uses the base instruct weights, quantised on load.
    assert default_model_for_backend("qwen2vl7b_bnb4") == "Qwen/Qwen2-VL-7B-Instruct"


def test_paper_aligned_backends_remain_available() -> None:
    # MiniCPM-V 2.6 and GPT-4o stay as opt-in for paper-alignment runs.
    assert "minicpmv26" in GENERATOR_BACKENDS
    assert "gpt4o" in GENERATOR_BACKENDS
    assert default_model_for_backend("minicpmv26") == "openbmb/MiniCPM-V-2_6"
    assert default_model_for_backend("gpt4o") == "gpt-4o"


def test_minicpm_messages_use_same_content_contract_for_images_and_text() -> None:
    img1 = DummyImage()
    img2 = DummyImage()

    msg = build_minicpm_messages("Question?", [img1, img2])

    assert msg == [{"role": "user", "content": [img1, img2, "Question?"]}]


def test_minicpm_messages_allow_text_only_generation() -> None:
    msg = build_minicpm_messages("Question?", [])

    assert msg == [{"role": "user", "content": "Question?"}]


def test_qwen2vl_messages_use_openai_style_multipart() -> None:
    img1 = DummyImage()
    img2 = DummyImage()

    msg = build_qwen2vl_messages("Question?", [img1, img2])

    assert msg == [{
        "role": "user",
        "content": [
            {"type": "image", "image": img1},
            {"type": "image", "image": img2},
            {"type": "text", "text": "Question?"},
        ],
    }]


def test_qwen2vl_messages_allow_text_only_generation() -> None:
    msg = build_qwen2vl_messages("Question?", [])

    assert msg == [{"role": "user", "content": [{"type": "text", "text": "Question?"}]}]
