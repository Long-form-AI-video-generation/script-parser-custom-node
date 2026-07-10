import os
import httpx
from openai import OpenAI
import requests
from dotenv import load_dotenv

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

_active_llm_config = None

def set_active_config(config: dict):
    """Sets the active configuration globally in memory."""
    global _active_llm_config
    _active_llm_config = config
    print(f"🔑 LLM Provider: Configured provider to '{config.get('provider')}' (model: '{config.get('model_name')}')")

def clear_active_config():
    """Clears the active configuration from memory."""
    global _active_llm_config
    _active_llm_config = None

def query_llm_with_config(prompt: str, config: dict) -> str:
    """
    Routes the LLM call using the provided in-memory config dict.
    Provides fallback defaults if certain options are empty.
    """
    provider = config.get("provider", "Gemini Relay")
    api_key = config.get("api_key", "").strip()
    model_name = config.get("model_name", "").strip()
    temperature = config.get("temperature", 0.2)
    max_tokens = config.get("max_tokens", 4000)

    if provider == "Gemini Relay":
        return ask_gemini_via_relay(prompt)

    elif provider == "OpenAI":
        if not api_key:
            return "Error: OpenAI API Key is missing/empty."
        model = model_name if model_name else "gpt-4o-mini"
        try:
            proxy = os.getenv("OPENAI_PROXY")
            if proxy:
                client = OpenAI(api_key=api_key, http_client=httpx.Client(proxy=proxy, timeout=60.0))
            else:
                client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error: OpenAI call failed: {e}"

    elif provider == "Anthropic":
        if not api_key:
            return "Error: Anthropic API Key is missing/empty."
        model = model_name if model_name else "claude-3-5-sonnet-20241022"
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            return f"Error: Anthropic call failed: {e}"

    elif provider == "Grok":
        if not api_key:
            return "Error: Grok API Key is missing/empty."
        model = model_name if model_name else "grok-2-1212"
        try:
            # Grok has an OpenAI-compatible API
            client = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error: Grok call failed: {e}"

    else:
        return f"Error: Unknown provider '{provider}'"

def query_llm(prompt: str) -> str:
    """
    The Router: Decides which provider to use.
    If an active in-memory configuration exists, we prioritize it.
    Otherwise, we fall back to the .env file configuration.
    """
    if _active_llm_config:
        return query_llm_with_config(prompt, _active_llm_config)

    if USE_OPENAI:
        print("🚀 Using OpenAI via Proxy (from .env)...")
        return ask_openai_via_proxy(prompt)
    else:
        print("🧠 Using Gemini Relay Server (from .env)...")
        return ask_gemini_via_relay(prompt)