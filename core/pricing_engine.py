def calculate_price(material, tshirt_type, garment_type="T-Shirt"):
    base_cost = 200

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

    garment_cost = {
        "T-Shirt": 0,
        "Hoodie": 180,
    }

    cost_price = base_cost + material_cost[material] + type_cost[tshirt_type] + garment_cost[garment_type]
    selling_price = cost_price * 1.8

    return int(cost_price), int(selling_price)
