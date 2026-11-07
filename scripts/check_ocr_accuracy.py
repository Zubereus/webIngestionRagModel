from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess


PARAGRAPHS = [
    ("Thời hạn giải quyết là 08 Ngày làm việc.", ["Thời hạn giải quyết", "08 Ngày làm việc"]),
    ("Người nộp hồ sơ sử dụng mẫu TK01.", ["mẫu TK01"]),
    ("Lệ phí cấp mới là 50.000 đồng; cấp lại là 100.000 đồng.", ["50.000 đồng", "100.000 đồng"]),
    ("Phí cấp đổi là 200.000 đồng.", ["200.000 đồng"]),
    (
        "Thời hạn giải quyết 08 Ngày làm việc; biểu mẫu mẫu TK01; lệ phí 50.000 đồng.",
        ["08 Ngày làm việc", "mẫu TK01", "50.000 đồng"],
    ),
]


def edit_distance(left: str, right: str) -> int:
    previous = list(range(len(right) + 1))
    for left_index, left_char in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_char in enumerate(right, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[right_index] + 1,
                    previous[right_index - 1] + (left_char != right_char),
                )
            )
        previous = current
    return previous[-1]


def wrap_text(text: str, draw, font, max_width: int) -> list[str]:
    lines = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if current and draw.textbbox((0, 0), candidate, font=font)[2] > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def find_font() -> Path | None:
    configured = os.getenv("WEBRAG_OCR_TEST_FONT")
    candidates = [
        Path(configured) if configured else None,
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path(r"C:\Windows\Fonts\calibri.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
    ]
    return next((path for path in candidates if path and path.is_file()), None)


def render_fixture(dpi: int, font_path: Path):
    from PIL import Image, ImageDraw, ImageFont

    width = round(8.27 * dpi)
    height = round(11.69 * dpi)
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    font_size = round(dpi * 0.12)
    font = ImageFont.truetype(font_path, font_size)
    y = round(dpi * 0.6)
    x = round(dpi * 0.55)
    line_gap = max(4, font_size // 3)
    paragraph_gap = font_size

    for paragraph, _ in PARAGRAPHS:
        lines = wrap_text(paragraph, draw, font, width - 2 * x)
        draw.multiline_text(
            (x, y),
            "\n".join(lines),
            fill="black",
            font=font,
            spacing=line_gap,
        )
        y += len(lines) * (font_size + line_gap) + paragraph_gap
    return image


def main() -> int:
    tesseract = shutil.which("tesseract")
    if not tesseract:
        print("SKIP: Tesseract binary is not installed.")
        return 0

    languages_result = subprocess.run(
        [tesseract, "--list-langs"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    languages = set(languages_result.stdout.splitlines()[1:])
    missing_languages = {"vie", "eng"} - languages
    if languages_result.returncode or missing_languages:
        missing = ", ".join(sorted(missing_languages)) or "Tesseract language data"
        print(f"SKIP: required Tesseract language data is unavailable: {missing}.")
        return 0

    font_path = find_font()
    if font_path is None:
        print(
            "SKIP: no Vietnamese-capable test font found; set WEBRAG_OCR_TEST_FONT."
        )
        return 0

    import pytesseract

    pytesseract.pytesseract.tesseract_cmd = tesseract
    expected = " ".join(paragraph for paragraph, _ in PARAGRAPHS)
    expected = " ".join(expected.split())
    fact_strings = list(dict.fromkeys(fact for _, facts in PARAGRAPHS for fact in facts))

    for dpi in (150, 300):
        image = render_fixture(dpi, font_path)
        try:
            recognized = pytesseract.image_to_string(image, lang="vie+eng")
        finally:
            image.close()
        recognized = " ".join(recognized.split())
        errors = edit_distance(expected, recognized)
        cer = errors / max(len(expected), 1)
        failures = [fact for fact in fact_strings if fact not in recognized]
        survived = len(fact_strings) - len(failures)
        print(
            f"{dpi} DPI: CER={cer:.2%}; exact fact strings "
            f"{survived}/{len(fact_strings)} survived."
        )
        print("Failures: " + (", ".join(failures) if failures else "none"))

    print("Synthetic rendered images only; this does not establish real-world OCR quality.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
