import os
import openai

openai.api_key = os.getenv("OPENAI_API_KEY")
print("API key loaded:", bool(openai.api_key))
