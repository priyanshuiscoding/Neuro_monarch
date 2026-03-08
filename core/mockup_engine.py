from pathlib import Path
from statistics import mean
import os
from collections import deque

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps
import numpy as np

# Relative print-safe zones as (x0, y0, x1, y1) ratios of template size.
PRINT_ZONE_RATIOS = {
    ("T-Shirt", "Front"): (0.30, 0.22, 0.70, 0.66),
    ("T-Shirt", "Back"): (0.29, 0.20, 0.71, 0.68),
    # Tuned for provided person-worn hoodie photos.
    # Front: chest to near-kangaroo pocket area.
    ("Hoodie", "Front"): (0.34, 0.27, 0.68, 0.80),
    # Back: upper back to just above hem.
    ("Hoodie", "Back"): (0.24, 0.24, 0.76, 0.82),
    ("Pants", "Front"): (0.32, 0.16, 0.68, 0.86),
    ("Pants", "Back"): (0.32, 0.16, 0.68, 0.86),
    # Scarf should be fully designable with tiny bleed-safe margins.
    ("Scarf", "Full"): (0.03, 0.03, 0.97, 0.97),
    ("Scarf", "Front"): (0.03, 0.03, 0.97, 0.97),
    ("Scarf", "Back"): (0.03, 0.03, 0.97, 0.97),
}


def _base_garment_color(color: str) -> tuple[int, int, int]:
    return (35, 35, 35) if (color or "").strip().lower() == "black" else (245, 245, 245)


def create_flat_garment_template(
    garment_type: str,
    color: str,
    output_path: str | Path,
    print_side: str = "Front",
) -> Path:
    kind = (garment_type or "T-Shirt").strip()
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fabric = _base_garment_color(color)

    if kind == "Scarf":
        w, h = 1024, 1024
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle(
            (70, 100, w - 70, h - 100),
            radius=28,
            fill=(*fabric, 255),
            outline=(120, 120, 120, 255),
            width=3,
        )
        for y in range(140, h - 120, 24):
            alpha = 20 if y % 48 == 0 else 12
            draw.line((88, y, w - 88, y), fill=(255, 255, 255, alpha), width=1)
    elif kind == "Pants":
        w, h = 1024, 1024
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        left = [(360, 120), (470, 120), (500, 880), (390, 920), (315, 910), (295, 220)]
        right = [(554, 120), (664, 120), (730, 220), (709, 910), (634, 920), (523, 880)]
        draw.polygon(left, fill=(*fabric, 255))
        draw.polygon(right, fill=(*fabric, 255))
        draw.rectangle((470, 120, 554, 168), fill=(max(0, fabric[0] - 10), max(0, fabric[1] - 10), max(0, fabric[2] - 10), 255))
        draw.line((315, 220, 360, 120, 664, 120, 730, 220), fill=(125, 125, 125, 210), width=2)
    else:
        # Conservative t-shirt fallback silhouette.
        w, h = 1024, 1024
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        poly = [
            (300, 160),
            (430, 160),
            (460, 120),
            (564, 120),
            (594, 160),
            (724, 160),
            (815, 288),
            (748, 360),
            (700, 320),
            (700, 900),
            (324, 900),
            (324, 320),
            (276, 360),
            (209, 288),
        ]
        draw.polygon(poly, fill=(*fabric, 255))
        draw.arc((430, 110, 594, 235), start=20, end=160, fill=(120, 120, 120, 220), width=4)

    img.save(out)
    return out


def _distance_to_color_image(rgb: Image.Image, br: int, bg: int, bb: int) -> Image.Image:
    # Pillow 11+ may not expose ImageMath.eval in all builds; use NumPy for robust distance.
    arr = np.asarray(rgb, dtype=np.int16)
    dist = (
        np.abs(arr[:, :, 0] - br)
        + np.abs(arr[:, :, 1] - bg)
        + np.abs(arr[:, :, 2] - bb)
    ) // 3
    dist = np.clip(dist, 0, 255).astype(np.uint8)
    return Image.fromarray(dist, mode="L")


