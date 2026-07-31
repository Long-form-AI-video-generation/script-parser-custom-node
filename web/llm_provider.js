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
        }
    }
});
