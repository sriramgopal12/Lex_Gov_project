import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai

backend_dir = Path(__file__).resolve().parent.parent
load_dotenv(backend_dir / ".env")

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError("GEMINI_API_KEY was not found in backend/.env")

client = genai.Client(api_key=api_key)

interaction = client.interactions.create(
    model="gemini-3.6-flash",
    input="Explain what a legal document is in one simple sentence."
)

print("LLM Response:")
print(interaction.output_text)