def _remove_light_background(img: Image.Image) -> Image.Image:
    rgba = img.convert("RGBA")
    rgb = rgba.convert("RGB")
    hsv = rgb.convert("HSV")
    sat = hsv.split()[1]
    val = hsv.split()[2]

    pixels = rgb.load()
    w, h = rgb.size
    edge_pixels = []
    for x in range(w):
        edge_pixels.append(pixels[x, 0])
        edge_pixels.append(pixels[x, h - 1])
    for y in range(h):
        edge_pixels.append(pixels[0, y])
        edge_pixels.append(pixels[w - 1, y])

    sample_step = max(1, len(edge_pixels) // 400)
    sampled = edge_pixels[::sample_step]
    bg_r = int(mean(p[0] for p in sampled))
    bg_g = int(mean(p[1] for p in sampled))
    bg_b = int(mean(p[2] for p in sampled))

    r, g, b = rgb.split()
    dist_to_bg = _distance_to_color_image(rgb, bg_r, bg_g, bg_b)

    low_sat = Image.eval(sat, lambda p: 255 if p < 52 else 0)
    bright = Image.eval(val, lambda p: 255 if p > 206 else 0)
    near_bg = Image.eval(dist_to_bg, lambda p: 255 if p < 42 else 0)

    bg_like = ImageChops.lighter(near_bg, ImageChops.multiply(low_sat, bright))
    bg_like = bg_like.filter(ImageFilter.GaussianBlur(1.5))

    keep = ImageOps.invert(bg_like)
    alpha = ImageChops.multiply(rgba.split()[3], keep)
    cleaned = Image.merge("RGBA", (r, g, b, alpha))

    alpha = cleaned.split()[3]
    non_transparent = alpha.point(lambda p: 255 if p > 10 else 0).getbbox()
    if non_transparent is None:
        # Fail-safe: never return fully transparent artwork.
        return img.convert("RGBA")

    bbox = alpha.getbbox()
    if bbox:
        cleaned = cleaned.crop(bbox)
    return cleaned


def _remove_flat_background_if_opaque(img: Image.Image) -> Image.Image:
    rgba = img.convert("RGBA")
    alpha = rgba.split()[3]
    opaque_ratio = sum(alpha.histogram()[250:256]) / max(1, rgba.width * rgba.height)
    if opaque_ratio < 0.95:
        return rgba

    rgb = rgba.convert("RGB")
    w, h = rgb.size
    px = rgb.load()
    edge = []
    for x in range(w):
        edge.append(px[x, 0])
        edge.append(px[x, h - 1])
    for y in range(h):
        edge.append(px[0, y])
        edge.append(px[w - 1, y])

    step = max(1, len(edge) // 500)
    sampled = edge[::step]
    bg_r = int(mean(p[0] for p in sampled))
    bg_g = int(mean(p[1] for p in sampled))
    bg_b = int(mean(p[2] for p in sampled))

    r, g, b = rgb.split()
    dist = _distance_to_color_image(rgb, bg_r, bg_g, bg_b)
    hsv = rgb.convert("HSV")
    sat = hsv.split()[1]
    val = hsv.split()[2]

    # Keep colorful regions and dark ink lines; fade edge-like flat background.
    keep_color = sat.point(lambda p: 255 if p > 48 else 0)
    keep_dark = val.point(lambda p: 255 if p < 188 else 0)
    keep_dist = dist.point(lambda p: 255 if p > 22 else 0)
    keep = ImageChops.lighter(keep_dist, ImageChops.lighter(keep_color, keep_dark))
    keep = keep.filter(ImageFilter.GaussianBlur(1.1))
    alpha_new = ImageChops.multiply(alpha, keep)

    cleaned = Image.merge("RGBA", (*rgb.split(), alpha_new))
    bbox = alpha_new.getbbox()
    if bbox:
        cleaned = cleaned.crop(bbox)
    return cleaned


def _extract_ink_like_cutout(img: Image.Image) -> Image.Image:
    # Remove flat/background regions from fully opaque generated art so
    # print edges look free-form instead of square patches.
    rgba = img.convert("RGBA")
    alpha = rgba.split()[3]
    opaque_ratio = sum(alpha.histogram()[250:256]) / max(1, rgba.width * rgba.height)
    if opaque_ratio < 0.9:
        return rgba

    rgb = rgba.convert("RGB")
    w, h = rgb.size
    px = rgb.load()
    corners = [px[0, 0], px[w - 1, 0], px[0, h - 1], px[w - 1, h - 1]]
    bg_r = int(mean(c[0] for c in corners))
    bg_g = int(mean(c[1] for c in corners))
    bg_b = int(mean(c[2] for c in corners))

    r, g, b = rgb.split()
    dist = _distance_to_color_image(rgb, bg_r, bg_g, bg_b)
    gray = rgb.convert("L")
    edge = gray.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.GaussianBlur(0.8))
    sat = rgb.convert("HSV").split()[1]

    keep_dist = dist.point(lambda p: 255 if p > 24 else 0)
    keep_edge = edge.point(lambda p: 255 if p > 20 else 0)
    keep_sat = sat.point(lambda p: 255 if p > 28 else 0)
    keep = ImageChops.lighter(keep_dist, ImageChops.lighter(keep_edge, keep_sat))
    keep = keep.filter(ImageFilter.GaussianBlur(1.2))

    new_alpha = ImageChops.multiply(alpha, keep)
    cutout = Image.merge("RGBA", (*rgb.split(), new_alpha))
    bbox = new_alpha.getbbox()
    if bbox:
        cutout = cutout.crop(bbox)
    return cutout


def _estimate_subject_bbox(garment: Image.Image) -> tuple[int, int, int, int] | None:
    # Detect foreground person/hoodie region from near-uniform background.
    gw, gh = garment.size
    max_dim = 900
    scale = min(1.0, max_dim / max(gw, gh))
    sw, sh = max(1, int(gw * scale)), max(1, int(gh * scale))
    small = garment.resize((sw, sh), Image.Resampling.BILINEAR).convert("RGB")
    arr = np.asarray(small).astype(np.float32)

    border_w = max(2, int(sw * 0.04))
    border_h = max(2, int(sh * 0.04))
    border_pixels = np.concatenate(
        [
            arr[:border_h, :, :].reshape(-1, 3),
            arr[-border_h:, :, :].reshape(-1, 3),
            arr[:, :border_w, :].reshape(-1, 3),
            arr[:, -border_w:, :].reshape(-1, 3),
        ],
        axis=0,
    )
    bg = np.median(border_pixels, axis=0)
    dist = np.sqrt(((arr - bg) ** 2).sum(axis=2))
    threshold = max(14.0, float(np.percentile(dist, 62) * 0.9))
    bg_like = dist < threshold

    visited = np.zeros((sh, sw), dtype=np.uint8)
    q = deque()
    for x in range(sw):
        if bg_like[0, x]:
            q.append((x, 0))
            visited[0, x] = 1
        if bg_like[sh - 1, x]:
            q.append((x, sh - 1))
            visited[sh - 1, x] = 1
    for y in range(sh):
        if bg_like[y, 0] and not visited[y, 0]:
            q.append((0, y))
            visited[y, 0] = 1
        if bg_like[y, sw - 1] and not visited[y, sw - 1]:
            q.append((sw - 1, y))
            visited[y, sw - 1] = 1

    while q:
        x, y = q.popleft()
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < sw and 0 <= ny < sh and not visited[ny, nx] and bg_like[ny, nx]:
                visited[ny, nx] = 1
                q.append((nx, ny))

    fg_mask = visited == 0
    if fg_mask.sum() < (sw * sh * 0.03):
        return None

    ys, xs = np.where(fg_mask)
    x0, x1 = int(xs.min()), int(xs.max())
    y0, y1 = int(ys.min()), int(ys.max())

    # Scale back to original image coordinates.
    gx0 = int(x0 / scale)
    gy0 = int(y0 / scale)
    gx1 = int(x1 / scale)
    gy1 = int(y1 / scale)
    return max(0, gx0), max(0, gy0), min(gw, gx1), min(gh, gy1)


def _estimate_subject_mask(garment: Image.Image) -> Image.Image | None:
    # Build a coarse foreground matte from border-connected background regions.
    gw, gh = garment.size
    max_dim = 900
    scale = min(1.0, max_dim / max(gw, gh))
    sw, sh = max(1, int(gw * scale)), max(1, int(gh * scale))
    small = garment.resize((sw, sh), Image.Resampling.BILINEAR).convert("RGB")
    arr = np.asarray(small).astype(np.float32)

    border_w = max(2, int(sw * 0.04))
    border_h = max(2, int(sh * 0.04))
    border_pixels = np.concatenate(
        [
            arr[:border_h, :, :].reshape(-1, 3),
            arr[-border_h:, :, :].reshape(-1, 3),
            arr[:, :border_w, :].reshape(-1, 3),
            arr[:, -border_w:, :].reshape(-1, 3),
        ],
        axis=0,
    )
    bg = np.median(border_pixels, axis=0)
    dist = np.sqrt(((arr - bg) ** 2).sum(axis=2))
    threshold = max(14.0, float(np.percentile(dist, 62) * 0.9))
    bg_like = dist < threshold

    visited = np.zeros((sh, sw), dtype=np.uint8)
    q = deque()
    for x in range(sw):
        if bg_like[0, x]:
            q.append((x, 0))
            visited[0, x] = 1
        if bg_like[sh - 1, x]:
            q.append((x, sh - 1))
            visited[sh - 1, x] = 1
    for y in range(sh):
        if bg_like[y, 0] and not visited[y, 0]:
            q.append((0, y))
            visited[y, 0] = 1
        if bg_like[y, sw - 1] and not visited[y, sw - 1]:
            q.append((sw - 1, y))
            visited[y, sw - 1] = 1

    while q:
        x, y = q.popleft()
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < sw and 0 <= ny < sh and not visited[ny, nx] and bg_like[ny, nx]:
                visited[ny, nx] = 1
                q.append((nx, ny))

    fg_mask = (visited == 0).astype(np.uint8) * 255
    if fg_mask.sum() < (sw * sh * 0.03 * 255):
        return None

    small_mask = Image.fromarray(fg_mask, mode="L")
    # Fill tiny holes and keep edges soft for natural print blending.
    small_mask = small_mask.filter(ImageFilter.MaxFilter(3))
    mask = small_mask.resize((gw, gh), Image.Resampling.BILINEAR)
    mask = mask.point(lambda p: 255 if p > 24 else 0)
    return mask.filter(ImageFilter.GaussianBlur(1.2))


def _resolve_zone(
    garment_size: tuple[int, int],
    garment_type: str,
    print_side: str,
    garment_img: Image.Image | None = None,
) -> tuple[int, int, int, int]:
    gw, gh = garment_size
    side_key = "Full" if garment_type == "Scarf" else print_side

    auto_zone = os.getenv("AUTO_SUBJECT_ZONE", "true").lower() in {"1", "true", "yes"}
    if garment_type == "Hoodie" and not auto_zone:
        auto_zone = os.getenv("AUTO_HOODIE_ZONE", "true").lower() in {"1", "true", "yes"}
    if auto_zone and garment_img is not None:
        bbox = _estimate_subject_bbox(garment_img)
        if bbox:
            sx0, sy0, sx1, sy1 = bbox
            bw = max(1, sx1 - sx0)
            bh = max(1, sy1 - sy0)
            if garment_type == "Hoodie":
                if print_side == "Front":
                    return (
                        int(sx0 + bw * 0.23),
                        int(sy0 + bh * 0.22),
                        int(sx0 + bw * 0.77),
                        int(sy0 + bh * 0.82),
                    )
                return (
                    int(sx0 + bw * 0.20),
                    int(sy0 + bh * 0.18),
                    int(sx0 + bw * 0.80),
                    int(sy0 + bh * 0.86),
                )
            # T-Shirt placement from detected torso region.
            if print_side == "Front":
                return (
                    int(sx0 + bw * 0.24),
                    int(sy0 + bh * 0.18),
                    int(sx0 + bw * 0.76),
                    int(sy0 + bh * 0.68),
                )
            return (
                int(sx0 + bw * 0.22),
                int(sy0 + bh * 0.15),
                int(sx0 + bw * 0.78),
                int(sy0 + bh * 0.72),
            )

    override_key = f"PRINT_ZONE_{garment_type.upper().replace('-', '_')}_{side_key.upper()}"
    override = os.getenv(override_key)
    if override:
        try:
            rx0, ry0, rx1, ry1 = [float(x.strip()) for x in override.split(",")]
        except Exception:
            rx0, ry0, rx1, ry1 = PRINT_ZONE_RATIOS.get(
                (garment_type, side_key), PRINT_ZONE_RATIOS[("T-Shirt", "Front")]
            )
    else:
        rx0, ry0, rx1, ry1 = PRINT_ZONE_RATIOS.get(
            (garment_type, side_key), PRINT_ZONE_RATIOS[("T-Shirt", "Front")]
        )
    return int(gw * rx0), int(gh * ry0), int(gw * rx1), int(gh * ry1)


def _hoodie_body_mask(size: tuple[int, int], print_side: str) -> Image.Image:
    w, h = size
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)

    if print_side == "Front":
        poly = [
            (int(w * 0.22), int(h * 0.03)),
            (int(w * 0.78), int(h * 0.03)),
            (int(w * 0.90), int(h * 0.22)),
            (int(w * 0.92), int(h * 0.58)),
            (int(w * 0.84), int(h * 0.97)),
            (int(w * 0.16), int(h * 0.97)),
            (int(w * 0.08), int(h * 0.58)),
            (int(w * 0.10), int(h * 0.22)),
        ]
    else:
        poly = [
            (int(w * 0.16), int(h * 0.03)),
            (int(w * 0.84), int(h * 0.03)),
            (int(w * 0.93), int(h * 0.24)),
            (int(w * 0.90), int(h * 0.64)),
            (int(w * 0.80), int(h * 0.98)),
            (int(w * 0.20), int(h * 0.98)),
            (int(w * 0.10), int(h * 0.64)),
            (int(w * 0.07), int(h * 0.24)),
        ]

    draw.polygon(poly, fill=255)
    return mask.filter(ImageFilter.GaussianBlur(max(2, int(min(w, h) * 0.012))))


