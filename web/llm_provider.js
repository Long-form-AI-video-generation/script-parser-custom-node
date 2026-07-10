import { app } from "../../scripts/app.js";

app.registerExtension({
    name: "S2V.LLMProvider",
    async beforeQueue() {
        const node = app.graph.findNodesByType("LLMProvider_S2V")[0];
        if (node && node.mode === 0) {
            const provider = node.widgets?.find(w => w.name === "provider")?.value;
            const apiKey = node.widgets?.find(w => w.name === "api_key")?.value || "";
            
            try {
                await fetch("/s2v/update_llm_config", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify({
                        provider: provider,
                        api_key: apiKey
                    })
                });
                console.log("✅ LLM Provider settings synced to backend successfully.");
            } catch (e) {
                console.error("❌ Failed to sync LLM Provider settings to backend:", e);
            }
        } else {
            try {
                await fetch("/s2v/clear_llm_config", {
                    method: "POST"
                });
                console.log("ℹ️ LLM Provider node is disabled/absent. Reverted to .env settings.");
            } catch (e) {
                console.error("❌ Failed to clear LLM Provider settings in backend:", e);
            }
        }
    },
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
        }
    }
});
