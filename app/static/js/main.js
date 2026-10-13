let selectedFiles = [];

function setupUploadArea(areaId, fileInputId, fileListId, accept = ".pdf", multiple = true) {
    const area = document.getElementById(areaId);
    const input = document.getElementById(fileInputId);
    const list = document.getElementById(fileListId);

    area.addEventListener("click", () => input.click());

    area.addEventListener("dragover", (e) => {
        e.preventDefault();
        area.classList.add("dragover");
    });

    area.addEventListener("dragleave", () => {
        area.classList.remove("dragover");
    });

    area.addEventListener("drop", (e) => {
        e.preventDefault();
        area.classList.remove("dragover");
        if (multiple) {
            addFiles(Array.from(e.dataTransfer.files), list, accept);
        } else {
            replaceFile(e.dataTransfer.files[0], list, accept);
        }
    });

    input.addEventListener("change", () => {
        if (multiple) {
            addFiles(Array.from(input.files), list, accept);
        } else if (input.files[0]) {
            replaceFile(input.files[0], list, accept);
        }
        input.value = "";
    });
}

function addFiles(files, listElement, accept) {
    for (const file of files) {
        if (accept === "image/*") {
            if (!file.type.startsWith("image/")) continue;
        } else if (accept === "office") {
            const exts = [".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt", ".ods", ".odp"];
            const ext = "." + file.name.split(".").pop().toLowerCase();
            if (!exts.includes(ext)) continue;
        } else if (accept !== "*") {
            const exts = accept.split(",").map(e => e.trim());
            const ext = "." + file.name.split(".").pop().toLowerCase();
            if (!exts.includes(ext)) continue;
        }
        if (!selectedFiles.find(f => f.name === file.name && f.size === file.size)) {
            selectedFiles.push(file);
        }
    }
    renderFileList(listElement);
}

function replaceFile(file, listElement, accept) {
    selectedFiles = [];
    if (file) {
        const exts = accept.split(",").map(e => e.trim());
        const ext = "." + file.name.split(".").pop().toLowerCase();
        if (exts.includes(ext)) {
            selectedFiles = [file];
        }
    }
    renderFileList(listElement);
}

function removeFile(index, listElement) {
    selectedFiles.splice(index, 1);
    renderFileList(listElement);
}

function renderFileList(listElement) {
    listElement.innerHTML = "";
    for (let i = 0; i < selectedFiles.length; i++) {
        const f = selectedFiles[i];
        const item = document.createElement("div");
        item.className = "file-item";
        item.innerHTML = `
            <span>📄</span>
            <span class="name">${escapeHtml(f.name)}</span>
            <span class="size">${formatSize(f.size)}</span>
            <button class="remove-btn" onclick="removeFile(${i}, document.getElementById('${listElement.id}'))">✕</button>
        `;
        listElement.appendChild(item);
    }
}

function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, c => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[c]);
}

async function readError(resp) {
    try {
        const data = await resp.json();
        if (data && data.error) return data.error;
    } catch (_) { /* resposta nao-JSON (ex.: proxy) */ }
    if (resp.status === 413) return "Arquivo grande demais";
    return `Erro no processamento (HTTP ${resp.status})`;
}

function formatSize(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / 1048576).toFixed(1) + " MB";
}

async function uploadForm(url, formData, buttonId) {
    const btn = document.getElementById(buttonId);
    const progress = document.getElementById("progress-bar");
    const status = document.getElementById("status-message");

    btn.disabled = true;
    btn.textContent = "Processando...";
    status.className = "status-message";
    status.style.display = "none";

    if (progress) {
        progress.classList.add("active");
        const fill = progress.querySelector(".progress-fill");
        if (fill) fill.style.width = "80%";
    }

    try {
        const resp = await fetch(url, { method: "POST", body: formData });

        if (!resp.ok) {
            throw new Error(await readError(resp));
        }

        const disposition = resp.headers.get("Content-Disposition");
        let filename = "download";
        if (disposition) {
            const match = disposition.match(/filename\*?=(?:UTF-8''|"?)?"?([^";\s]+)/i);
            if (match) {
                filename = decodeURIComponent(match[1].replace(/"/g, ""));
            } else {
                const m2 = disposition.match(/filename="?([^";\s]+)/i);
                if (m2) filename = m2[1];
            }
        }

        const blob = await resp.blob();
        downloadBlob(blob, filename);

        if (progress) {
            const fill = progress.querySelector(".progress-fill");
            if (fill) fill.style.width = "100%";
        }

        status.className = "status-message success";
        status.textContent = "Concluído! Download iniciado.";
        status.style.display = "block";
    } catch (e) {
        status.className = "status-message error";
        status.textContent = "Erro: " + e.message;
        status.style.display = "block";
    } finally {
        btn.disabled = false;
        btn.textContent = btn.getAttribute("data-label") || "Processar";
        if (progress) {
            setTimeout(() => {
                progress.classList.remove("active");
                const fill = progress.querySelector(".progress-fill");
                if (fill) fill.style.width = "0%";
            }, 1000);
        }
    }
}

function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

function getUploadFormData(inputPrefix = "") {
    const fd = new FormData();
    for (const f of selectedFiles) {
        fd.append(inputPrefix + "files", f);
    }
    return fd;
}
