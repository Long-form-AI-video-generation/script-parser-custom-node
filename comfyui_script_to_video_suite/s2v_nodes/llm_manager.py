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
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_MAX_TOKENS = int(os.getenv("OPENAI_MAX_TOKENS", "12000"))

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

def ask_openai_via_proxy(prompt: str, response_format=None, system_message: str | None = None) -> str:
    """New functionality: Calls OpenAI via Proxy"""
    if not OPENAI_API_KEY:
        return "Error: OPENAI_API_KEY not set."

    http_client_kwargs = {"timeout": 60.0}
    if OPENAI_PROXY:
        http_client_kwargs["proxy"] = OPENAI_PROXY
    
    client = OpenAI(
        api_key=OPENAI_API_KEY,
        http_client=httpx.Client(**http_client_kwargs)
    )
    
    try:
        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": prompt})

        request_kwargs = {
            "model": OPENAI_MODEL,
            "messages": messages,
            "max_tokens": OPENAI_MAX_TOKENS,
            "temperature": 0.2,
        }
        if response_format is not None:
            request_kwargs["response_format"] = response_format

        response = client.chat.completions.create(**request_kwargs)
        choice = response.choices[0]

        usage = getattr(response, "usage", None)
        usage_text = ""
        if usage is not None:
            usage_text = (
                f" | tokens prompt={getattr(usage, 'prompt_tokens', '?')} "
                f"completion={getattr(usage, 'completion_tokens', '?')} "
                f"total={getattr(usage, 'total_tokens', '?')}"
            )
        print(f"✅ OpenAI finish_reason={choice.finish_reason}{usage_text}")

        if choice.finish_reason == "length":
            return (
                "Error: OpenAI response was truncated before completion. "
                "Increase OPENAI_MAX_TOKENS or reduce Prompt Generator batch_size."
            )
        if choice.finish_reason == "content_filter":
            return "Error: OpenAI response was blocked by the content filter."

        refusal = getattr(choice.message, "refusal", None)
        if refusal:
            return f"Error: OpenAI refused the request: {refusal}"

        content = choice.message.content
        if not content:
            return "Error: OpenAI returned an empty message."
        return content
    except Exception as e:
        return f"Error: OpenAI request failed: {e}"

def query_llm(prompt: str, response_format=None, system_message: str | None = None) -> str:
    """
    The Router: Decides which provider to use based on the .env file.
    """
    if USE_OPENAI:
        print("🚀 Using OpenAI via Proxy...")
        return ask_openai_via_proxy(
            prompt,
            response_format=response_format,
            system_message=system_message,
        )
    else:
        print("🧠 Using Gemini Relay Server...")
        return ask_gemini_via_relay(prompt)
