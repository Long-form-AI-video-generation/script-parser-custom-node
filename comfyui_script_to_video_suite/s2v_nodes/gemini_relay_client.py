from .llm_manager import query_llm

def ask_gemini_via_relay(prompt: str) -> str:
    return query_llm(prompt)

