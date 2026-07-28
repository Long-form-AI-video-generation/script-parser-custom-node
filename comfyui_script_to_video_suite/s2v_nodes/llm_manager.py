import os
import httpx
import requests
from dotenv import load_dotenv

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

load_dotenv()

# Configuration
# Default to False if not set
USE_OPENAI = os.getenv("USE_OPENAI", "False").lower() == "true"
GEMINI_RELAY_URL = os.getenv("RELAY_SERVER_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_PROXY = os.getenv("OPENAI_PROXY")

def ask_gemini_via_relay(prompt: str) -> str:
    """Old functionality: Calls your Relay Server"""
    if not GEMINI_RELAY_URL:
        return "Error: RELAY_SERVER_URL not set."
    try:
        response = requests.post(
            GEMINI_RELAY_URL, 
            json={"prompt": prompt}, 
            timeout=(100, 600)
        )
        return response.json().get("response", "Error: Malformed JSON")
    except Exception as e:
        return f"Error: {e}"

def ask_openai_via_proxy(prompt: str) -> str:
    """New functionality: Calls OpenAI via Proxy"""
    if not OPENAI_API_KEY:
        return "Error: OPENAI_API_KEY not set."
    if OpenAI is None:
        return "Error: openai package is not installed in the ComfyUI environment."
    
    client = OpenAI(
        api_key=OPENAI_API_KEY,
        http_client=httpx.Client(proxy=OPENAI_PROXY, timeout=60.0)
    )
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4000,
            temperature=0.2  
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error: {e}"

def query_llm(prompt: str) -> str:
    """
    The Router: Decides which provider to use based on the .env file.
    """
    if USE_OPENAI:
        print("🚀 Using OpenAI via Proxy...")
        return ask_openai_via_proxy(prompt)
    else:
        print("🧠 Using Gemini Relay Server...")
        return ask_gemini_via_relay(prompt)