def _hoodie_torso_clip_mask(size: tuple[int, int], print_side: str) -> Image.Image:
    # Conservative torso-only matte in full-template coordinates.
    w, h = size
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)

    if print_side == "Front":
        poly = [
            (int(w * 0.33), int(h * 0.17)),
            (int(w * 0.67), int(h * 0.17)),
            (int(w * 0.76), int(h * 0.31)),
            (int(w * 0.78), int(h * 0.53)),
            (int(w * 0.72), int(h * 0.87)),
            (int(w * 0.28), int(h * 0.87)),
            (int(w * 0.22), int(h * 0.53)),
            (int(w * 0.24), int(h * 0.31)),
        ]
    else:
        poly = [
            (int(w * 0.30), int(h * 0.15)),
            (int(w * 0.70), int(h * 0.15)),
            (int(w * 0.78), int(h * 0.31)),
            (int(w * 0.79), int(h * 0.57)),
            (int(w * 0.72), int(h * 0.88)),
            (int(w * 0.28), int(h * 0.88)),
            (int(w * 0.21), int(h * 0.57)),
            (int(w * 0.22), int(h * 0.31)),
        ]

    draw.polygon(poly, fill=255)
    return mask.filter(ImageFilter.GaussianBlur(max(2, int(min(w, h) * 0.01))))


