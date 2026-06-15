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

function selectedFilesIncludeUnsupported(form) {
  const fileInput = form.querySelector("input[type='file'][name='source_files']");

  if (!fileInput) {
    return false;
  }

  const allowedExtensions = [".txt", ".md", ".csv"];

  return Array.from(fileInput.files || []).some((file) => {
    const lowerName = file.name.toLowerCase();
    return !allowedExtensions.some((extension) => lowerName.endsWith(extension));
  });
}

function wireFormGuardrails() {
  document.querySelectorAll("form").forEach((form) => {
    form.addEventListener("submit", (event) => {
      const confirmationMessage = form.dataset.confirm;

      if (confirmationMessage && !window.confirm(confirmationMessage)) {
        event.preventDefault();
        return;
      }

      if (selectedFilesIncludeUnsupported(form)) {
        const proceed = window.confirm("Some selected files are unsupported and will be skipped. Continue with the supported files?");

        if (!proceed) {
          event.preventDefault();
          return;
        }
      }

      const submitter = event.submitter || form.querySelector("button[type='submit']");

      if (submitter) {
        submitter.disabled = true;
        submitter.dataset.originalText = submitter.textContent;
        submitter.textContent = "Working...";
      }
    });
  });
}

function wirePromptChips() {
  document.querySelectorAll("[data-question]").forEach((button) => {
    button.addEventListener("click", () => {
      const questionInput = document.querySelector("input[name='question']");

      if (!questionInput) {
        return;
      }

      questionInput.value = button.dataset.question || "";
      questionInput.focus();

      if (button.dataset.submitQuestion === "true") {
        const askForm = button.closest("form") || document.querySelector("[data-ask-form]");

        if (askForm) {
          askForm.requestSubmit();
        }
      }
    });
  });
}

function wireVaultEditToggles() {
  document.querySelectorAll("[data-toggle-edit]").forEach((button) => {
    button.addEventListener("click", () => {
      const row = button.closest(".vault-row");
      const editPanel = row ? row.querySelector(".vault-edit-panel") : null;

      if (!editPanel) {
        return;
      }

      const isOpening = editPanel.hasAttribute("hidden");
      editPanel.toggleAttribute("hidden");
      button.textContent = isOpening ? "Close" : "Edit";
    });
  });
}

document.addEventListener("DOMContentLoaded", () => {
  const fileInput = document.querySelector("input[type='file'][name='source_files']");

  if (fileInput) {
    fileInput.addEventListener("change", () => renderUploadSummary(fileInput));
  }

  wireFormGuardrails();
  wirePromptChips();
  wireVaultEditToggles();
});
