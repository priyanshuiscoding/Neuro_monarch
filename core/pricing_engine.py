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
        "Pants": 220,
        "Scarf": 90,
    }
    type_extra = type_cost.get(tshirt_type, 0) if garment_type in {"T-Shirt", "Hoodie"} else 0
    cost_price = base_cost + material_cost.get(material, 100) + type_extra + garment_cost.get(garment_type, 0)
    markup = 2.0 if garment_type in {"Hoodie", "Pants"} else 1.8
    selling_price = cost_price * markup

    return int(cost_price), int(selling_price)
