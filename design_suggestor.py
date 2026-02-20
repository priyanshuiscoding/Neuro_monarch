def suggest_design_elements(description):
    desc = description.lower()

    if "dragon" in desc:
        return [
            "Add fire or smoke effects",
            "Use red and black color contrast"
        ]

    if "car" in desc:
        return [
            "Add motion blur",
            "Neon street racing background"
        ]

    return ["Try minimal typography or geometric shapes"]
