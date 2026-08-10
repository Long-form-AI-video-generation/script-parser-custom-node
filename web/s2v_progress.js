import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

// Shows S2V progress announcements as toast notifications so they are
// visible in every UI mode (graph view, app mode, mobile).
app.registerExtension({
    name: "s2v.progress",
    beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "PromptExecutionStatus_S2V") return;

        const originalCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            originalCreated?.apply(this, arguments);
            this.s2vStatusWidget = this.addWidget(
                "text",
                "current",
                "Waiting for execution",
                () => {},
                { multiline: true }
            );
            this.s2vStatusWidget.disabled = true;
            this.setSize([Math.max(this.size[0], 420), Math.max(this.size[1], 180)]);
        };
    },
    setup() {
        api.addEventListener("s2v.progress", (event) => {
            const text = event?.detail?.text ?? "";
            if (!text) return;
            const nodeId = Number(event?.detail?.node);
            const node = Number.isFinite(nodeId) ? app.graph?._nodes_by_id?.[nodeId] : null;
            if (node?.s2vStatusWidget) {
                node.s2vStatusWidget.value = text;
                node.setDirtyCanvas(true, true);
            }
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
