import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const PDF_UPLOAD_WIDGET_NAME = "upload_pdf";
const PDF_UPLOAD_NODE_NAME = "PDFUploadChunker_S2V";
const PDF_UPLOAD_FALLBACK_INPUT = "pdf_file";

function isPdfUploadInput(inputData) {
    return Boolean(inputData?.[1]?.pdf_upload);
}

function findPdfInputName(nodeData) {
    const requiredInputs = nodeData?.input?.required;
    if (requiredInputs) {
        const pdfUploadEntry = Object.entries(requiredInputs).find(([, inputData]) =>
            isPdfUploadInput(inputData)
        );

        if (pdfUploadEntry) {
            return pdfUploadEntry[0];
        }
    }

    if (
        nodeData?.name === PDF_UPLOAD_NODE_NAME ||
        nodeData?.display_name?.includes("PDF Upload Chunker")
    ) {
        return PDF_UPLOAD_FALLBACK_INPUT;
    }

    return null;
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
    const allowedExts = [".pdf", ".docx", ".txt"];
    const hasValidExt = allowedExts.some(ext => filename.toLowerCase().endsWith(ext));
    if (!hasValidExt) {
        throw new Error("Please select a PDF, DOCX, or TXT file.");
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
    fileInput.accept = ".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain";

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
            notify(`File uploaded and selected: ${uploadedPath}`);
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
            summary: "File Upload",
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
    btn.textContent = "Upload File";
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

function resizeNodeForWidget(node) {
    if (!node.computeSize || !node.setSize) {
        return;
    }

    const computedSize = node.computeSize();
    node.setSize([
        Math.max(node.size?.[0] ?? 0, computedSize[0]),
        Math.max(node.size?.[1] ?? 0, computedSize[1]),
    ]);
}

function ensurePdfUploadWidget(node, pdfInputName) {
    const pdfWidget = node.widgets?.find((widget) => widget.name === pdfInputName);
    if (!pdfWidget || node.widgets?.some((widget) => widget.name === PDF_UPLOAD_WIDGET_NAME)) {
        return;
    }

    const uploadWidget = node.addWidget(
        "button",
        PDF_UPLOAD_WIDGET_NAME,
        "Choose PDF",
        () => openPdfPicker(node, pdfWidget),
        { serialize: false }
    );
    uploadWidget.label = "choose PDF to upload";
    uploadWidget.serialize = false;

    resizeNodeForWidget(node);
    node.graph?.setDirtyCanvas(true, true);
}

function schedulePdfUploadWidget(node, pdfInputName) {
    ensurePdfUploadWidget(node, pdfInputName);
    requestAnimationFrame(() => ensurePdfUploadWidget(node, pdfInputName));
    setTimeout(() => ensurePdfUploadWidget(node, pdfInputName), 0);
}

app.registerExtension({
    name: "S2V.PDFUpload",
    setup() {
        ensureFloatingUploadButton();
    },
    beforeRegisterNodeDef(nodeType, nodeData) {
        const pdfInputName = findPdfInputName(nodeData);
        if (!pdfInputName) {
            return;
        }

        const originalOnNodeCreated = nodeType.prototype.onNodeCreated;
        const originalOnConfigure = nodeType.prototype.onConfigure;
        const originalOnAdded = nodeType.prototype.onAdded;
        const originalGetExtraMenuOptions = nodeType.prototype.getExtraMenuOptions;

        nodeType.prototype.onNodeCreated = function () {
            const result = originalOnNodeCreated?.apply(this, arguments);
            schedulePdfUploadWidget(this, pdfInputName);
            return result;
        };

        nodeType.prototype.onConfigure = function () {
            const result = originalOnConfigure?.apply(this, arguments);
            schedulePdfUploadWidget(this, pdfInputName);
            return result;
        };

        nodeType.prototype.onAdded = function () {
            const result = originalOnAdded?.apply(this, arguments);
            schedulePdfUploadWidget(this, pdfInputName);
            return result;
        };

        nodeType.prototype.getExtraMenuOptions = function (_, options) {
            originalGetExtraMenuOptions?.apply(this, arguments);
            const pdfWidget = this.widgets?.find((widget) => widget.name === pdfInputName);
            if (!pdfWidget) {
                return;
            }

            options.push({
                content: "Upload PDF...",
                callback: () => openPdfPicker(this, pdfWidget),
            });
        };
    },
});
