import { app } from "../../scripts/app.js";

app.registerExtension({
    name: "S2V.LLMProvider",
    async nodeCreated(node) {
        if (node.comfyClass === "LLMProvider_S2V") {
            const apiKeyWidget = node.widgets?.find(w => w.name === "api_key");
            if (apiKeyWidget) {
                // Ensure key is never serialized or saved to the workflow JSON
                apiKeyWidget.serialize = false;
                
                // Mask the input box on creation if it already has DOM input element
                if (apiKeyWidget.inputEl) {
                    apiKeyWidget.inputEl.type = "password";
                }
            }

            const providerWidget = node.widgets?.find(w => w.name === "provider");
            const modelNameWidget = node.widgets?.find(w => w.name === "model_name");

            if (providerWidget && modelNameWidget) {
                // Store original callback to maintain ComfyUI standard behaviors
                const originalCallback = providerWidget.callback;
                
                providerWidget.callback = function (value) {
                    let result;
                    if (originalCallback) {
                        result = originalCallback.apply(this, arguments);
                    }
                    
                    // Update default model name dynamically based on selected provider
                    if (value === "Gemini Relay") {
                        modelNameWidget.value = "";
                    } else if (value === "OpenAI") {
                        modelNameWidget.value = "gpt-4o-mini";
                    } else if (value === "Anthropic") {
                        modelNameWidget.value = "claude-3-5-sonnet-20241022";
                    } else if (value === "Grok") {
                        modelNameWidget.value = "grok-2-1212";
                    }
                    
                    // Sync value to the DOM element if active
                    if (modelNameWidget.inputEl) {
                        modelNameWidget.inputEl.value = modelNameWidget.value;
                    }
                    
                    node.graph?.setDirtyCanvas(true, true);
                    return result;
                };
            }
        }
    }
});
