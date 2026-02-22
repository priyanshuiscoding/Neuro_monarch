def suggest_design_elements(description, garment_type="T-Shirt"):
    """
    Suggests design enhancements based on the subject matter 
    and the specific garment type (T-Shirt vs Hoodie).
    """
    desc = description.lower()
    garment = garment_type.lower()
    suggestions = []

    # Subject-based suggestions
    if "dragon" in desc:
        suggestions.extend([
            "Add realistic smoke plumes that wrap around the torso",
            "Use deep crimson and charcoal grey for high-end contrast",
            "Incorporate intricate scale textures for fabric depth"
        ])
    elif "car" in desc:
        suggestions.extend([
            "Apply horizontal motion blur effects for speed",
            "Use neon accents (cyan/magenta) for a synthwave aesthetic",
            "Add a 'low-angle' perspective to make the car look powerful"
        ])
    elif "nature" in desc or "forest" in desc:
        suggestions.extend([
            "Use an oil-painting texture for a premium look",
            "Incorporate a sun-flare effect for realistic lighting",
            "Add organic borders like pine needles or vines"
        ])
    else:
        suggestions.append("Try a minimalist vintage typography style")

    # Garment-specific placement suggestions
    if garment == "hoodie":
        suggestions.extend([
            "Place the primary design higher on the chest to stay clear of the pocket",
            "Consider a vertical 'sleeve print' for added premium appeal",
            "Ensure the design doesn't get covered by the hood drawstrings"
        ])
    else:
        suggestions.append("Use a centered chest layout for standard fit")

    return suggestions