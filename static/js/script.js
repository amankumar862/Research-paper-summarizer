const form = document.getElementById("form");
const btn = document.getElementById("btn");
const output = document.getElementById("output");
const progressBar = document.getElementById("progressBar");
const progressText = document.getElementById("progressText");
const progressBox = document.getElementById("progressBox");
const loader = document.getElementById("loader");
const downloadBtn = document.getElementById("downloadBtn");
const lengthSelect = document.getElementById("length");

let finalSummary = "";

form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const file = document.getElementById("file").files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);
    formData.append("length", lengthSelect.value);

    btn.disabled = true;
    loader.style.display = "block";
    loader.innerText = "Processing...";

    progressBox.classList.remove("hidden");
    progressText.classList.remove("hidden");
    downloadBtn.classList.add("hidden");

    output.innerHTML = "";
    progressBar.style.width = "0%";
    progressText.innerText = "0%";

    const res = await fetch("/summarize", {
        method: "POST",
        body: formData
    });

    const { job_id } = await res.json();

    const interval = setInterval(async () => {
        try {
            const res = await fetch(`/progress/${job_id}`);
            const data = await res.json();

            const percent = Math.floor(data.progress);

            progressBar.style.width = percent + "%";
            progressText.innerText = percent + "%";

            if (percent < 40) {
                loader.innerText = "Reading document...";
            } else if (percent < 85) {
                loader.innerText = "Summarizing chunks...";
            } else if (percent < 100) {
                loader.innerText = "Finalizing summary...";
            }

            if (data.summary) {
                clearInterval(interval);

                finalSummary = data.summary;

                progressBar.style.width = "100%";
                progressText.innerText = "100%";
                loader.innerText = "Done ✅";

                setTimeout(() => {
                    // Render rich Markdown with beautiful table
                    output.innerHTML = marked.parse(finalSummary);

                    loader.style.display = "none";
                    btn.disabled = false;
                    downloadBtn.classList.remove("hidden");
                }, 800);
            }

        } catch (err) {
            clearInterval(interval);
            output.innerHTML = "<p style='color:red;'>Something went wrong.</p>";
            loader.style.display = "none";
            btn.disabled = false;
        }
    }, 3000);
});

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