from pathlib import Path

from PIL import Image, ImageEnhance


def create_mockup_animation(
    image_path: str | Path,
    output_path: str | Path,
    frames_count: int = 14,
    duration_ms: int = 90,
) -> Path:
    src = Path(image_path)
    dst = Path(output_path)
    dst.parent.mkdir(parents=True, exist_ok=True)

    base = Image.open(src).convert("RGB")
    w, h = base.size
    frames = []

    # Gentle zoom + micro brightness swing for a premium "live mockup" feel.
    for i in range(max(6, frames_count)):
        t = i / max(1, frames_count - 1)
        zoom = 1.0 + 0.05 * (0.5 - abs(t - 0.5)) * 2.0
        zw, zh = int(w * zoom), int(h * zoom)
        resized = base.resize((zw, zh), Image.Resampling.LANCZOS)

        left = (zw - w) // 2
        top = (zh - h) // 2
        frame = resized.crop((left, top, left + w, top + h))

        brightness = 0.98 + 0.06 * (0.5 - abs(t - 0.5)) * 2.0
        frame = ImageEnhance.Brightness(frame).enhance(brightness)
        frames.append(frame)

    frames[0].save(
        dst,
        save_all=True,
        append_images=frames[1:] + list(reversed(frames[1:-1])),
        optimize=True,
        duration=duration_ms,
        loop=0,
    )
    return dst
