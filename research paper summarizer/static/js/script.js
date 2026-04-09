const form = document.getElementById("form");
const btn = document.getElementById("btn");
const output = document.getElementById("output");
const progressBar = document.getElementById("progressBar");
const progressText = document.getElementById("progressText");
const progressBox = document.getElementById("progressBox");
const loader = document.getElementById("loader");
const downloadBtn = document.getElementById("downloadBtn");
const lengthSelect = document.getElementById("length");
const fileInput = document.getElementById("file");
const uploadArea = document.getElementById("uploadArea");
const browseBtn = document.getElementById("browseBtn");
const outputCard = document.getElementById("outputCard");
const statusText = document.getElementById("statusText");

// 🔥 Chat elements
const chatBox = document.getElementById("chatBox");
const chatBtn = document.getElementById("chatBtn");
const chatInput = document.getElementById("chatInput");
const chatMessages = document.getElementById("chatMessages");

let finalSummary = "";
let selectedFile = null;
let currentJobId = null;

// Function to show file preview
function showFilePreview(file) {
    selectedFile = file;

    uploadArea.innerHTML = `
        <i class="fas fa-file-pdf upload-icon" style="color: #ef4444; font-size: 3.5rem;"></i>
        <h3 style="margin: 12px 0 8px;">${file.name}</h3>
        <p style="color: #64748b; font-size: 0.95rem;">
            ${(file.size / (1024 * 1024)).toFixed(2)} MB • PDF
        </p>
        <button type="button" class="remove-btn" id="removeBtn">
            <i class="fas fa-times"></i> Remove
        </button>
    `;

    document.getElementById("removeBtn").addEventListener("click", (e) => {
        e.stopPropagation();
        resetUploadArea();
    });
}

// Reset upload area
function resetUploadArea() {

    selectedFile = null;

    uploadArea.innerHTML = `
        <i class="fas fa-cloud-upload-alt upload-icon"></i>
        <h3>Upload Research Paper</h3>
        <p class="upload-text">PDF format • Max 50MB recommended</p>
        
        <input type="file" id="file" name="file" accept=".pdf" required>
        
        <button type="button" class="browse-btn" id="browseBtn">
            Browse Files
        </button>
    `;

    const newFileInput = document.getElementById("file");
    const newBrowseBtn = document.getElementById("browseBtn");

    newBrowseBtn.addEventListener("click", () => newFileInput.click());

    uploadArea.addEventListener("click", (e) => {
        if (e.target !== newBrowseBtn) newFileInput.click();
    });

    attachDragAndDrop();
}

// Drag & Drop
function attachDragAndDrop() {

    uploadArea.addEventListener("dragover", (e) => {
        e.preventDefault();
        uploadArea.style.borderColor = "#6366f1";
        uploadArea.style.background = "#f0f9ff";
    });

    uploadArea.addEventListener("dragleave", () => {
        uploadArea.style.borderColor = "#cbd5e1";
        uploadArea.style.background = "#f8fafc";
    });

    uploadArea.addEventListener("drop", (e) => {

        e.preventDefault();

        uploadArea.style.borderColor = "#cbd5e1";
        uploadArea.style.background = "#f8fafc";

        const file = e.dataTransfer.files[0];

        if (file && file.type === "application/pdf") {

            showFilePreview(file);

            const dataTransfer = new DataTransfer();
            dataTransfer.items.add(file);
            fileInput.files = dataTransfer.files;

        } else {
            alert("Please upload a PDF file only.");
        }

    });

}

// Initial setup
browseBtn.addEventListener("click", () => fileInput.click());

uploadArea.addEventListener("click", (e) => {
    if (!selectedFile && e.target !== browseBtn) {
        fileInput.click();
    }
});

fileInput.addEventListener("change", () => {
    const file = fileInput.files[0];
    if (file) showFilePreview(file);
});

attachDragAndDrop();

// ============================
// Submit Form
// ============================

form.addEventListener("submit", async (e) => {

    e.preventDefault();

    const file = fileInput.files[0];

    if (!file) {
        alert("Please select a PDF file first.");
        return;
    }

    const formData = new FormData();
    formData.append("file", file);
    formData.append("length", lengthSelect.value);

    btn.disabled = true;
    loader.style.display = "flex";

    progressBox.classList.remove("hidden");
    outputCard.classList.add("hidden");

    downloadBtn.classList.add("hidden");

    chatBox.classList.add("hidden"); // hide chat initially

    output.innerHTML = "";

    progressBar.style.width = "0%";
    progressText.innerText = "0%";

    try {

        const res = await fetch("/summarize", {
            method: "POST",
            body: formData
        });

        const data = await res.json();
        currentJobId = data.job_id;

        const interval = setInterval(async () => {

            try {

                const res = await fetch(`/progress/${currentJobId}`);
                const data = await res.json();

                const percent = Math.floor(data.progress || 0);

                progressBar.style.width = percent + "%";
                progressText.innerText = percent + "%";

                if (percent < 40) statusText.innerText = "Reading document...";
                else if (percent < 85) statusText.innerText = "Summarizing chunks...";
                else if (percent < 100) statusText.innerText = "Finalizing summary...";

                if (data.summary) {

                    clearInterval(interval);

                    finalSummary = data.summary;

                    progressBar.style.width = "100%";
                    progressText.innerText = "100%";

                    loader.style.display = "none";

                    outputCard.classList.remove("hidden");

                    output.innerHTML = marked.parse(finalSummary);

                    downloadBtn.classList.remove("hidden");

                    chatBox.classList.remove("hidden"); // 🔥 SHOW CHAT

                    btn.disabled = false;

                }

            } catch (err) {

                clearInterval(interval);

                output.innerHTML = "<p style='color:red;'>Something went wrong.</p>";

                loader.style.display = "none";
                btn.disabled = false;

            }

        }, 2500);

    } catch (err) {

        alert("Error connecting to server.");

        btn.disabled = false;
        loader.style.display = "none";

    }

});

// ============================
// Download Summary
// ============================

downloadBtn.addEventListener("click", () => {

    if (!finalSummary) return;

    const blob = new Blob([finalSummary], { type: "text/plain" });

    const url = window.URL.createObjectURL(blob);

    const a = document.createElement("a");

    a.href = url;
    a.download = "research_summary.txt";

    document.body.appendChild(a);
    a.click();

    document.body.removeChild(a);

    window.URL.revokeObjectURL(url);

});

// ============================
// Chat With PDF
// ============================

chatBtn.addEventListener("click", async () => {

    const question = chatInput.value.trim();

    if (!question) return;

    const userBubble = document.createElement("div");
    userBubble.className = "chat-bubble user";
    userBubble.innerText = question;

    chatMessages.appendChild(userBubble);

    chatInput.value = "";

    const res = await fetch(`/chat/${currentJobId}`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ question })
    });

    const data = await res.json();

    const botBubble = document.createElement("div");
    botBubble.className = "chat-bubble bot";
    botBubble.innerText = data.answer;

    chatMessages.appendChild(botBubble);

    chatMessages.scrollTop = chatMessages.scrollHeight;

});