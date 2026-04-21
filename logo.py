# convert_logo.py
import base64
from PIL import Image
import os

# Get the directory where this script is located
script_dir = os.path.dirname(os.path.abspath(__file__))
logo_path = os.path.join(script_dir, "logo.png")

if not os.path.exists(logo_path):
    print(f"Error: logo.png not found at {logo_path}")
    print("Make sure the file is in the same folder as this script.")
    exit(1)

# Open and resize the image
img = Image.open(logo_path)
# Resize to a reasonable size for the header (e.g., 40x40 pixels)
img_resized = img.resize((40, 40), Image.Resampling.LANCZOS)

# Save resized version (optional, for reference)
resized_path = os.path.join(script_dir, "logo_resized.png")
img_resized.save(resized_path)
print(f"Resized logo saved to: {resized_path}")

# Convert to base64
with open(logo_path, "rb") as f:
    b64_string = base64.b64encode(f.read()).decode("utf-8")

# Also convert resized version (optional, if you prefer to embed the resized one)
with open(resized_path, "rb") as f:
    b64_resized = base64.b64encode(f.read()).decode("utf-8")

# Print the base64 strings
print("\n" + "="*60)
print("Base64 for ORIGINAL size (use if you want Pillow to resize in code):")
print("="*60)
print(b64_string)
print("\n" + "="*60)
print("Base64 for RESIZED (40x40) - ready to use without resizing in code:")
print("="*60)
print(b64_resized)

# Save to a file for easy copying
output_file = os.path.join(script_dir, "logo_base64.txt")
with open(output_file, "w") as f:
    f.write("ORIGINAL SIZE:\n")
    f.write(b64_string)
    f.write("\n\nRESIZED (40x40):\n")
    f.write(b64_resized)
print(f"\nBase64 strings also saved to: {output_file}")