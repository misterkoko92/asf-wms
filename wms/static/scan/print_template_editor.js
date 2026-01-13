(function () {
  const layoutNode = document.getElementById("layout-data");
  const blockLibraryNode = document.getElementById("block-library-data");
  const docTypeNode = document.getElementById("doc-type-data");

  if (!layoutNode || !blockLibraryNode || !docTypeNode) {
    return;
  }

  const layoutData = JSON.parse(layoutNode.textContent || "{}");
  const blockLibrary = JSON.parse(blockLibraryNode.textContent || "{}");
  const docType = JSON.parse(docTypeNode.textContent || "\"\"");

  let blocks = Array.isArray(layoutData.blocks) ? layoutData.blocks.slice() : [];
  let selectedIndex = null;
  let previewTimer = null;

  const editorRoot = document.getElementById("template-editor");
  const blockList = document.getElementById("block-list");
  const blockLibraryEl = document.getElementById("block-library");
  const blockEditor = document.getElementById("block-editor");
  const previewFrame = document.getElementById("template-preview");
  const previewStatus = document.getElementById("preview-status");
  const previewSelect =
    document.getElementById("preview-shipment") ||
    document.getElementById("preview-product");
  const previewButton = document.getElementById("preview-layout");
  const resetButton = document.getElementById("reset-layout");
  const form = document.getElementById("template-form");
  const layoutInput = document.getElementById("layout-json");
  const actionInput = document.getElementById("layout-action");
  const csrfToken = form.querySelector("input[name=csrfmiddlewaretoken]").value;
  const previewUrl = editorRoot.dataset.previewUrl;

  function deepClone(value) {
    return JSON.parse(JSON.stringify(value || {}));
  }

  function normalizeBlocks() {
    if (!Array.isArray(blocks)) {
      blocks = [];
    }
  }

  function getBlockLabel(block) {
    const info = blockLibrary[block.type] || {};
    const baseLabel = info.label || block.type;
    if (block.type === "text" && block.text) {
      const preview = block.text.replace(/<[^>]+>/g, "").slice(0, 40);
      return preview ? `${baseLabel}: ${preview}` : baseLabel;
    }
    return baseLabel;
  }

  function setNestedValue(obj, path, value) {
    const parts = path.split(".");
    let current = obj;
    for (let i = 0; i < parts.length - 1; i += 1) {
      const key = parts[i];
      if (!current[key] || typeof current[key] !== "object") {
        current[key] = {};
      }
      current = current[key];
    }
    current[parts[parts.length - 1]] = value;
  }

  function getNestedValue(obj, path) {
    const parts = path.split(".");
    let current = obj;
    for (let i = 0; i < parts.length; i += 1) {
      if (!current) {
        return "";
      }
      current = current[parts[i]];
    }
    return current == null ? "" : current;
  }

  function renderBlockLibrary() {
    blockLibraryEl.innerHTML = "";
    Object.entries(blockLibrary).forEach(([type, info]) => {
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.blockType = type;
      button.textContent = info.label || type;
      button.addEventListener("click", () => addBlock(type));
      blockLibraryEl.appendChild(button);
    });
  }

  function addBlock(type) {
    const block = {
      id: `block-${Date.now()}-${Math.random().toString(16).slice(2)}`,
      type,
    };
    const info = blockLibrary[type] || {};
    if (info.defaults) {
      Object.assign(block, deepClone(info.defaults));
    }
    if (type === "text") {
      block.text = block.text || "Nouveau bloc";
      block.tag = block.tag || "div";
      block.style = block.style || {};
    }
    if (type === "table_items") {
      block.mode = block.mode || "carton";
    }
    blocks.push(block);
    selectedIndex = blocks.length - 1;
    renderBlocks();
    schedulePreview();
  }

  function removeBlock(index) {
    const confirmRemove = window.confirm("Supprimer ce bloc ?");
    if (!confirmRemove) {
      return;
    }
    blocks.splice(index, 1);
    if (selectedIndex === index) {
      selectedIndex = null;
    } else if (selectedIndex > index) {
      selectedIndex -= 1;
    }
    renderBlocks();
    schedulePreview();
  }

  function moveBlock(from, to) {
    if (from === to) {
      return;
    }
    const [moved] = blocks.splice(from, 1);
    blocks.splice(to, 0, moved);
    selectedIndex = to;
  }

  function renderBlocks() {
    normalizeBlocks();
    blockList.innerHTML = "";
    blocks.forEach((block, index) => {
      const item = document.createElement("li");
      item.className = "template-block-item";
      if (index === selectedIndex) {
        item.classList.add("selected");
      }
      item.setAttribute("draggable", "true");

      item.addEventListener("dragstart", (event) => {
        event.dataTransfer.setData("text/plain", String(index));
      });
      item.addEventListener("dragover", (event) => {
        event.preventDefault();
      });
      item.addEventListener("drop", (event) => {
        event.preventDefault();
        const fromIndex = Number(event.dataTransfer.getData("text/plain"));
        if (Number.isNaN(fromIndex)) {
          return;
        }
        moveBlock(fromIndex, index);
        renderBlocks();
        schedulePreview();
      });

      item.addEventListener("click", () => {
        selectedIndex = index;
        renderBlocks();
      });

      const handle = document.createElement("span");
      handle.className = "template-block-handle";
      handle.textContent = "≡";

      const label = document.createElement("div");
      label.innerHTML = `<span class="template-block-title">${getBlockLabel(block)}</span>`;

      const actions = document.createElement("div");
      actions.className = "template-block-actions";
      const removeButton = document.createElement("button");
      removeButton.type = "button";
      removeButton.className = "template-block-remove";
      removeButton.textContent = "Supprimer";
      removeButton.addEventListener("click", (event) => {
        event.stopPropagation();
        removeBlock(index);
      });
      actions.appendChild(removeButton);

      item.appendChild(handle);
      item.appendChild(label);
      item.appendChild(actions);
      blockList.appendChild(item);
    });
    renderEditor();
  }

  function renderEditor() {
    blockEditor.innerHTML = "";
    if (selectedIndex == null || !blocks[selectedIndex]) {
      blockEditor.innerHTML =
        '<p class="template-muted">Selectionnez un bloc pour le modifier.</p>';
      return;
    }
    const block = blocks[selectedIndex];
    const info = blockLibrary[block.type] || {};
    const fields = info.fields || [];

    if (!fields.length) {
      blockEditor.innerHTML =
        '<p class="template-muted">Aucune option disponible pour ce bloc.</p>';
      return;
    }

    fields.forEach((field) => {
      const fieldWrap = document.createElement("div");
      fieldWrap.className = "template-field";
      const label = document.createElement("label");
      label.textContent = field.label || field.name;
      const inputName = `field-${field.name}`;

      label.setAttribute("for", inputName);
      fieldWrap.appendChild(label);

      let input;
      if (field.type === "textarea") {
        input = document.createElement("textarea");
        input.value = getNestedValue(block, field.name);
      } else if (field.type === "select") {
        input = document.createElement("select");
        (field.options || []).forEach((option) => {
          const optionEl = document.createElement("option");
          optionEl.value = option;
          optionEl.textContent = option;
          if (String(option) === String(getNestedValue(block, field.name))) {
            optionEl.selected = true;
          }
          input.appendChild(optionEl);
        });
      } else if (field.type === "checkbox") {
        input = document.createElement("input");
        input.type = "checkbox";
        input.checked = Boolean(getNestedValue(block, field.name));
      } else {
        input = document.createElement("input");
        input.type = "text";
        input.value = getNestedValue(block, field.name);
      }

      input.id = inputName;
      input.addEventListener("input", () => {
        const value =
          field.type === "checkbox" ? input.checked : input.value;
        setNestedValue(block, field.name, value);
        schedulePreview();
      });
      input.addEventListener("change", () => {
        renderBlocks();
      });

      fieldWrap.appendChild(input);
      blockEditor.appendChild(fieldWrap);
    });
  }

  function schedulePreview() {
    if (previewTimer) {
      clearTimeout(previewTimer);
    }
    previewTimer = setTimeout(refreshPreview, 400);
  }

  async function refreshPreview() {
    if (!previewUrl) {
      return;
    }
    const payload = new FormData();
    payload.append("doc_type", docType);
    payload.append("layout_json", JSON.stringify({ blocks }));
    if (previewSelect && previewSelect.value) {
      if (docType === "product_label" || docType === "product_qr") {
        payload.append("product_id", previewSelect.value);
      } else {
        payload.append("shipment_id", previewSelect.value);
      }
    }

    previewStatus.textContent = "Chargement...";
    try {
      const response = await fetch(previewUrl, {
        method: "POST",
        headers: {
          "X-CSRFToken": csrfToken,
        },
        body: payload,
      });
      if (!response.ok) {
        previewStatus.textContent = "Erreur d'apercu.";
        return;
      }
      const html = await response.text();
      previewFrame.srcdoc = html;
      previewStatus.textContent = "";
    } catch (error) {
      previewStatus.textContent = "Erreur d'apercu.";
    }
  }

  form.addEventListener("submit", () => {
    if (!actionInput.value) {
      actionInput.value = "save";
    }
    layoutInput.value = JSON.stringify({ blocks });
  });

  resetButton.addEventListener("click", () => {
    const confirmReset = window.confirm(
      "Remettre ce template par defaut ?"
    );
    if (!confirmReset) {
      return;
    }
    actionInput.value = "reset";
    form.submit();
  });

  if (previewButton) {
    previewButton.addEventListener("click", refreshPreview);
  }

  if (previewSelect) {
    previewSelect.addEventListener("change", refreshPreview);
  }

  renderBlockLibrary();
  renderBlocks();
  refreshPreview();
})();
