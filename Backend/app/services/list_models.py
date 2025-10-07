import os
import google.generativeai as genai
from dotenv import load_dotenv

# Load API key from .env
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    raise ValueError("❌ GOOGLE_API_KEY not found. Please set it in your .env file.")

# Configure Gemini client
genai.configure(api_key=api_key)

# List available models
print("✅ Available Gemini Models:")
for m in genai.list_models():
    print(f"- {m.name} | supported methods: {m.supported_generation_methods}")
