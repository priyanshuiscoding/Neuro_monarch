def calculate_price(material, tshirt_type):
    base = 200

    material_cost = {
        "Cotton": 120,
        "Polyester": 80,
        "Blend": 100
    }

    type_cost = {
        "Crew Neck": 0,
        "V Neck": 40,
        "Oversized": 80
    }

    cost = base + material_cost[material] + type_cost[tshirt_type]
    selling = int(cost * 1.8)

    return cost, selling
