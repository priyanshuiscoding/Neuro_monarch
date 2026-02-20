from PIL import Image
import os

def generate_mockup(design_path, tshirt_path, logo_path, output_path, garment_type, print_side):
    # 1. Load the background (Garment)
    garment = Image.open(tshirt_path).convert("RGBA")
    g_width, g_height = garment.size

    # 2. Load the design
    design = Image.open(design_path).convert("RGBA")
    
    # 3. Calculate Ratio & Scale
    # We want the design to take up about 35% of the garment width for a natural look
    target_width = int(g_width * 0.35)
    aspect_ratio = design.height / design.width
    target_height = int(target_width * aspect_ratio)
    
    design = design.resize((target_width, target_height), Image.Resampling.LANCZOS)

    # 4. Calculate Center Position
    # Horizontal center
    x_pos = (g_width - target_width) // 2
    
    # Vertical position (Higher for Hoodies to avoid the pocket)
    if garment_type.lower() == "hoodie":
        y_pos = int(g_height * 0.28) # Placed on the chest
    else:
        y_pos = int(g_height * 0.30) # Standard T-shirt chest height

    # 5. Paste Design
    garment.paste(design, (x_pos, y_pos), design)

    # 6. Handle Branding Logo (Optional)
    if logo_path and os.path.exists(logo_path):
        logo = Image.open(logo_path).convert("RGBA")
        logo_w = int(g_width * 0.1) # Logo is 10% of garment width
        logo_h = int(logo.height * (logo_w / logo.width))
        logo = logo.resize((logo_w, logo_h), Image.Resampling.LANCZOS)
        
        # Place logo on the top left chest or neck
        garment.paste(logo, (int(g_width * 0.65), int(g_height * 0.15)), logo)

    # 7. Save result
    garment.save(output_path)
    return output_path

def generate_print_ready_from_design(design_path, output_path, garment_type):
    # This remains the same, providing the high-res source design
    img = Image.open(design_path).convert("RGBA")
    img.save(output_path)
    return output_path