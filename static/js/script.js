const form = document.querySelector("form");
const btn = document.getElementById("btn");
const loader = document.getElementById("loader");

form.addEventListener("submit", () => {
    btn.innerText = "Generating...";
    btn.disabled = true;
    loader.style.display = "block";
});