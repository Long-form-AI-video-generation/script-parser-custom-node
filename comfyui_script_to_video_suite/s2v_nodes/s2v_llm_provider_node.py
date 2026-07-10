from . import llm_manager

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
                "provider": (["Gemini Relay", "OpenAI", "Anthropic", "Grok"], {"default": "Gemini Relay"}),
                "api_key": ("STRING", {"default": "", "multiline": False}),
            }
        }

    RETURN_TYPES = ("LLM_CONFIG",)
    RETURN_NAMES = ("llm_config",)
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
        
        return (config,)
