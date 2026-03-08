import re


KNOWN_ENTITY_PATTERNS = [
    r"\b(?:shinchan|sinchan|crayon shinchan|crayon shin-chan)\b",
    r"\b(?:naruto|itachi|sasuke|kakashi|gojo|luffy|zoro|goku|vegeta)\b",
    r"\b(?:batman|spiderman|superman|iron man|captain america|hulk)\b",
    r"\b(?:tesla|ferrari|lamborghini|porsche|bmw|mercedes)\b",
]

ENTITY_ALIASES = {
    r"\bsinchan\b": "shinchan",
    r"\bcrayon shinchan\b": "shinchan",
    r"\bcrayon shin-chan\b": "shinchan",
}

CHARACTER_PROFILES = {
    "shinchan": (
        "Character profile for shinchan: mischievous 5-year-old anime boy, short child proportions, "
        "round face, thick straight eyebrows, small dot-like eyes, black short hair, red top, yellow shorts, "
        "playful cartoon expression, flat cel-shaded anime coloring."
    )
}


def _normalize_prompt(text: str) -> str:
    clean = " ".join((text or "").strip().split())
    return clean


def canonicalize_user_prompt(user_prompt: str) -> str:
    text = _normalize_prompt(user_prompt)
    if not text:
        return text
    normalized = text
    for pattern, replacement in ENTITY_ALIASES.items():
        normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)
    return normalized


def _detect_known_entity(prompt: str) -> bool:
    lowered = prompt.lower()
    return any(re.search(pattern, lowered) for pattern in KNOWN_ENTITY_PATTERNS)


def _detect_accessory_terms(prompt: str) -> list[str]:
    lowered = prompt.lower()
    accessories: list[str] = []
    if any(x in lowered for x in ("scarf", "shawl", "bandana")):
        accessories.append("include a visible scarf accessory integrated with the subject")
    if any(x in lowered for x in ("paint", "paint splash", "paint splatter", "brush stroke", "graffiti")):
        accessories.append("include paint-splatter and brush-stroke accents as intentional design elements")
    return accessories


def _character_profile_text(prompt: str) -> str:
    lowered = prompt.lower()
    parts: list[str] = []
    if "shinchan" in lowered:
        parts.append(CHARACTER_PROFILES["shinchan"])
        parts.append(
            "Age/style lock: keep childlike cartoon anatomy; avoid adult, realistic, semi-realistic, military, or photoreal portrait styling."
        )
    return " ".join(parts)


def improve_prompt(
    user_prompt: str,
    garment_type: str = "T-Shirt",
    print_side: str = "Front",
    garment_color: str = "White",
    print_style: str = "Artwork",
    audience: str = "General",
) -> str:
    cleaned = canonicalize_user_prompt(user_prompt)
    if not cleaned:
        return (
            "Premium apparel print artwork, balanced composition, transparent background, "
            "crisp edges, production-ready."
        )

    entity_rule = (
        "Identity fidelity: preserve the exact named character/person/brand cues from the request; "
        "do not replace with a generic subject."
        if _detect_known_entity(cleaned)
        else "Identity fidelity: keep the main subject and key nouns exactly as requested."
    )
    accessory_rules = _detect_accessory_terms(cleaned)
    accessory_line = " ".join(accessory_rules) if accessory_rules else ""
    subject_lock = (
        f"Primary subject lock: '{cleaned}'. Keep this exact subject identity and style intent. "
        "Do not substitute with any unrelated subject."
    )
    shinchan_boost = (
        "If subject is shinchan: maintain a cartoon/anime kid illustration style faithful to shinchan cues; "
        "do not generate animals, beasts, or realistic lion faces."
        if re.search(r"\bshinchan\b", cleaned, flags=re.IGNORECASE)
        else ""
    )
    character_profile = _character_profile_text(cleaned)

    return (
        f"Core concept: {cleaned}. "
        f"Target: {garment_type} {print_side} print, garment color {garment_color}, style {print_style}, audience {audience}. "
        f"{entity_rule} "
        f"{subject_lock} "
        f"{shinchan_boost} "
        f"{character_profile} "
        f"{accessory_line} "
        "Strict content rule: include only what the user asked for; do not add extra decorative objects, "
        "extra text, extra symbols, or unrelated secondary subjects. "
        "Composition: center-weighted design with clean silhouette and protected margins for chest/back print zone. "
        "Production constraints: isolated artwork only, transparent background, no garment mockup, "
        "no scene background, no watermark, high contrast, crisp vector-like edges."
    ).strip()
