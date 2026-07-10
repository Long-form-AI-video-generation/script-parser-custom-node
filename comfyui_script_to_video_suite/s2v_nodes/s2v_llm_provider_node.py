from . import llm_manager
from server import PromptServer
from aiohttp import web

@PromptServer.instance.routes.post("/s2v/update_llm_config")
async def update_llm_config(request):
    try:
        json_data = await request.json()
        provider = json_data.get("provider")
        api_key = json_data.get("api_key", "").strip()
        
        # Delegate configuration saving to the node's class method
        LLMProvider_S2V().set_provider(provider, api_key)
        return web.json_response({"status": "success"})
    except Exception as e:
        return web.json_response({"status": "error", "message": str(e)}, status=500)

@PromptServer.instance.routes.post("/s2v/clear_llm_config")
async def clear_llm_config(request):
    try:
        llm_manager.clear_active_config()
        return web.json_response({"status": "success"})
    except Exception as e:
        return web.json_response({"status": "error", "message": str(e)}, status=500)

class LLMProvider_S2V:
    """
    Sets the active LLM provider and API key globally in memory.
    Connect this node's 'llm_config' output to the 'llm_config' input of 
    the 'Storyboard Generator' node to ensure it executes first.
    """
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "provider": (["Gemini", "OpenAI", "Anthropic", "Grok"], {"default": "OpenAI"}),
                "api_key": ("STRING", {"default": "", "multiline": False}),
            }
        }

    RETURN_TYPES = ()
    RETURN_NAMES = ()
    FUNCTION = "set_provider"
    CATEGORY = "Script To Video Suite"

    def set_provider(self, provider: str, api_key: str):
        # Clear any existing configuration to prevent leakages across executions
        llm_manager.clear_active_config()
        
        config = {
            "provider": provider,
            "api_key": api_key.strip()
        }
        
        # Store in the global memory state of llm_manager
        llm_manager.set_active_config(config)
        
        return ()