def _hoodie_print_area_mask(size: tuple[int, int], print_side: str) -> Image.Image:
    # Strict central print area only; excludes sleeves and side seams.
    w, h = size
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)

    if print_side == "Front":
        x0, y0, x1, y1 = int(w * 0.35), int(h * 0.23), int(w * 0.65), int(h * 0.79)
    else:
        x0, y0, x1, y1 = int(w * 0.34), int(h * 0.20), int(w * 0.66), int(h * 0.82)

    corner = max(8, int(min(w, h) * 0.02))
    draw.rounded_rectangle((x0, y0, x1, y1), radius=corner, fill=255)
    return mask.filter(ImageFilter.GaussianBlur(max(1, int(min(w, h) * 0.004))))


def _texture_print(
    design_rgba: Image.Image,
    garment_crop: Image.Image,
    garment_type: str = "T-Shirt",
    print_side: str = "Front",
) -> Image.Image:
    alpha = design_rgba.split()[3].point(lambda p: int(p * 0.92))
    alpha = alpha.filter(ImageFilter.GaussianBlur(0.8))
    design_rgb = design_rgba.convert("RGB")

    texture = garment_crop.convert("L")
    texture = ImageOps.autocontrast(texture)
    texture = ImageEnhance.Contrast(texture).enhance(1.35)
    texture = texture.point(lambda p: max(86, min(255, int(p * 1.08))))
    texture_rgb = Image.merge("RGB", (texture, texture, texture))

    # Mix multiply with original to keep colors vibrant while preserving fabric texture.
    multiplied = ImageChops.multiply(design_rgb, texture_rgb)
    soft_light = ImageChops.screen(multiplied, design_rgb)
    printed_rgb = Image.blend(soft_light, multiplied, 0.52)

    if garment_type == "Hoodie":
        body_mask = _hoodie_body_mask(design_rgba.size, print_side)
        alpha = ImageChops.multiply(alpha, body_mask)

    return Image.merge("RGBA", (*printed_rgb.split(), alpha))


