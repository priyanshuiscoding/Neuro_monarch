import requests

def improve_prompt(user_prompt, garment_type="T-Shirt", print_side="Front"):
    """
    Uses local Mistral (Ollama) to transform a simple user idea into a 
    professional fashion design prompt tailored for specific garments.
    """
    
    # Context-aware system prompt
    system_prompt = f"""
    You are an expert Fashion Graphic Designer.
    Transform the user's idea: "{user_prompt}" into a high-end professional design prompt.
    
    Target Garment: {garment_type}
    Placement: {print_side}
    
    Requirements for the output prompt:
    1. Focus on 'Apparel Graphics': Mention textures like silk-screen, high-density print, or embroidery.
    2. Composition: Ensure the design is centered and fits the {garment_type} dimensions.
    3. Fashion Appeal: Use keywords like 'streetwear aesthetic', 'minimalist luxury', 'vintage wash', or 'cyberpunk'.
    4. Color Palette: Suggest a specific professional color hex palette.
    5. Technical: Mention 'clean vector lines', 'high contrast', and 'no background'.
    
    Output ONLY the improved prompt text. No conversational filler.
    """

    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "mistral",
                "prompt": system_prompt,
                "stream": False
            },
            timeout=10 # Added timeout to prevent app hanging
        )
        response.raise_for_status()
        return response.json()["response"].strip()
    
    except Exception as e:
        print(f"Ollama Error: {e}")
        # High-quality fallback if Ollama is offline
        return f"Premium {user_prompt} design, professional streetwear fashion graphic, highly detailed, 8k resolution, centered on {garment_type}."