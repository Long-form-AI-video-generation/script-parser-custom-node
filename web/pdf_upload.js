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

app.registerExtension({
    name: "S2V.PDFUpload",
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
                { serialize: false, canvasOnly: true }
            );
            uploadWidget.label = "choose PDF to upload";

            return result;
        };
    },
});