def export_print_ready_art(
    design_rgba: Image.Image,
    output_path: str | Path,
    garment_type: str = "T-Shirt",
) -> str:
    # 4500x5400 @300 DPI is a common DTG-friendly canvas.
    if garment_type == "Scarf":
        canvas = Image.new("RGBA", (5400, 5400), (0, 0, 0, 0))
        max_w, max_h = 5200, 5200
        y_offset = (canvas.height - max_h) // 2
    elif garment_type == "Pants":
        canvas = Image.new("RGBA", (4500, 5400), (0, 0, 0, 0))
        max_w, max_h = 3000, 4700
        y_offset = 350
    else:
        canvas = Image.new("RGBA", (4500, 5400), (0, 0, 0, 0))
        max_w = 3600 if garment_type == "T-Shirt" else 3400
        max_h = 4200 if garment_type == "T-Shirt" else 4000
        y_offset = 620

    art = ImageOps.contain(design_rgba, (max_w, max_h), method=Image.Resampling.LANCZOS)
    x = (canvas.width - art.width) // 2
    y = y_offset
    canvas.paste(art, (x, y), art)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, dpi=(300, 300))
    return str(output)


def generate_print_ready_from_design(
    design_path: str | Path,
    output_path: str | Path,
    garment_type: str = "T-Shirt",
) -> str:
    design = Image.open(design_path).convert("RGBA")
    cleaned = _remove_light_background(design)
    return export_print_ready_art(cleaned, output_path=output_path, garment_type=garment_type)


