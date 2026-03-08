from datetime import datetime
import os
import json
import re
from pathlib import Path

from flask import Flask, jsonify, render_template, request, url_for
from dotenv import load_dotenv
from PIL import Image, ImageOps
from werkzeug.utils import secure_filename
from werkzeug.exceptions import HTTPException

from core.design_suggestor import suggest_design_elements
from core.image_generation import generate_image_from_prompt
from core.mockup_engine import create_flat_garment_template, generate_mockup, generate_print_ready_from_design
from core.prompt_builder import build_structured_prompts
from core.pricing_engine import calculate_price
from core.prompt_engine import canonicalize_user_prompt, improve_prompt
from core.demo_engine import create_mockup_animation

BASE_DIR = Path(__file__).resolve().parent
GENERATED_DIR = BASE_DIR / "static" / "generated"
DATA_DIR = BASE_DIR / "data"
HISTORY_FILE = DATA_DIR / "history.json"
TSHIRT_PATH = BASE_DIR / "assets" / "tshirts" / "white.png"
TSHIRT_FRONT_PATH = BASE_DIR / "assets" / "tshirts" / "white_front.png"
TSHIRT_BACK_PATH = BASE_DIR / "assets" / "tshirts" / "white_back.png"
TSHIRT_BACK_JPG_PATH = BASE_DIR / "assets" / "tshirts" / "tshirt_back.jpg"
TSHIRT_BACK_JPEG_PATH = BASE_DIR / "assets" / "tshirts" / "tshirt_back.jpeg"
HOODIE_PATH = BASE_DIR / "assets" / "hoodies" / "white.png"
HOODIE_FRONT_PATH = BASE_DIR / "assets" / "hoodies" / "white_front.png"
HOODIE_BACK_PATH = BASE_DIR / "assets" / "hoodies" / "white_back.png"
HOODIE_FRONT_JPG_PATH = BASE_DIR / "assets" / "hoodies" / "white_front.jpg"
HOODIE_FRONT_JPEG_PATH = BASE_DIR / "assets" / "hoodies" / "white_front.jpeg"
HOODIE_BACK_JPG_PATH = BASE_DIR / "assets" / "hoodies" / "white_back.jpg"
HOODIE_BACK_JPEG_PATH = BASE_DIR / "assets" / "hoodies" / "white_back.jpeg"
HOODIE_JPG_PATH = BASE_DIR / "assets" / "hoodies" / "white.jpg"
HOODIE_JPEG_PATH = BASE_DIR / "assets" / "hoodies" / "white.jpeg"
HOODIE_ALT_DIR = BASE_DIR / "assets" / "hoodie"
TSHIRT_DIR = BASE_DIR / "assets" / "tshirts"
HOODIE_DIR = BASE_DIR / "assets" / "hoodies"
PANTS_DIR = BASE_DIR / "assets" / "pants"
SCARF_DIR = BASE_DIR / "assets" / "scarves"
LOGO_PATH = BASE_DIR / "assets" / "branding" / "back_neck_logo.png"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

GENERATED_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)
if not HISTORY_FILE.exists():
    HISTORY_FILE.write_text("[]", encoding="utf-8")
load_dotenv()

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
PROTOTYPE_DEMO_MODE = os.getenv("PROTOTYPE_DEMO_MODE", "false").lower() in {"1", "true", "yes"}
IMAGE_RETRIES = int(os.getenv("IMAGE_RETRIES", "2"))
IS_RENDER = (
    os.getenv("RENDER", "").lower() in {"1", "true", "yes"}
    or bool(os.getenv("RENDER_SERVICE_ID"))
)
ENABLE_ANIMATION = os.getenv("ENABLE_ANIMATION", "false" if IS_RENDER else "true").lower() in {
    "1",
    "true",
    "yes",
}
ENABLE_PRINT_READY = os.getenv("ENABLE_PRINT_READY", "false" if IS_RENDER else "true").lower() in {
    "1",
    "true",
    "yes",
}
AUTO_INTENT_FROM_PROMPT = os.getenv("AUTO_INTENT_FROM_PROMPT", "true").lower() in {"1", "true", "yes"}
AUTO_AI_MOCKUP_FROM_PROMPT = os.getenv("AUTO_AI_MOCKUP_FROM_PROMPT", "true").lower() in {"1", "true", "yes"}
VERBOSE_ASSISTANT_MESSAGE = os.getenv("VERBOSE_ASSISTANT_MESSAGE", "false").lower() in {"1", "true", "yes"}
AI_ONLY_MODE = os.getenv("AI_ONLY_MODE", "true").lower() in {"1", "true", "yes"}
ALLOW_PRINT_READY_WITH_AI_MOCKUP = os.getenv("ALLOW_PRINT_READY_WITH_AI_MOCKUP", "false").lower() in {
    "1",
    "true",
    "yes",
}
MATCH_PREVIEW_IMAGES_IN_AI_MODE = os.getenv("MATCH_PREVIEW_IMAGES_IN_AI_MODE", "true").lower() in {
    "1",
    "true",
    "yes",
}
SCARF_RENDER_STYLE = os.getenv("SCARF_RENDER_STYLE", "mannequin").strip().lower()
APPAREL_RENDER_STYLE = os.getenv("APPAREL_RENDER_STYLE", "flat").strip().lower()


