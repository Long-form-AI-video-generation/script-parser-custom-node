from .llm_manager import query_llm

def ask_gemini_via_relay(prompt: str, response_format=None, system_message: str | None = None) -> str:
    return query_llm(
        prompt,
        response_format=response_format,
        system_message=system_message,
    )