def generate_mockup(
    design_path,
    tshirt_path,
    logo_path=None,
    output_path="uploads/final_mockup.png",
    garment_type="T-Shirt",
    print_side="Front",
):
    garment = Image.open(tshirt_path).convert("RGBA")
    hoodie_subject_mask = None
    hoodie_torso_mask = None
    hoodie_print_mask = None
    if garment_type == "Hoodie":
        hoodie_subject_mask = _estimate_subject_mask(garment)
        hoodie_torso_mask = _hoodie_torso_clip_mask(garment.size, print_side)
        hoodie_print_mask = _hoodie_print_area_mask(garment.size, print_side)

    design = Image.open(design_path).convert("RGBA")
    design = _remove_light_background(design)
    design = _remove_flat_background_if_opaque(design)
    design = _extract_ink_like_cutout(design)

    x0, y0, x1, y1 = _resolve_zone(garment.size, garment_type, print_side, garment_img=garment)
    if garment_type == "Hoodie" and hoodie_print_mask is not None:
        pb = hoodie_print_mask.getbbox()
        if pb:
            x0, y0, x1, y1 = pb
    if garment_type == "Hoodie" and hoodie_torso_mask is not None:
        mb = hoodie_torso_mask.getbbox()
        if mb:
            mx0, my0, mx1, my1 = mb
            x0, y0, x1, y1 = max(x0, mx0), max(y0, my0), min(x1, mx1), min(y1, my1)
    if x1 <= x0 or y1 <= y0:
        x0, y0, x1, y1 = _resolve_zone(garment.size, garment_type, print_side, garment_img=garment)
    zone_w, zone_h = x1 - x0, y1 - y0

    # Keep artwork strictly inside the printable area with garment-specific safe margin.
    if garment_type == "Hoodie":
        fill_ratio = float(os.getenv("PRINT_FILL_HOODIE", "0.98"))
        margin_ratio = float(os.getenv("PRINT_MARGIN_HOODIE", "0.01"))
    elif garment_type == "Scarf":
        fill_ratio = float(os.getenv("PRINT_FILL_SCARF", "0.995"))
        margin_ratio = float(os.getenv("PRINT_MARGIN_SCARF", "0.002"))
    elif garment_type == "Pants":
        fill_ratio = float(os.getenv("PRINT_FILL_PANTS", "0.94"))
        margin_ratio = float(os.getenv("PRINT_MARGIN_PANTS", "0.025"))
    else:
        fill_ratio = float(os.getenv("PRINT_FILL_TSHIRT", "0.96"))
        margin_ratio = float(os.getenv("PRINT_MARGIN_TSHIRT", "0.03"))

    target_w = max(1, int(zone_w * fill_ratio))
    target_h = max(1, int(zone_h * fill_ratio))
    fit = ImageOps.contain(design, (target_w, target_h), method=Image.Resampling.LANCZOS)

    margin = max(4, int(min(zone_w, zone_h) * margin_ratio))
    fit = ImageOps.contain(
        fit,
        (max(1, zone_w - 2 * margin), max(1, zone_h - 2 * margin)),
        method=Image.Resampling.LANCZOS,
    )
    fit = fit.filter(ImageFilter.UnsharpMask(radius=1.1, percent=125, threshold=2))

    px = x0 + (zone_w - fit.width) // 2
    py = y0 + (zone_h - fit.height) // 2
    crop = garment.crop((px, py, px + fit.width, py + fit.height))
    printed = _texture_print(fit, crop, garment_type=garment_type, print_side=print_side)

    # Hard-clip hoodie prints to detected garment/body region so art never floats outside.
    if garment_type == "Hoodie" and hoodie_subject_mask is not None:
        clip = hoodie_subject_mask.crop((px, py, px + fit.width, py + fit.height))
        pr, pg, pb, pa = printed.split()
        pa = ImageChops.multiply(pa, clip)
        printed = Image.merge("RGBA", (pr, pg, pb, pa))
    if garment_type == "Hoodie" and hoodie_torso_mask is not None:
        clip = hoodie_torso_mask.crop((px, py, px + fit.width, py + fit.height))
        pr, pg, pb, pa = printed.split()
        pa = ImageChops.multiply(pa, clip)
        printed = Image.merge("RGBA", (pr, pg, pb, pa))
    if garment_type == "Hoodie" and hoodie_print_mask is not None:
        clip = hoodie_print_mask.crop((px, py, px + fit.width, py + fit.height))
        pr, pg, pb, pa = printed.split()
        pa = ImageChops.multiply(pa, clip)
        printed = Image.merge("RGBA", (pr, pg, pb, pa))

    garment.paste(printed, (px, py), printed)

    if logo_path and Path(logo_path).exists() and print_side == "Front" and garment_type in {"T-Shirt", "Hoodie"}:
        logo = Image.open(logo_path).convert("RGBA")
        logo = ImageOps.contain(logo, (58, 34), method=Image.Resampling.LANCZOS)
        garment.paste(logo, (120, 96), logo)

    # Keep preview output in fixed 1:1 ratio for consistent UI/product cards.
    square_size = int(os.getenv("MOCKUP_SQUARE_SIZE", "1024"))
    if garment.width != garment.height:
        side = max(garment.width, garment.height)
        square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        x = (side - garment.width) // 2
        y = (side - garment.height) // 2
        square.paste(garment, (x, y), garment)
        garment = square

    if square_size > 0 and garment.width != square_size:
        garment = garment.resize((square_size, square_size), Image.Resampling.LANCZOS)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    garment.save(output)
    return str(output)
