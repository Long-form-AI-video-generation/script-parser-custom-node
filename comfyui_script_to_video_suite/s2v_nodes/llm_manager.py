import os
import httpx
from openai import OpenAI
import requests
from dotenv import load_dotenv
import anthropic

load_dotenv()

# Configuration
# Default to False if not set
USE_OPENAI = os.getenv("USE_OPENAI", "False").lower() == "true"
GEMINI_RELAY_URL = os.getenv("RELAY_SERVER_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_PROXY = os.getenv("OPENAI_PROXY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_PROXY = os.getenv("GEMINI_PROXY")
_active_llm_config = None

# def ask_gemini_via_relay(prompt: str) -> str:
#     """Old functionality: Calls your Relay Server"""
#     if not GEMINI_RELAY_URL:
#         return "Error: RELAY_SERVER_URL not set."
#     try:
#         response = requests.post(
#             GEMINI_RELAY_URL, 
#             json={"prompt": prompt}, 
#             timeout=(100, 600)
#         )
#         return response.json().get("response", "Error: Malformed JSON")
#     except Exception as e:
#         return f"Error: {e}"

def ask_gemini_via_proxy(prompt: str) -> str:
    """Calls Gemini directly via Proxy using environment variables"""
    if not GEMINI_API_KEY:
        return "Error: GEMINI_API_KEY not set."
    
    model = "gemini-1.5-flash"
    try:
        if GEMINI_PROXY:
            os.environ["HTTPS_PROXY"] = GEMINI_PROXY
            
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY, transport="rest")
        
        client = genai.GenerativeModel(model_name=model)
        response = client.generate_content(
            prompt,
            generation_config={
                "temperature": 0.2,
                "max_output_tokens": 4000
            }
        )
        return response.text
    except Exception as e:
        return f"Error: Gemini call failed: {e}"

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



def set_active_config(config: dict):
    """Sets the active configuration globally in memory."""
    global _active_llm_config
    _active_llm_config = config
    print(f" LLM Provider: Configured provider to '{config.get('provider')}' ")

def clear_active_config():
    """Clears the active configuration from memory."""
    global _active_llm_config
    _active_llm_config = None

def call_gemini_with_config(prompt: str, api_key: str, temperature: float, max_tokens: int) -> str:
    """Calls Gemini directly via SDK using custom configuration parameters."""
    if not api_key:
        return "Error: Gemini API Key is missing/empty."
    model = "gemini-1.5-flash"
    try:
        proxy = os.getenv("GEMINI_PROXY")
        if proxy:
            os.environ["HTTPS_PROXY"] = proxy
            
        import google.generativeai as genai
        genai.configure(api_key=api_key, transport="rest")
        
        client = genai.GenerativeModel(model_name=model)
        response = client.generate_content(
            prompt,
            generation_config={
                "temperature": temperature,
                "max_output_tokens": max_tokens
            }
        )
        return response.text
    except Exception as e:
        return f"Error: Gemini call failed: {e}"

def call_openai_with_config(prompt: str, api_key: str, temperature: float, max_tokens: int) -> str:
    """Calls OpenAI API using custom configuration parameters."""
    if not api_key:
        return "Error: OpenAI API Key is missing/empty."
    model = "gpt-4o-mini"
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
        content = response.choices[0].message.content
        return content if content is not None else "Error: OpenAI returned empty content."
    except Exception as e:
        return f"Error: OpenAI call failed: {e}"

def call_anthropic_with_config(prompt: str, api_key: str, temperature: float, max_tokens: int) -> str:
    """Calls Anthropic API using custom configuration parameters."""
    if not api_key:
        return "Error: Anthropic API Key is missing/empty."
    model = "claude-3-5-sonnet-20241022"
    try:
        proxy = os.getenv("ANTHROPIC_PROXY")
        if proxy:
            client = anthropic.Anthropic(api_key=api_key, http_client=httpx.Client(proxy=proxy, timeout=60.0))
        else:
            client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.content[0].text
        return text if text is not None else "Error: Anthropic returned empty content."
    except Exception as e:
        return f"Error: Anthropic call failed: {e}"

def call_grok_with_config(prompt: str, api_key: str, temperature: float, max_tokens: int) -> str:
    """Calls Grok API using custom configuration parameters."""
    if not api_key:
        return "Error: Grok API Key is missing/empty."
    model = "grok-2-1212"
    try:
        # Grok has an OpenAI-compatible API
        proxy = os.getenv("GROK_PROXY")
        if proxy:
            client = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1", http_client=httpx.Client(proxy=proxy, timeout=60.0))
        else:
            client = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature
        )
        content = response.choices[0].message.content
        return content if content is not None else "Error: Grok returned empty content."
    except Exception as e:
        return f"Error: Grok call failed: {e}"

def query_llm_with_config(prompt: str, config: dict) -> str:
    """
    Routes the LLM call using the provided in-memory config dict.
    Provides fallback defaults if certain options are empty.
    """
    provider = config.get("provider", "OpenAI")
    api_key = config.get("api_key", "").strip()

    # Static parameters optimized for structured prompt generation tasks
    temperature = 0.2
    max_tokens = 4000

    if provider == "Gemini":
        return call_gemini_with_config(prompt, api_key, temperature, max_tokens)
    elif provider == "OpenAI":
        return call_openai_with_config(prompt, api_key, temperature, max_tokens)
    elif provider == "Anthropic":
        return call_anthropic_with_config(prompt, api_key, temperature, max_tokens)
    elif provider == "Grok":
        return call_grok_with_config(prompt, api_key, temperature, max_tokens)
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
        # print("🧠 Using Gemini Relay Server (from .env)...")
        # return ask_gemini_via_relay(prompt)
        print("🧠 Using Gemini Direct (from .env)...")
        return ask_gemini_via_proxy(prompt)
