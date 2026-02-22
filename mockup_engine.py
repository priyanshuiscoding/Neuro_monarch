from PIL import Image, ImageOps
import os

def generate_mockup(design_path, tshirt_path, logo_path, output_path, garment_type, print_side):
    """
    Advanced composition engine for realistic garment placement.
    Handles centering, vertical safe-zones, and side-specific logic.
    """
    # 1. Load the Garment Template
    garment = Image.open(tshirt_path).convert("RGBA")
    g_w, g_h = garment.size

    # 2. Process the Design (Auto-crop empty space first)
    design = Image.open(design_path).convert("RGBA")
    # Remove any extra transparency around the AI design to ensure accurate scaling
    bbox = design.getbbox()
    if bbox:
        design = design.crop(bbox)
    
    # 3. Dynamic Scaling based on Industry Standards
    # A standard print width is 12 inches; we'll simulate this as 38% of garment width
    max_print_width = int(g_w * 0.38)
    
    # Maintain aspect ratio
    aspect_ratio = design.height / design.width
    target_width = max_print_width
    target_height = int(target_width * aspect_ratio)

    # Safety check: if design is too tall, scale by height instead
    if target_height > (g_h * 0.45):
        target_height = int(g_h * 0.45)
        target_width = int(target_height / aspect_ratio)

    design = design.resize((target_width, target_height), Image.Resampling.LANCZOS)

    # 4. Precision Centering (Horizontal)
    x_pos = (g_w - target_width) // 2
    
    # 5. Vertical Logic (The "Perfect Fit" calculation)
    # Hoodies need higher placement to avoid the pocket 'muff'
    # Back prints usually start lower than front prints
    is_hoodie = garment_type.lower() == "hoodie"
    is_back = print_side.lower() == "back"

    if is_hoodie:
        # Avoid hood overhang and pocket
        y_pos = int(g_h * 0.25) if not is_back else int(g_h * 0.22)
    else:
        # Standard T-shirt chest/back placement
        y_pos = int(g_h * 0.28) if not is_back else int(g_h * 0.25)

    # 6. Final Composite
    garment.paste(design, (x_pos, y_pos), design)

    # 7. Logo Placement (Neck/Brand tag area)
    if logo_path and os.path.exists(logo_path):
        logo = Image.open(logo_path).convert("RGBA")
        # Scale logo to roughly 2.5 inches wide
        l_w = int(g_w * 0.07)
        l_h = int(logo.height * (l_w / logo.width))
        logo = logo.resize((l_w, l_h), Image.Resampling.LANCZOS)
        
        # Position logo slightly below the collar
        l_x = (g_w - l_w) // 2
        l_y = int(g_h * 0.12)
        garment.paste(logo, (l_x, l_y), logo)

    # 8. Save with optimized settings
    garment.save(output_path, "PNG", optimize=True)
    return output_path

def generate_print_ready_from_design(design_path, output_path, garment_type):
    """Prepares the design as a standalone PNG with no background for the printer."""
    img = Image.open(design_path).convert("RGBA")
    # Standard 300 DPI metadata (if your printer requires it)
    img.save(output_path, dpi=(300, 300))
    return output_path