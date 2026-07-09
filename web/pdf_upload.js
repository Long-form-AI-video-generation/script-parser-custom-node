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
