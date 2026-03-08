def suggest_design_elements(description, garment_type="T-Shirt"):
    suggestions = []

    if "dragon" in description.lower():
        suggestions.append("Add flames or smoke for aggressive appeal")
        suggestions.append("Use red and black contrast")

    if "car" in description.lower():
        suggestions.append("Add motion blur or neon lighting")
        suggestions.append("Side-angle racing pose works best")

    if not suggestions:
        suggestions.append("Try minimal typography or abstract shapes")

    if garment_type == "Scarf":
        suggestions.append("Use edge-to-edge composition with small bleed-safe border")
        suggestions.append("Prefer seamless motifs for full scarf coverage")
    if garment_type == "Pants":
        suggestions.append("Keep key subject on upper panel for visibility and print stability")

    return suggestions
