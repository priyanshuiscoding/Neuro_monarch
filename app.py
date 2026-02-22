from datetime import datetime
import os
import json
from pathlib import Path

from flask import Flask, jsonify, render_template, request, url_for
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from werkzeug.exceptions import HTTPException

from core.design_suggestor import suggest_design_elements
from core.image_generation import generate_image_from_prompt
from core.mockup_engine import generate_mockup, generate_print_ready_from_design
from core.prompt_builder import build_structured_prompts
from core.pricing_engine import calculate_price
from core.prompt_engine import improve_prompt
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
IMAGE_RETRIES = int(os.getenv("IMAGE_RETRIES", "1"))
IS_RENDER = (
    os.getenv("RENDER", "").lower() in {"1", "true", "yes"}
    or bool(os.getenv("RENDER_SERVICE_ID"))
)
ENABLE_ANIMATION = os.getenv("ENABLE_ANIMATION", "false" if IS_RENDER else "true").lower() in {
    "1",
    "true",
    "yes",
}


def _is_allowed(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _variant_files(folder: Path, stem: str) -> list[Path]:
    return [folder / f"{stem}.{ext}" for ext in ("png", "jpg", "jpeg", "webp")]


def _is_api_request_path(path: str) -> bool:
    return path.startswith("/chat") or path.startswith("/history")


def _resolve_template(garment_type: str, print_side: str, color: str = "White") -> Path:
    color_key = (color or "White").strip().lower()
    if color_key not in {"white", "black"}:
        color_key = "white"

    if garment_type == "Hoodie" and print_side == "Front":
        candidates = []
        for folder in (HOODIE_DIR, HOODIE_ALT_DIR):
            candidates.extend(_variant_files(folder, f"{color_key}_front"))
            candidates.extend(_variant_files(folder, color_key))
        candidates.extend([
            HOODIE_FRONT_PATH,
            HOODIE_FRONT_JPG_PATH,
            HOODIE_FRONT_JPEG_PATH,
            HOODIE_PATH,
            HOODIE_JPG_PATH,
            HOODIE_JPEG_PATH,
            HOODIE_ALT_DIR / "white_front.png",
            HOODIE_ALT_DIR / "white_front.jpg",
            HOODIE_ALT_DIR / "white_front.jpeg",
            HOODIE_ALT_DIR / "white.png",
            HOODIE_ALT_DIR / "white.jpg",
            HOODIE_ALT_DIR / "white.jpeg",
        ])
    elif garment_type == "Hoodie" and print_side == "Back":
        candidates = []
        for folder in (HOODIE_DIR, HOODIE_ALT_DIR):
            candidates.extend(_variant_files(folder, f"{color_key}_back"))
            candidates.extend(_variant_files(folder, color_key))
        candidates.extend([
            HOODIE_BACK_PATH,
            HOODIE_BACK_JPG_PATH,
            HOODIE_BACK_JPEG_PATH,
            HOODIE_PATH,
            HOODIE_JPG_PATH,
            HOODIE_JPEG_PATH,
            HOODIE_ALT_DIR / "white_back.png",
            HOODIE_ALT_DIR / "white_back.jpg",
            HOODIE_ALT_DIR / "white_back.jpeg",
            HOODIE_ALT_DIR / "white.png",
            HOODIE_ALT_DIR / "white.jpg",
            HOODIE_ALT_DIR / "white.jpeg",
        ])
    elif garment_type == "T-Shirt" and print_side == "Back":
        candidates = (
            _variant_files(TSHIRT_DIR, f"{color_key}_back")
            + [TSHIRT_BACK_PATH, TSHIRT_BACK_JPG_PATH, TSHIRT_BACK_JPEG_PATH]
            + _variant_files(TSHIRT_DIR, color_key)
            + [TSHIRT_PATH]
        )
    else:
        candidates = (
            _variant_files(TSHIRT_DIR, f"{color_key}_front")
            + _variant_files(TSHIRT_DIR, color_key)
            + [TSHIRT_FRONT_PATH, TSHIRT_PATH]
        )

    for item in candidates:
        if item.exists():
            return item
    wanted = ", ".join(str(p) for p in candidates)
    raise FileNotFoundError(f"No template image found for {garment_type} ({print_side}). Expected one of: {wanted}")


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
    material = request.form.get("material", "Cotton")
    tshirt_type = request.form.get("tshirt_type", "Crew Neck")
    garment_type = request.form.get("garment_type", "T-Shirt")
    print_side = request.form.get("print_side", "Front")
    color = request.form.get("color", "White")
    size = request.form.get("size", "M")
    print_style = request.form.get("print_style", "Artwork")
    audience = request.form.get("audience", "Male")

    if not prompt:
        return jsonify({"error": "Please enter a design prompt."}), 400

    if material not in {"Cotton", "Polyester", "Blend"}:
        return jsonify({"error": "Invalid material selected."}), 400

    if tshirt_type not in {"Crew Neck", "V Neck", "Oversized"}:
        return jsonify({"error": "Invalid t-shirt type selected."}), 400

    if garment_type not in {"T-Shirt", "Hoodie"}:
        return jsonify({"error": "Invalid garment type selected."}), 400

    if print_side not in {"Front", "Back"}:
        return jsonify({"error": "Invalid print side selected."}), 400

    if color not in {"White", "Black"}:
        return jsonify({"error": "Invalid color selected."}), 400

    if size not in {"S", "M", "L", "XL", "XXL"}:
        return jsonify({"error": "Invalid size selected."}), 400

    if print_style not in {"Artwork", "Typography"}:
        return jsonify({"error": "Invalid print style selected."}), 400

    if audience not in {"Male", "Female", "Business", "General"}:
        return jsonify({"error": "Invalid audience selected."}), 400

    structured = build_structured_prompts(
        user_prompt=prompt,
        garment_type=garment_type,
        print_side=print_side,
        color=color,
        size=size,
        print_style=print_style,
        audience=audience,
    )
    improved_prompt = improve_prompt(prompt)
    final_generation_prompt = structured.get("generation_prompt") or improved_prompt
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    reference = request.files.get("reference_image")
    design_path = None

    if reference and reference.filename:
        if not _is_allowed(reference.filename):
            return jsonify({"error": "Unsupported image format. Use PNG/JPG/JPEG/WEBP."}), 400

        filename = secure_filename(reference.filename)
        suffix = Path(filename).suffix.lower() or ".png"
        design_path = GENERATED_DIR / f"reference_{timestamp}{suffix}"
        reference.save(design_path)
    else:
        design_path = GENERATED_DIR / f"design_{timestamp}.png"
        try:
            generate_image_from_prompt(
                prompt=final_generation_prompt,
                output_path=design_path,
                retries=IMAGE_RETRIES,
                negative_prompt=structured.get("negative_prompt"),
            )
        except Exception as exc:
            return jsonify({"error": f"Image generation failed: {exc}"}), 502

    suggestions = suggest_design_elements(prompt)
    cost_price, selling_price = calculate_price(material, tshirt_type, garment_type)
    template_path = None
    if not PROTOTYPE_DEMO_MODE:
        try:
            template_path = _resolve_template(garment_type, print_side, color=color)
        except FileNotFoundError as exc:
            return jsonify({"error": str(exc)}), 500

    mockup_path = GENERATED_DIR / f"mockup_{timestamp}.png"
    print_ready_path = GENERATED_DIR / f"print_ready_{timestamp}.png"
    animation_path = GENERATED_DIR / f"mockup_{timestamp}.gif"
    animation_error = ""
    logo_to_use = LOGO_PATH if LOGO_PATH.exists() else None

    try:
        if PROTOTYPE_DEMO_MODE:
            demo_prompt = (
                f"Premium ecommerce apparel mockup photo, {color.lower()} {garment_type.lower()}, "
                f"{tshirt_type.lower()} fit, {print_side.lower()} print placement, "
                f"design concept: {prompt}. "
                "Studio lighting, realistic fabric folds, centered product framing, high-detail print texture, "
                "professional catalog style, no watermark."
            )
            generate_image_from_prompt(
                prompt=demo_prompt,
                output_path=mockup_path,
                retries=IMAGE_RETRIES,
                negative_prompt=(
                    "blurry, low quality, watermark, extra hands, cropped product, text artifacts, deformed cloth"
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
        generate_print_ready_from_design(
            design_path=str(design_path),
            output_path=str(print_ready_path),
            garment_type=garment_type,
        )
        if ENABLE_ANIMATION:
            try:
                create_mockup_animation(mockup_path, animation_path)
            except Exception as exc:
                # Animation is optional; skip instead of failing the full generation.
                animation_error = str(exc)
    except Exception as exc:
        return jsonify({"error": f"Mockup generation failed: {exc}"}), 500

    mockup_url = url_for("static", filename=f"generated/{mockup_path.name}")
    design_url = url_for("static", filename=f"generated/{Path(design_path).name}")
    print_ready_url = url_for("static", filename=f"generated/{print_ready_path.name}")
    animation_url = (
        url_for("static", filename=f"generated/{animation_path.name}") if animation_path.exists() else None
    )

    assistant_lines = [
        "Design pipeline complete.",
        f"Garment: {garment_type} | Side: {print_side} | Color: {color} | Size: {size}",
        f"Audience: {audience}",
        f"Print style: {print_style}",
        f"Template used: {template_path.name if template_path else 'AI generated mockup'}",
        f"Mode: {'Prototype AI Mockup' if PROTOTYPE_DEMO_MODE else 'Template Placement'}",
        f"Enhanced prompt: {improved_prompt}",
        f"Layout spec: {structured.get('layout_prompt', '')}",
        f"Estimated cost price: INR {cost_price}",
        f"Recommended selling price: INR {selling_price}",
    ]
    if animation_error:
        assistant_lines.append("Animation preview skipped to keep response stable.")

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
