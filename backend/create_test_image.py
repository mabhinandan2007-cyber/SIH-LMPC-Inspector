from PIL import Image, ImageDraw, ImageFont

def create_label():
    # Create a white background image
    img = Image.new('RGB', (800, 600), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    
    # Try to load a font, otherwise use default
    font_large = None
    font_small = None
    
    # Draw some text resembling a label
    draw.text((50, 50), "WONDER WHEAT FLOUR", fill=(0,0,0))
    draw.text((50, 100), "Net Weight: 1 kg", fill=(0,0,0))
    draw.text((50, 150), "Ingredients: Whole Wheat", fill=(0,0,0))
    draw.text((50, 200), "Nutritional Info (per 100g):", fill=(0,0,0))
    draw.text((50, 230), "Energy: 340 kcal", fill=(0,0,0))
    
    # MRP and Date (The critical fields)
    draw.text((50, 350), "MRP Rs. 85.00 (Incl. of all taxes)", fill=(0,0,0))
    draw.text((50, 400), "Packed on: 10/2026", fill=(0,0,0))
    draw.text((50, 450), "Best before 6 months from packaging", fill=(0,0,0))
    
    # Mfr info
    draw.text((50, 500), "Mfd. by: Wonder Foods Ltd.", fill=(0,0,0))
    draw.text((50, 530), "Plot 12, Industrial Area, Mumbai", fill=(0,0,0))
    
    img.save("test_label.jpg")
    print("Created test_label.jpg")

if __name__ == "__main__":
    create_label()
