function formatBytes(size) {
  if (size >= 1024 * 1024) {
    return `${(size / (1024 * 1024)).toFixed(1)} MB`;
  }

  if (size >= 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }

  return `${size} B`;
}

function renderUploadSummary(input) {
  const summary = document.querySelector("[data-upload-summary]");

  if (!summary) {
    return;
  }

  const files = Array.from(input.files || []);

  if (!files.length) {
    summary.innerHTML = "<strong>No files selected yet</strong><span>Choose files to preview names, sizes, and accepted formats before extraction.</span>";
    return;
  }

  const allowedExtensions = [".txt", ".md", ".csv"];
  const totalSize = files.reduce((sum, file) => sum + file.size, 0);
  const items = files.map((file) => {
    const lowerName = file.name.toLowerCase();
    const accepted = allowedExtensions.some((extension) => lowerName.endsWith(extension));
    const className = accepted ? "" : " class=\"rejected\"";
    const status = accepted ? "ready" : "unsupported type";

    return `<li${className}>${file.name} · ${formatBytes(file.size)} · ${status}</li>`;
  }).join("");

  summary.innerHTML = `<strong>${files.length} file(s) selected · ${formatBytes(totalSize)} total</strong><ul>${items}</ul>`;
}

document.addEventListener("DOMContentLoaded", () => {
  const fileInput = document.querySelector("input[type='file'][name='source_files']");

  if (fileInput) {
    fileInput.addEventListener("change", () => renderUploadSummary(fileInput));
  }

  document.querySelectorAll("[data-question]").forEach((button) => {
    button.addEventListener("click", () => {
      const questionInput = document.querySelector("input[name='question']");

      if (questionInput) {
        questionInput.value = button.dataset.question || "";
        questionInput.focus();
      }
    });
  });
});
