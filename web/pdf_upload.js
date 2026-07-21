import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

function isPdfUploadInput(inputData) {
    return Boolean(inputData?.[1]?.pdf_upload);
}

function getUploadedPath(uploadResponse) {
    return uploadResponse.subfolder
        ? `${uploadResponse.subfolder}/${uploadResponse.name}`
        : uploadResponse.name;
}

function addComboValue(widget, value) {
    if (!widget.options) {
        widget.options = {};
    }

    if (!widget.options.values) {
        widget.options.values = [];
    }

    if (Array.isArray(widget.options.values)) {
        if (!widget.options.values.includes(value)) {
            widget.options.values.push(value);
        }
        return;
    }

    if (typeof widget.options.values === "object") {
        widget.options.values[value] = value;
    }
}

async function uploadPdf(file) {
    const filename = file?.name ?? "";
    if (!filename.toLowerCase().endsWith(".pdf")) {
        throw new Error("Please select a PDF file.");
    }

    const body = new FormData();
    body.append("image", file);
    body.append("type", "input");

    const response = await api.fetchApi("/upload/image", {
        method: "POST",
        body,
    });

    if (response.status !== 200) {
        throw new Error(`${response.status} - ${response.statusText}`);
    }

    return getUploadedPath(await response.json());
}

function openPdfPicker(node, pdfWidget) {
    if (node.isUploadingPdf) {
        alert("PDF upload is already in progress.");
        return;
    }

    const fileInput = document.createElement("input");
    fileInput.type = "file";
    fileInput.accept = ".pdf,application/pdf";

    fileInput.addEventListener("change", async () => {
        const file = fileInput.files?.[0];
        if (!file) {
            return;
        }

        const previousValue = pdfWidget.value;
        pdfWidget.value = file.name;
        node.isUploadingPdf = true;
        node.graph?.setDirtyCanvas(true, true);

        try {
            const uploadedPath = await uploadPdf(file);
            addComboValue(pdfWidget, uploadedPath);
            pdfWidget.value = uploadedPath;
            pdfWidget.callback?.(uploadedPath);
            notify(`PDF uploaded and selected: ${uploadedPath}`);
        } catch (error) {
            pdfWidget.value = previousValue;
            alert(`PDF upload failed: ${error.message ?? error}`);
        } finally {
            node.isUploadingPdf = false;
            node.graph?.setDirtyCanvas(true, true);
        }
    });

    fileInput.click();
}

function notify(text) {
    try {
        app.extensionManager.toast.add({
            severity: "success",
            summary: "PDF Upload",
            detail: text,
            life: 5000,
        });
    } catch (e) {
        console.log("[S2V PDF Upload]", text);
    }
}

function findChunkerNode() {
    const nodes = app.graph?._nodes ?? [];
    return nodes.find(
        (n) => n.type === "PDFUploadChunker_S2V" || n.comfyClass === "PDFUploadChunker_S2V"
    );
}

function ensureFloatingUploadButton() {
    if (document.getElementById("s2v-pdf-upload-fab")) {
        return;
    }

    const btn = document.createElement("button");
    btn.id = "s2v-pdf-upload-fab";
    btn.textContent = "Upload PDF";
    Object.assign(btn.style, {
        position: "fixed",
        bottom: "76px",
        right: "16px",
        zIndex: "10000",
        padding: "10px 16px",
        borderRadius: "8px",
        border: "1px solid #446",
        background: "#2d5a70",
        color: "#fff",
        cursor: "pointer",
        fontSize: "14px",
        boxShadow: "0 2px 8px rgba(0,0,0,0.4)",
        display: "none",
    });

    btn.addEventListener("click", () => {
        const node = findChunkerNode();
        if (!node) {
            alert("This workflow has no PDF Upload Chunker node.");
            return;
        }
        const pdfWidget = node.widgets?.find((w) => w.name === "pdf_file");
        if (!pdfWidget) {
            alert("Could not find the pdf_file selector on the chunker node.");
            return;
        }
        openPdfPicker(node, pdfWidget);
    });

    document.body.appendChild(btn);

    // Only show the button while the loaded workflow contains the node.
    setInterval(() => {
        btn.style.display = findChunkerNode() ? "block" : "none";
    }, 2000);
}

app.registerExtension({
    name: "S2V.PDFUpload",
    setup() {
        ensureFloatingUploadButton();
    },
    beforeRegisterNodeDef(nodeType, nodeData) {
        const requiredInputs = nodeData?.input?.required;
        if (!requiredInputs) {
            return;
        }

        const pdfUploadEntry = Object.entries(requiredInputs).find(([, inputData]) =>
            isPdfUploadInput(inputData)
        );
        if (!pdfUploadEntry) {
            return;
        }

        const [pdfInputName] = pdfUploadEntry;
        const originalOnNodeCreated = nodeType.prototype.onNodeCreated;

        nodeType.prototype.onNodeCreated = function () {
            const result = originalOnNodeCreated?.apply(this, arguments);
            const pdfWidget = this.widgets?.find((widget) => widget.name === pdfInputName);

            if (!pdfWidget || this.widgets?.some((widget) => widget.name === "upload_pdf")) {
                return result;
            }

            const uploadWidget = this.addWidget(
                "button",
                "upload_pdf",
                "pdf",
                () => openPdfPicker(this, pdfWidget),
                { serialize: false }
            );
            uploadWidget.label = "choose PDF to upload";

            return result;
        };
    },
});
