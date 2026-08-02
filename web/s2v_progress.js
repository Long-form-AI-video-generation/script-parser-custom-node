import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

// Shows S2V progress announcements as toast notifications so they are
// visible in every UI mode (graph view, app mode, mobile).
app.registerExtension({
    name: "s2v.progress",
    setup() {
        api.addEventListener("s2v.progress", (event) => {
            const text = event?.detail?.text ?? "";
            if (!text) return;
            try {
                app.extensionManager.toast.add({
                    severity: "info",
                    summary: "Progress",
                    detail: text,
                    life: 8000,
                });
            } catch (e) {
                console.log("[S2V Progress]", text);
            }
        });
    },
});
