from app.services.image_ai import detect_image_content_type


def test_detect_image_content_type() -> None:
    assert detect_image_content_type(b"\xff\xd8\xff\xe0") == "image/jpeg"
    assert detect_image_content_type(b"\x89PNG\r\n\x1a\n") == "image/png"
    assert detect_image_content_type(b"RIFF\x00\x00\x00\x00WEBP") == "image/webp"
    assert detect_image_content_type(b"not-an-image") is None
