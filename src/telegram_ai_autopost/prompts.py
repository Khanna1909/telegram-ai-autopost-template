from __future__ import annotations

from .models import ContentExample, VisualMode


def build_visual_prompt(example: ContentExample, signature: str) -> str:
    base = example.visual_prompt.strip()
    signature_rule = (
        f'Include one small, elegant artist signature in the bottom-right safe '
        f'area reading exactly "{signature}". Use refined luxury handwritten '
        "lettering, subtle and tasteful, naturally integrated into the artwork. "
        "Keep it fully visible and away from faces, hands and important objects."
    )

    if example.mode in {VisualMode.CLEAN, VisualMode.SIGNATURE}:
        text_rule = (
            "Do not include any other text, captions, logos or watermarks."
        )
    else:
        if not example.card_text.strip():
            raise ValueError("educational_card requires card_text")
        text_rule = (
            "Render the following prepared text exactly as written, without "
            "adding facts, labels, logos or watermarks:\n"
            f"{example.card_text.strip()}"
        )
    return "\n\n".join((base, text_rule, signature_rule))


def build_post_text(example: ContentExample, footer: str = "") -> str:
    parts = [example.title.strip(), example.post_text.strip(), example.visual_prompt.strip()]
    if footer.strip():
        parts.append(footer.strip())
    return "\n\n".join(part for part in parts if part)

