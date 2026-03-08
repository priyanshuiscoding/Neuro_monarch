import re


def _clean(value: str, default: str) -> str:
    text = (value or "").strip()
    return text if text else default


def _size_hint(size: str) -> str:
    mapping = {
        "S": "compact composition with tighter spacing",
        "M": "balanced composition",
        "L": "balanced composition with moderate negative space",
        "XL": "bolder composition with thicker major forms",
        "XXL": "bolder composition with high readability at distance",
    }
    return mapping.get(size, "balanced composition")


def _placement_hint(garment_type: str, print_side: str) -> str:
    if garment_type == "Scarf" or print_side == "Full":
        return "full-coverage scarf layout across entire printable area with clean edge-safe margins"
    if garment_type == "Pants" and print_side == "Front":
        return "centered vertical composition on upper thigh panel with clean side seam margins"
    if garment_type == "Pants" and print_side == "Back":
        return "centered vertical composition on rear panel with readable spacing and seam-safe margins"
    if garment_type == "Hoodie" and print_side == "Front":
        return "centered below neck, spanning chest to near-waist; avoid pocket overlap"
    if garment_type == "Hoodie" and print_side == "Back":
        return "centered on upper-back to lower-back panel; keep clean margins from hood and hem"
    if garment_type == "T-Shirt" and print_side == "Back":
        return "centered on upper-back panel with strong readability"
    return "centered below neck to mid-torso with production-safe margins"


def _color_strategy(garment_color: str) -> tuple[str, str]:
    c = (garment_color or "").strip().lower()
    if c == "white":
        return (
            "use dark, saturated inks with strong edge contrast",
            "black, charcoal, navy, deep red, cobalt, forest green",
        )
    if c == "black":
        return (
            "use light and vivid inks for visibility on dark fabric",
            "white, cream, cyan, magenta, yellow, neon accents",
        )
    if c == "navy":
        return (
            "use light and warm accents with clear luminance separation",
            "white, cream, yellow, orange, cyan",
        )
    if c == "red":
        return (
            "avoid red-on-red; use neutral and cool contrasting inks",
            "white, black, navy, cyan, cream",
        )
    if c == "green":
        return (
            "avoid green-on-green; use warm or neutral contrasting inks",
            "white, black, cream, orange, yellow",
        )
    return (
        "use high-contrast print-safe inks against garment fabric",
        "balanced contrasting palette",
    )


def _contains_named_entity(text: str) -> bool:
    return bool(re.search(r"\b[A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+)*\b", text or ""))


def _accessory_requirements(text: str) -> str:
    prompt = (text or "").lower()
    requirements: list[str] = []
    if any(x in prompt for x in ("scarf", "shawl", "bandana")):
        requirements.append("must include scarf details exactly as requested")
    if any(x in prompt for x in ("paint", "paint splash", "paint splatter", "brush stroke", "graffiti")):
        requirements.append("must include paint splatter and brush stroke accents")
    return "; ".join(requirements)


def _normalize_known_aliases(text: str) -> str:
    normalized = text or ""
    normalized = re.sub(r"\bsinchan\b", "shinchan", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\bcrayon shinchan\b", "shinchan", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\bcrayon shin-chan\b", "shinchan", normalized, flags=re.IGNORECASE)
    return normalized


def _character_fidelity_boost(text: str) -> str:
    lowered = (text or "").lower()
    if "shinchan" in lowered:
        return (
            "character fidelity boost: shinchan specific facial cues (thick eyebrows, simple dot eyes), "
            "short child body proportions, playful expression, cel-shaded anime colors, red top and yellow shorts."
        )
    return ""


def build_structured_prompts(
    user_prompt: str,
    garment_type: str,
    print_side: str,
    color: str,
    size: str,
    print_style: str,
    audience: str = "",
) -> dict[str, str]:
    idea = _normalize_known_aliases(_clean(user_prompt, "premium fashion graphic"))
    garment = _clean(garment_type, "T-Shirt")
    side = _clean(print_side, "Front")
    cloth_color = _clean(color, "White")
    chosen_size = _clean(size, "M")
    style = _clean(print_style, "Artwork")
    target_audience = _clean(audience, "General")

    placement = _placement_hint(garment, side)
    size_hint = _size_hint(chosen_size)
    color_rule, preferred_palette = _color_strategy(cloth_color)

    style_directive = (
        "text-only typographic design, no characters, no scenery, no photo background"
        if style == "Typography"
        else "illustrative apparel graphic, no scenery, no full-body characters outside design context"
    )
    entity_directive = (
        "strictly preserve all named entities and requested attributes from the concept"
        if _contains_named_entity(idea)
        else "preserve all primary nouns and attributes from the concept"
    )
    accessory_directive = _accessory_requirements(idea)
    character_boost = _character_fidelity_boost(idea)

    accessory_segment = f"Accessory requirements: {accessory_directive}. " if accessory_directive else ""
    character_segment = f"{character_boost}. " if character_boost else ""

    generation_prompt = (
        f"Create a {style.lower()} for apparel print. "
        f"Concept: {idea}. "
        f"Target garment: {garment}, print side: {side}, garment color: {cloth_color}, size target: {chosen_size}. "
        f"Audience context: {target_audience}. "
        f"Placement intent: {placement}. "
        f"Composition: {size_hint}. "
        f"Color strategy: {color_rule}. Preferred palette: {preferred_palette}. "
        f"Fidelity rule: {entity_directive}. "
        f"{STRICT_ONLY_DIRECTIVE} "
        f"{character_segment}"
        f"{accessory_segment}"
        "Output requirements: transparent background PNG look, isolated print artwork only, "
        "high-contrast ink-friendly colors, crisp edges, production-ready composition, no mockup, no garment photo. "
        f"Style directive: {style_directive}."
    )

    negative_prompt = (
        "mockup, t-shirt photo, hoodie photo, person wearing clothes, mannequin, hanger, room background, "
        "wall background, watermark, random unrelated subject replacement, low quality, blur, distorted hands, "
        "extra limbs, text artifacts, unnecessary decorative elements, extra icons, extra logos, extra typography, "
        "ornamental border, random pattern fill"
    )
    if re.search(r"\bshinchan\b", idea, flags=re.IGNORECASE):
        negative_prompt += (
            ", lion, tiger, wolf, beast face, realistic animal portrait, adult male portrait, "
            "military uniform, realistic city scene, photoreal face, mature facial structure"
        )

    layout_prompt = (
        f"Layout spec -> garment={garment}, side={side}, color={cloth_color}, size={chosen_size}, style={style}; "
        f"audience={target_audience}; placement={placement}; color_rule={color_rule}; keep safe margins and print-ready framing."
    )

    return {
        "generation_prompt": generation_prompt,
        "negative_prompt": negative_prompt,
        "layout_prompt": layout_prompt,
    }
STRICT_ONLY_DIRECTIVE = (
    "Strict content rule: include only elements explicitly requested in the concept. "
    "Do not add extra symbols, ornaments, text, background motifs, or secondary subjects."
)
