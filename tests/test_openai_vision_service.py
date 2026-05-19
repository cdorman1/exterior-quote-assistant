from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

import src.openai_vision_service as vision_service
from src.openai_vision_service import (
    DetectedMeasurement,
    VisionExtractionResponse,
    image_to_base64_data_url,
    parse_measurement_response,
)


def _make_image(path: Path, suffix: str) -> Path:
    image_path = path / f"sample.{suffix}"
    image = Image.new("RGB", (10, 10), color="white")
    image.save(image_path)
    return image_path


def test_image_to_base64_data_url_png(tmp_path):
    image_path = _make_image(tmp_path, "png")
    data_url = image_to_base64_data_url(str(image_path))
    assert data_url.startswith("data:image/png;base64,")


def test_image_to_base64_data_url_jpg(tmp_path):
    image_path = _make_image(tmp_path, "jpg")
    data_url = image_to_base64_data_url(str(image_path))
    assert data_url.startswith("data:image/jpeg;base64,")


def test_image_to_base64_data_url_webp(tmp_path):
    image_path = _make_image(tmp_path, "webp")
    data_url = image_to_base64_data_url(str(image_path))
    assert data_url.startswith("data:image/webp;base64,")


def test_image_to_base64_data_url_rejects_unsupported_extension(tmp_path):
    image_path = tmp_path / "sample.gif"
    image_path.write_bytes(b"GIF89a")
    with pytest.raises(ValueError):
        image_to_base64_data_url(str(image_path))


def test_parse_measurement_response_returns_dict():
    response = SimpleNamespace(
        output_parsed=VisionExtractionResponse(
            trade="roofing",
            detected_measurements=[
                DetectedMeasurement(
                    label="Roof",
                    measurement_type="roof_area",
                    shape="rectangle",
                    width_ft=10,
                    height_ft=12,
                    base_ft=None,
                    top_width_ft=None,
                    bottom_width_ft=None,
                    length_ft=None,
                    quantity=None,
                    confidence=0.9,
                    source_text="10 x 12",
                )
            ],
            openings=[],
            calculation_recommendations=["Measure roof area"],
            warnings=[],
            confidence=0.9,
        )
    )

    parsed = parse_measurement_response(response)
    assert parsed["trade"] == "roofing"
    assert parsed["detected_measurements"][0]["measurement_type"] == "roof_area"


def test_extract_measurements_from_image_uses_fake_openai_client(tmp_path, monkeypatch):
    image_path = _make_image(tmp_path, "png")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_VISION_MODEL", "gpt-5.5")

    captured = {}

    class FakeResponses:
        def parse(self, *, model, input, text_format):
            captured["model"] = model
            captured["input"] = input
            captured["text_format"] = text_format
            return SimpleNamespace(
                output_parsed=VisionExtractionResponse(
                    trade="siding",
                    detected_measurements=[],
                    openings=[],
                    calculation_recommendations=[],
                    warnings=[],
                    confidence=0.8,
                )
            )

    class FakeOpenAI:
        def __init__(self, api_key):
            captured["api_key"] = api_key
            self.responses = FakeResponses()

    monkeypatch.setattr(vision_service, "OpenAI", FakeOpenAI)

    result = vision_service.extract_measurements_from_image(str(image_path), trade_hint="siding")

    assert captured["api_key"] == "test-key"
    assert captured["model"] == "gpt-5.5"
    assert result["trade"] == "siding"
    assert any(item["type"] == "input_image" for item in captured["input"][0]["content"])