def _is_allowed(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _variant_files(folder: Path, stem: str) -> list[Path]:
    return [folder / f"{stem}.{ext}" for ext in ("png", "jpg", "jpeg", "webp")]


def _is_api_request_path(path: str) -> bool:
    return path.startswith("/chat") or path.startswith("/history")


def _infer_request_from_prompt(prompt: str) -> dict[str, str | bool]:
    p = (prompt or "").lower()
    out: dict[str, str | bool] = {
        "garment_type": "",
        "print_side": "",
        "color": "",
        "size": "",
        "print_style": "",
        "tshirt_type": "",
        "audience": "",
        "explicit_garment": False,
    }

    garment_patterns = [
        (r"\bhoodie\b|\bsweatshirt\b", "Hoodie"),
        (r"\bt-?shirt\b|\btee\b", "T-Shirt"),
        (r"\bscarf\b", "Scarf"),
        (r"\bpants\b|\btrouser\b|\bjogger\b", "Pants"),
    ]
    for pattern, garment in garment_patterns:
        if re.search(pattern, p):
            out["garment_type"] = garment
            out["explicit_garment"] = True
            break

    if re.search(r"\bback\b|\brear\b", p):
        out["print_side"] = "Back"
    elif re.search(r"\bfront\b|\bchest\b", p):
        out["print_side"] = "Front"
    elif re.search(r"\bfull\b|\ball over\b|\bedge to edge\b", p):
        out["print_side"] = "Full"

    if re.search(r"\bblack\b", p):
        out["color"] = "Black"
    elif re.search(r"\bwhite\b", p):
        out["color"] = "White"

    if re.search(r"\bxxl\b", p):
        out["size"] = "XXL"
    elif re.search(r"\bxl\b", p):
        out["size"] = "XL"
    elif re.search(r"\bl\b", p):
        out["size"] = "L"
    elif re.search(r"\bm\b", p):
        out["size"] = "M"
    elif re.search(r"\bs\b", p):
        out["size"] = "S"

    if re.search(r"\btypography\b|\btext only\b|\bquote\b", p):
        out["print_style"] = "Typography"
    elif re.search(r"\bart\b|\bartwork\b|\billustration\b", p):
        out["print_style"] = "Artwork"

    if re.search(r"\boversized\b", p):
        out["tshirt_type"] = "Oversized"
    elif re.search(r"\bv[- ]?neck\b", p):
        out["tshirt_type"] = "V Neck"
    elif re.search(r"\bcrew\b|\bcrew neck\b|\bregular\b", p):
        out["tshirt_type"] = "Crew Neck"

    if re.search(r"\bfemale\b|\bwomen\b|\bgirls?\b", p):
        out["audience"] = "Female"
    elif re.search(r"\bbusiness\b|\bcorporate\b", p):
        out["audience"] = "Business"
    elif re.search(r"\bgeneral\b|\bunisex\b", p):
        out["audience"] = "General"
    elif re.search(r"\bmale\b|\bmen\b|\bboys?\b", p):
        out["audience"] = "Male"

    return out


def _build_ai_mockup_prompt(
    *,
    prompt: str,
    garment_type: str,
    tshirt_type: str,
    print_side: str,
    color: str,
    print_style: str,
    audience: str,
) -> str:
    if garment_type == "Scarf":
        if SCARF_RENDER_STYLE == "flat":
            return (
                f"Premium product photo of a single {color.lower()} scarf only, flat-lay isolated product view. "
                f"Design concept printed on scarf: {prompt}. "
                "Placement rule: full-coverage scarf print across the entire printable surface with tiny edge-safe margins. "
                "Requirements: only one scarf visible, no human, no model, no mannequin, no neck, no face, no body, "
                "clean studio background, sharp textile detail, consistent catalog framing, no watermark."
            )
        return (
            f"Premium ecommerce product photo of a single {color.lower()} scarf draped on a neutral mannequin torso stand. "
            f"Design concept printed on scarf: {prompt}. "
            "Placement rule: full-coverage scarf print across the visible scarf surface with natural folds preserved. "
            "Requirements: scarf must look like real apparel product photography, mannequin torso only, "
            "no human model, no face, no hands, no arms, no extra garments, clean studio background, "
            "sharp textile detail, consistent centered framing, no watermark."
        )

    side_text = "front view" if print_side == "Front" else ("back view" if print_side == "Back" else "full product view")
    placement_text = (
        "print centered on chest area, occupying ~42% of garment width with clean margins"
        if print_side == "Front"
        else "print centered on back panel, occupying ~45% of garment width with clean margins"
    )
    if garment_type == "Scarf":
        placement_text = "design covers the full scarf printable area with tiny bleed-safe margins"
    if garment_type == "Pants":
        placement_text = "design centered vertically on the upper leg panel with seam-safe spacing"

    if APPAREL_RENDER_STYLE == "hanger":
        return (
            f"Simple ecommerce product photo of one {color.lower()} {garment_type.lower()} on a hanger, {side_text}. "
            f"Fit: {tshirt_type.lower()}, style: {print_style.lower()}. "
            f"Design printed on garment: {prompt}. "
            f"Placement rule: {placement_text}. "
            "Strict content rule: print only requested design elements; do not invent extra graphics or text. "
            "Requirements: plain solid studio background, no person, no model, no face, no hands, "
            "single garment only, centered framing, crisp print details, no watermark."
        )

    # Default: flat-lay style for stable, clean product presentation.
    return (
        f"Simple ecommerce flat-lay product photo of one {color.lower()} {garment_type.lower()}, {side_text}. "
        f"Fit: {tshirt_type.lower()}, style: {print_style.lower()}. "
        f"Design printed on garment: {prompt}. "
        f"Placement rule: {placement_text}. "
        "Strict content rule: print only requested design elements; do not invent extra graphics or text. "
        "Requirements: plain solid light-gray or white background, no person, no model body, no face, "
        "no hands, no extra props, single garment only, centered framing, crisp print details, no watermark."
    )


def _resolve_template(garment_type: str, print_side: str, color: str = "White") -> Path:
    color_key = (color or "White").strip().lower()
    if color_key not in {"white", "black"}:
        color_key = "white"
    side_key = "full" if garment_type == "Scarf" else print_side.lower()
    allow_cross_color_fallback = os.getenv("ALLOW_TEMPLATE_COLOR_FALLBACK", "false").lower() in {
        "1",
        "true",
        "yes",
    }

    def _first_existing(paths: list[Path]) -> Path | None:
        for path in paths:
            if path.exists():
                return path
        return None

    if garment_type == "Scarf":
        candidates = _variant_files(SCARF_DIR, color_key) + _variant_files(SCARF_DIR, "default")
    elif garment_type == "Pants":
        candidates = (
            _variant_files(PANTS_DIR, f"{color_key}_{side_key}")
            + _variant_files(PANTS_DIR, color_key)
            + _variant_files(PANTS_DIR, side_key)
            + _variant_files(PANTS_DIR, "default")
        )
    elif garment_type == "Hoodie" and print_side == "Front":
        candidates: list[Path] = []
        for folder in (HOODIE_DIR, HOODIE_ALT_DIR):
            candidates.extend(_variant_files(folder, f"{color_key}_front"))
            candidates.extend(_variant_files(folder, color_key))
        # Legacy white-only templates are used only for explicit white color.
        if color_key == "white":
            candidates.extend(
                [
                    HOODIE_FRONT_PATH,
                    HOODIE_FRONT_JPG_PATH,
                    HOODIE_FRONT_JPEG_PATH,
                    HOODIE_PATH,
                    HOODIE_JPG_PATH,
                    HOODIE_JPEG_PATH,
                ]
            )
    elif garment_type == "Hoodie" and print_side == "Back":
        candidates = []
        for folder in (HOODIE_DIR, HOODIE_ALT_DIR):
            candidates.extend(_variant_files(folder, f"{color_key}_back"))
            candidates.extend(_variant_files(folder, color_key))
        if color_key == "white":
            candidates.extend(
                [
                    HOODIE_BACK_PATH,
                    HOODIE_BACK_JPG_PATH,
                    HOODIE_BACK_JPEG_PATH,
                    HOODIE_PATH,
                    HOODIE_JPG_PATH,
                    HOODIE_JPEG_PATH,
                ]
            )
    elif garment_type == "T-Shirt" and print_side == "Back":
        candidates = (
            _variant_files(TSHIRT_DIR, f"{color_key}_back")
            + ([TSHIRT_BACK_PATH, TSHIRT_BACK_JPG_PATH, TSHIRT_BACK_JPEG_PATH] if color_key == "white" else [])
            + _variant_files(TSHIRT_DIR, color_key)
            + ([TSHIRT_PATH] if color_key == "white" else [])
        )
    else:
        candidates = (
            _variant_files(TSHIRT_DIR, f"{color_key}_front")
            + _variant_files(TSHIRT_DIR, color_key)
            + ([TSHIRT_FRONT_PATH, TSHIRT_PATH] if color_key == "white" else [])
        )

    found = _first_existing(candidates)
    if found is not None:
        return found

    if allow_cross_color_fallback:
        fallback_color = "black" if color_key == "white" else "white"
        fallback_candidates = []
        if garment_type == "Hoodie":
            for folder in (HOODIE_DIR, HOODIE_ALT_DIR):
                stem = f"{fallback_color}_{print_side.lower()}"
                fallback_candidates.extend(_variant_files(folder, stem))
                fallback_candidates.extend(_variant_files(folder, fallback_color))
        else:
            stem = f"{fallback_color}_{print_side.lower()}"
            fallback_candidates.extend(_variant_files(TSHIRT_DIR, stem))
            fallback_candidates.extend(_variant_files(TSHIRT_DIR, fallback_color))

        found = _first_existing(fallback_candidates)
        if found is not None:
            return found

    # Graceful fallback: if exact color is missing, use same garment/side in any available color.
    # This avoids hard failures in prototype setups with incomplete asset packs.
    any_color_candidates: list[Path] = []
    side_key = print_side.lower()
    if garment_type == "Hoodie":
        for folder in (HOODIE_DIR, HOODIE_ALT_DIR):
            any_color_candidates.extend(_variant_files(folder, f"white_{side_key}"))
            any_color_candidates.extend(_variant_files(folder, f"black_{side_key}"))
            any_color_candidates.extend(_variant_files(folder, "white"))
            any_color_candidates.extend(_variant_files(folder, "black"))
    elif garment_type == "T-Shirt":
        any_color_candidates.extend(_variant_files(TSHIRT_DIR, f"white_{side_key}"))
        any_color_candidates.extend(_variant_files(TSHIRT_DIR, f"black_{side_key}"))
        any_color_candidates.extend(_variant_files(TSHIRT_DIR, "white"))
        any_color_candidates.extend(_variant_files(TSHIRT_DIR, "black"))
    elif garment_type in {"Pants", "Scarf"}:
        # handled below with generated fallback
        any_color_candidates = []

    found = _first_existing(any_color_candidates)
    if found is not None:
        return found

    if garment_type in {"Pants", "Scarf"}:
        generated_template = GENERATED_DIR / f"template_{garment_type.lower()}_{color_key}.png"
        return create_flat_garment_template(
            garment_type=garment_type,
            color=color,
            print_side=print_side,
            output_path=generated_template,
        )

    # Last-resort fallback for missing hoodie/t-shirt assets.
    generated_template = GENERATED_DIR / f"template_{garment_type.lower()}_{color_key}_{print_side.lower()}.png"
    return create_flat_garment_template(
        garment_type=garment_type,
        color=color,
        print_side=print_side,
        output_path=generated_template,
    )


def _apply_reference_style(generated_path: Path, reference_path: Path, output_path: Path) -> Path:
    generated = Image.open(generated_path).convert("RGBA")
    reference = Image.open(reference_path).convert("RGB")

    # Quantize generated art to a palette derived from the reference image to keep style influence
    # without replacing the requested concept.
    ref_palette = reference.resize((256, 256), Image.Resampling.BILINEAR).convert("P", palette=Image.ADAPTIVE, colors=64)
    generated_rgb = generated.convert("RGB")
    palette_mapped = generated_rgb.quantize(palette=ref_palette, dither=Image.Dither.NONE).convert("RGB")
    styled_rgb = Image.blend(generated_rgb, palette_mapped, 0.35)
    alpha = generated.split()[3]
    styled = Image.merge("RGBA", (*styled_rgb.split(), alpha))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    styled.save(output_path)
    return output_path


def _compose_scarf_showcase(mannequin_scarf_path: Path, flat_scarf_path: Path, output_path: Path) -> Path:
    # Simple side-by-side catalog board:
    # left = scarf on mannequin torso, right = full flat scarf view.
    mannequin = Image.open(mannequin_scarf_path).convert("RGBA")
    flat = Image.open(flat_scarf_path).convert("RGBA")

    panel_w, panel_h = 820, 960
    man_fit = ImageOps.contain(mannequin, (panel_w - 40, panel_h - 40), method=Image.Resampling.LANCZOS)
    flat_fit = ImageOps.contain(flat, (panel_w - 40, panel_h - 40), method=Image.Resampling.LANCZOS)

    board_w, board_h = panel_w * 2 + 60, 1040
    board = Image.new("RGBA", (board_w, board_h), (255, 255, 255, 255))

    left_panel_x = 20
    right_panel_x = left_panel_x + panel_w + 20
    panel_y = 40

    # subtle neutral panel boundary; keep overall look plain.
    panel_bg = Image.new("RGBA", (panel_w, panel_h), (248, 248, 248, 255))
    board.paste(panel_bg, (left_panel_x, panel_y), panel_bg)
    board.paste(panel_bg, (right_panel_x, panel_y), panel_bg)

    board.paste(
        man_fit,
        (left_panel_x + (panel_w - man_fit.width) // 2, panel_y + (panel_h - man_fit.height) // 2),
        man_fit,
    )
    board.paste(
        flat_fit,
        (right_panel_x + (panel_w - flat_fit.width) // 2, panel_y + (panel_h - flat_fit.height) // 2),
        flat_fit,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    board.convert("RGB").save(output_path)
    return output_path


def _generate_design_with_fallbacks(
    *,
    prompt: str,
    improved_prompt: str,
    user_prompt: str,
    output_path: Path,
    retries: int,
    negative_prompt: str | None,
) -> tuple[Path, str]:
    attempts = [
        ("structured+enhanced", prompt),
        ("enhanced-only", improved_prompt),
        (
            "simplified-fallback",
            (
                f"Apparel print artwork: {user_prompt}. "
                "Isolated design only, transparent background, high contrast, crisp edges, centered composition."
            ),
        ),
    ]
    last_error = "Unknown image generation failure"
    for mode, active_prompt in attempts:
        if not active_prompt or not active_prompt.strip():
            continue
        try:
            generate_image_from_prompt(
                prompt=active_prompt,
                output_path=output_path,
                retries=max(1, retries),
                negative_prompt=negative_prompt,
            )
            return output_path, mode
        except Exception as exc:
            last_error = str(exc)
            continue
    raise RuntimeError(last_error)


def _load_history() -> list[dict]:
    try:
        raw = HISTORY_FILE.read_text(encoding="utf-8")
        data = json.loads(raw)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def _append_history(entry: dict) -> None:
    history = _load_history()
    history.insert(0, entry)
    # Keep recent history bounded for prototype performance.
    history = history[:200]
    HISTORY_FILE.write_text(json.dumps(history, ensure_ascii=True, indent=2), encoding="utf-8")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True, "service": "neuromonarch"}), 200


@app.route("/history", methods=["GET"])
def history():
    return jsonify({"items": _load_history()})


@app.route("/chat", methods=["POST"])
def chat():
    prompt = (request.form.get("message") or "").strip()
    normalized_prompt = canonicalize_user_prompt(prompt)
    material = request.form.get("material", "Cotton")
    tshirt_type = request.form.get("tshirt_type", "Crew Neck")
    garment_type = request.form.get("garment_type", "T-Shirt")
    print_side = request.form.get("print_side", "Front")
    color = request.form.get("color", "White")
    size = request.form.get("size", "M")
    print_style = request.form.get("print_style", "Artwork")
    audience = request.form.get("audience", "Male")
    inferred = _infer_request_from_prompt(normalized_prompt) if AUTO_INTENT_FROM_PROMPT else {}

    if inferred:
        garment_type = inferred.get("garment_type") or garment_type
        print_side = inferred.get("print_side") or print_side
        color = inferred.get("color") or color
        size = inferred.get("size") or size
        print_style = inferred.get("print_style") or print_style
        tshirt_type = inferred.get("tshirt_type") or tshirt_type
        audience = inferred.get("audience") or audience

    if not prompt:
        return jsonify({"error": "Please enter a design prompt."}), 400

    if material not in {"Cotton", "Polyester", "Blend"}:
        return jsonify({"error": "Invalid material selected."}), 400

    if tshirt_type not in {"Crew Neck", "V Neck", "Oversized"}:
        return jsonify({"error": "Invalid t-shirt type selected."}), 400

    if garment_type not in {"T-Shirt", "Hoodie", "Pants", "Scarf"}:
        return jsonify({"error": "Invalid garment type selected."}), 400

    if print_side not in {"Front", "Back", "Full"}:
        return jsonify({"error": "Invalid print side selected."}), 400

    if color not in {"White", "Black"}:
        return jsonify({"error": "Invalid color selected."}), 400

    if size not in {"S", "M", "L", "XL", "XXL"}:
        return jsonify({"error": "Invalid size selected."}), 400

    if print_style not in {"Artwork", "Typography"}:
        return jsonify({"error": "Invalid print style selected."}), 400

    if audience not in {"Male", "Female", "Business", "General"}:
        return jsonify({"error": "Invalid audience selected."}), 400

    if garment_type == "Scarf":
        print_side = "Full"
    elif print_side == "Full":
        print_side = "Front"

    use_ai_mockup = True if AI_ONLY_MODE else (
        PROTOTYPE_DEMO_MODE or bool(
            AUTO_AI_MOCKUP_FROM_PROMPT and inferred and inferred.get("explicit_garment")
        )
    )

    structured = build_structured_prompts(
        user_prompt=normalized_prompt,
        garment_type=garment_type,
        print_side=print_side,
        color=color,
        size=size,
        print_style=print_style,
        audience=audience,
    )
    improved_prompt = improve_prompt(
        normalized_prompt,
        garment_type=garment_type,
        print_side=print_side,
        garment_color=color,
        print_style=print_style,
        audience=audience,
    )
    final_generation_prompt = " ".join(
        x
        for x in [
            structured.get("generation_prompt", "").strip(),
            improved_prompt.strip(),
        ]
        if x
    )
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    reference = request.files.get("reference_image")
    reference_path = None
    design_path = GENERATED_DIR / f"design_{timestamp}.png"
    generation_mode = "direct"
    used_reference_style = False
    if reference and reference.filename:
        if not _is_allowed(reference.filename):
            return jsonify({"error": "Unsupported image format. Use PNG/JPG/JPEG/WEBP."}), 400

        filename = secure_filename(reference.filename)
        suffix = Path(filename).suffix.lower() or ".png"
        reference_path = GENERATED_DIR / f"reference_{timestamp}{suffix}"
        reference.save(reference_path)
        final_generation_prompt = (
            f"{final_generation_prompt} "
            "Reference guidance: preserve the uploaded reference color energy and texture mood only; "
            "do not copy layout literally; follow the customer's concept and composition requirements."
        )

    try:
        design_path, generation_mode = _generate_design_with_fallbacks(
            prompt=final_generation_prompt,
            improved_prompt=improved_prompt,
            user_prompt=normalized_prompt,
            output_path=design_path,
            retries=IMAGE_RETRIES,
            negative_prompt=structured.get("negative_prompt"),
        )
    except Exception as exc:
        return jsonify({"error": f"Image generation failed after fallback attempts: {exc}"}), 502

    if reference_path and os.getenv("ENABLE_REFERENCE_STYLE_BLEND", "true").lower() in {"1", "true", "yes"}:
        try:
            styled_path = GENERATED_DIR / f"design_refstyled_{timestamp}.png"
            design_path = _apply_reference_style(design_path, reference_path, styled_path)
            used_reference_style = True
        except Exception as exc:
            app.logger.warning("Reference style blend skipped due to error: %s", exc)

    suggestions = suggest_design_elements(prompt, garment_type=garment_type)
    cost_price, selling_price = calculate_price(material, tshirt_type, garment_type)
    template_path = None
    if not use_ai_mockup:
        try:
            template_path = _resolve_template(garment_type, print_side, color=color)
        except FileNotFoundError as exc:
            return jsonify({"error": str(exc)}), 500

    mockup_path = GENERATED_DIR / f"mockup_{timestamp}.png"
    print_ready_path = GENERATED_DIR / f"print_ready_{timestamp}.png"
    animation_path = GENERATED_DIR / f"mockup_{timestamp}.gif"
    scarf_flat_preview_path: Path | None = None
    scarf_mannequin_preview_path: Path | None = None
    animation_error = ""
    print_ready_error = ""
    logo_to_use = LOGO_PATH if LOGO_PATH.exists() else None

    try:
        if use_ai_mockup:
            if garment_type == "Scarf":
                blank_scarf = GENERATED_DIR / f"scarf_blank_{timestamp}.png"
                printed_flat_scarf = GENERATED_DIR / f"scarf_printed_flat_{timestamp}.png"
                mannequin_scarf = GENERATED_DIR / f"scarf_mannequin_{timestamp}.png"
                create_flat_garment_template(
                    garment_type="Scarf",
                    color=color,
                    output_path=blank_scarf,
                    print_side="Full",
                )
                generate_mockup(
                    design_path=str(design_path),
                    tshirt_path=str(blank_scarf),
                    logo_path=None,
                    output_path=str(printed_flat_scarf),
                    garment_type="Scarf",
                    print_side="Full",
                )
                mannequin_prompt = (
                    f"Simple ecommerce product photo of one {color.lower()} scarf draped on a plain mannequin torso stand. "
                    f"Design on scarf: {normalized_prompt}. "
                    "No human model, no face, no hands, plain studio background, centered framing, high textile detail."
                )
                generate_image_from_prompt(
                    prompt=mannequin_prompt,
                    output_path=mannequin_scarf,
                    retries=IMAGE_RETRIES,
                    negative_prompt=(
                        "human face, person, hands, arms, legs, full body model, multiple scarves, "
                        "busy background, blurry, low quality, watermark"
                    ),
                )
                scarf_flat_preview_path = printed_flat_scarf
                scarf_mannequin_preview_path = mannequin_scarf
                # Keep generic mockup path pointing to mannequin preview for history compatibility.
                mockup_path = mannequin_scarf
            else:
                demo_prompt = _build_ai_mockup_prompt(
                    prompt=normalized_prompt,
                    garment_type=garment_type,
                    tshirt_type=tshirt_type,
                    print_side=print_side,
                    color=color,
                    print_style=print_style,
                    audience=audience,
                )
                generate_image_from_prompt(
                    prompt=demo_prompt,
                    output_path=mockup_path,
                    retries=IMAGE_RETRIES,
                    negative_prompt=(
                        (
                            "person, human face, eyes, hands, arms, legs, full body model, duplicate scarves, "
                            "blurry, low quality, watermark, cropped product, text artifacts, deformed cloth, "
                            "extra ornaments, extra symbols, extra random motifs"
                            if SCARF_RENDER_STYLE != "flat"
                            else "person, model, mannequin, neck, face, body, hands, arms, wearing scarf, "
                            "blurry, low quality, watermark, cropped product, text artifacts, deformed cloth, "
                            "extra ornaments, extra symbols, extra random motifs"
                        )
                        if garment_type == "Scarf"
                        else (
                            "person, human, model, face, head, hands, arms, legs, full body, mannequin wearer, "
                            "busy scene, cluttered background, blurry, low quality, watermark, cropped product, "
                            "text artifacts, deformed cloth, extra decorative elements, extra symbols, "
                            "extra typography, random background motifs"
                        )
                    ),
                )
        else:
            generate_mockup(
                design_path=str(design_path),
                tshirt_path=str(template_path),
                logo_path=str(logo_to_use) if logo_to_use else None,
                output_path=str(mockup_path),
                garment_type=garment_type,
                print_side=print_side,
            )
        should_export_print_ready = ENABLE_PRINT_READY and (
            garment_type == "Scarf" or (not use_ai_mockup or ALLOW_PRINT_READY_WITH_AI_MOCKUP)
        )
        if should_export_print_ready:
            try:
                generate_print_ready_from_design(
                    design_path=str(design_path),
                    output_path=str(print_ready_path),
                    garment_type=garment_type,
                )
            except Exception as exc:
                # Print-ready export can be expensive; never fail the main response.
                print_ready_error = str(exc)
        elif use_ai_mockup:
            print_ready_error = "Disabled for AI mockup mode (not a guaranteed production print file)."
        if ENABLE_ANIMATION and garment_type != "Scarf":
            try:
                create_mockup_animation(mockup_path, animation_path)
            except Exception as exc:
                # Animation is optional; skip instead of failing the full generation.
                animation_error = str(exc)
    except Exception as exc:
        return jsonify({"error": f"Mockup generation failed: {exc}"}), 500

    mockup_url = url_for("static", filename=f"generated/{mockup_path.name}")
    design_url = url_for("static", filename=f"generated/{Path(design_path).name}")
    if garment_type == "Scarf":
        if scarf_flat_preview_path is not None:
            design_url = url_for("static", filename=f"generated/{scarf_flat_preview_path.name}")
        if scarf_mannequin_preview_path is not None:
            mockup_url = url_for("static", filename=f"generated/{scarf_mannequin_preview_path.name}")
    if use_ai_mockup and MATCH_PREVIEW_IMAGES_IN_AI_MODE and garment_type != "Scarf":
        design_url = mockup_url
    print_ready_url = (
        url_for("static", filename=f"generated/{print_ready_path.name}") if print_ready_path.exists() else None
    )
    animation_url = (
        url_for("static", filename=f"generated/{animation_path.name}") if animation_path.exists() else None
    )
    if garment_type == "Scarf":
        animation_url = None

    assistant_lines = [
        "Done.",
        f"{garment_type} | {print_side} | {color} | Size {size}",
        f"Style: {print_style} | Audience: {audience}",
        f"Mode: {'AI Mockup' if use_ai_mockup else 'Template Placement'}",
        f"Cost: INR {cost_price} | Sell: INR {selling_price}",
    ]
    if VERBOSE_ASSISTANT_MESSAGE:
        assistant_lines.extend(
            [
                f"Template: {template_path.name if template_path else 'AI generated mockup'}",
                f"Inference: garment={inferred.get('garment_type') or '-'}, side={inferred.get('print_side') or '-'}, color={inferred.get('color') or '-'}",
                f"Generation mode: {generation_mode}",
                f"Reference: {'style-guided transform' if used_reference_style else ('uploaded but generation-only' if reference_path else 'no reference')}",
                f"Enhanced prompt: {improved_prompt}",
                f"Layout spec: {structured.get('layout_prompt', '')}",
            ]
        )
    if animation_error:
        assistant_lines.append("Animation preview skipped to keep response stable.")
    if print_ready_error:
        assistant_lines.append("Print-ready not provided for this run.")

    payload = {
        "assistant_message": "\n".join(assistant_lines),
        "suggestions": suggestions,
        "cost_price": cost_price,
        "selling_price": selling_price,
        "garment_type": garment_type,
        "print_side": print_side,
        "color": color,
        "size": size,
        "print_style": print_style,
        "audience": audience,
        "generation_prompt": final_generation_prompt,
        "layout_prompt": structured.get("layout_prompt", ""),
        "mockup_url": mockup_url,
        "design_url": design_url,
        "print_ready_url": print_ready_url,
        "animation_url": animation_url,
    }

    try:
        _append_history(
            {
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "prompt": prompt,
                "garment_type": garment_type,
                "print_side": print_side,
                "color": color,
                "size": size,
                "print_style": print_style,
                "audience": audience,
                "cost_price": cost_price,
                "selling_price": selling_price,
                "mockup_url": mockup_url,
                "design_url": design_url,
                "print_ready_url": print_ready_url,
                "animation_url": animation_url,
            }
        )
    except Exception as exc:
        app.logger.warning("History write skipped due to error: %s", exc)

    return jsonify(payload)


@app.errorhandler(413)
def handle_request_too_large(_err):
    if _is_api_request_path(request.path or ""):
        limit_mb = app.config.get("MAX_CONTENT_LENGTH", 0) // (1024 * 1024)
        return jsonify({"error": f"Uploaded file is too large. Max size is {limit_mb} MB."}), 413
    return jsonify({"error": "Request entity too large."}), 413


@app.errorhandler(HTTPException)
def handle_http_exception(err: HTTPException):
    if _is_api_request_path(request.path or ""):
        return jsonify({"error": err.description or "Request failed."}), err.code
    return err


@app.errorhandler(Exception)
def handle_unexpected_exception(err: Exception):
    if _is_api_request_path(request.path or ""):
        return jsonify({"error": f"Internal server error: {err}"}), 500
    return jsonify({"error": "Internal server error."}), 500


if __name__ == "__main__":
    app.run(debug=True)
