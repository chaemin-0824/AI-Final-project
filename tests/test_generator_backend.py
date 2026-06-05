from __future__ import annotations

from benchmark.v12_on_visrag import build_minicpm_messages, default_model_for_backend


class DummyImage:
    pass


def test_default_generator_model_is_minicpmv26() -> None:
    assert default_model_for_backend("minicpmv26") == "openbmb/MiniCPM-V-2_6"


def test_minicpm_messages_use_same_content_contract_for_images_and_text() -> None:
    img1 = DummyImage()
    img2 = DummyImage()

    msg = build_minicpm_messages("Question?", [img1, img2])

    assert msg == [{"role": "user", "content": [img1, img2, "Question?"]}]


def test_minicpm_messages_allow_text_only_generation() -> None:
    msg = build_minicpm_messages("Question?", [])

    assert msg == [{"role": "user", "content": "Question?"}]
