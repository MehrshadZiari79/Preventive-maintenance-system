# gen_logo_base64.py
import base64
with open("gela-logo.png", "rb") as f:
    print(base64.b64encode(f.read()).decode())