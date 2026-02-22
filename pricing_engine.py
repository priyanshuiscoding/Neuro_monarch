def calculate_price(material, tshirt_type, garment_type):
    """
    Calculates the manufacturing cost and retail price.
    Updated to handle Hoodies and premium fits.
    """
    # Base manufacturing overhead
    base_cost = 250 

    # Material costs (Hoodies use more fabric, so these are weighted averages)
    material_costs = {
        "Cotton": 180,
        "Polyester": 110,
        "Blend": 140
    }

    # Fit/Style costs
    style_costs = {
        "Crew Neck": 0,
        "V Neck": 50,
        "Oversized": 120
    }
    
    # Garment Type Logic: Hoodies are significantly more expensive to produce
    # (Higher weight, hood construction, and pocket sewing)
    garment_multiplier = 2.2 if garment_type.lower() == "hoodie" else 1.0
    
    # Additional flat fee for Hoodie hardware (drawstrings, etc.)
    garment_flat_extra = 150 if garment_type.lower() == "hoodie" else 0

    # Calculate Total Cost
    # Formula: (Base + Material + Style) * Multiplier + Flat Extra
    subtotal = base_cost + material_costs.get(material, 140) + style_costs.get(tshirt_type, 0)
    total_cost = int((subtotal * garment_multiplier) + garment_flat_extra)

    # Calculate Selling Price (Retail Markup)
    # We use a 1.8x markup for T-Shirts and a 2.0x for premium Hoodies
    markup = 2.0 if garment_type.lower() == "hoodie" else 1.8
    selling_price = int(total_cost * markup)

    return total_cost, selling_price