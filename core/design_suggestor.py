def suggest_design_elements(description):
    suggestions = []

    if "dragon" in description.lower():
        suggestions.append("Add flames or smoke for aggressive appeal")
        suggestions.append("Use red and black contrast")

    if "car" in description.lower():
        suggestions.append("Add motion blur or neon lighting")
        suggestions.append("Side-angle racing pose works best")

    if not suggestions:
        suggestions.append("Try minimal typography or abstract shapes")

    return suggestions
