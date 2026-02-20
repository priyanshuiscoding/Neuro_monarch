def improve_prompt(user_prompt: str) -> str:
    cleaned = (user_prompt or "").strip()
    if not cleaned:
        return "Premium streetwear t-shirt artwork with balanced composition and clean details"

    return (
        f"Premium t-shirt design concept: {cleaned}. "
        "Style: high-detail fashion illustration, modern composition, crisp edges, print-ready look. "
        "Color direction: bold but balanced contrast, premium fabric-friendly palette."
    )