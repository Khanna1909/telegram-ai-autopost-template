from __future__ import annotations

from pathlib import Path

from PIL import Image, UnidentifiedImageError


class InvalidMediaError(ValueError):
    pass


def validate_image(
    path: str | Path, *, min_width: int = 512, min_height: int = 512
) -> tuple[int, int]:
    image_path = Path(path)
    if not image_path.exists() or image_path.stat().st_size == 0:
        raise InvalidMediaError("Image file is missing or empty")
    if image_path.stat().st_size < 1024:
        raise InvalidMediaError("Image file is critically small")
    try:
        with Image.open(image_path) as image:
            image.verify()
        with Image.open(image_path) as image:
            width, height = image.size
    except (UnidentifiedImageError, OSError) as error:
        raise InvalidMediaError("Image file is damaged or unsupported") from error
    if width < min_width or height < min_height:
        raise InvalidMediaError(
            f"Image dimensions {width}x{height} are below {min_width}x{min_height}"
        )
    return width, height

