(function () {
  function parseJsonScript(id, fallback) {
    const element = document.getElementById(id);
    if (!element) {
      return fallback;
    }
    try {
      return JSON.parse(element.textContent);
    } catch (_error) {
      return fallback;
    }
  }

  function setOptions(select, options, selectedValue) {
    if (!select) {
      return;
    }
    const previous = selectedValue || select.value || "";
    select.innerHTML = "";
    const emptyOption = document.createElement("option");
    emptyOption.value = "";
    emptyOption.textContent = "--";
    select.appendChild(emptyOption);
    const optionValues = Array.isArray(options) ? options.slice() : [];
    if (previous && !optionValues.includes(previous)) {
      optionValues.push(previous);
    }
    optionValues.forEach((value) => {
      const option = document.createElement("option");
      option.value = String(value);
      option.textContent = String(value);
      if (String(value) === String(previous)) {
        option.selected = true;
      }
      select.appendChild(option);
    });
  }

  function updateCellRef(row) {
    if (!row) {
      return;
    }
    const columnSelect = row.querySelector(".mapping-column");
    const rowSelect = row.querySelector(".mapping-row-number");
    const cellRefInput = row.querySelector(".mapping-cell-ref");
    if (!columnSelect || !rowSelect || !cellRefInput) {
      return;
    }
    const columnValue = (columnSelect.value || "").trim();
    const rowValue = (rowSelect.value || "").trim();
    cellRefInput.value = columnValue && rowValue ? `${columnValue}${rowValue}` : "";
  }

  function configureRow(row, workbookMeta) {
    const worksheetSelect = row.querySelector(".mapping-worksheet");
    const columnSelect = row.querySelector(".mapping-column");
    const rowSelect = row.querySelector(".mapping-row-number");
    const removeButton = row.querySelector(".remove-mapping-row");
    if (!worksheetSelect || !columnSelect || !rowSelect) {
      return;
    }

    const worksheetNames = workbookMeta.worksheetNames;
    const columnsByWorksheet = workbookMeta.columnsByWorksheet;
    const rowsByWorksheet = workbookMeta.rowsByWorksheet;

    const selectedWorksheet = worksheetSelect.dataset.selected || worksheetSelect.value || worksheetNames[0] || "";
    setOptions(worksheetSelect, worksheetNames, selectedWorksheet);

    function updateWorksheetLinkedFields() {
      const worksheetName = worksheetSelect.value || worksheetNames[0] || "";
      const columnSelected = columnSelect.dataset.selected || columnSelect.value || "";
      const rowSelected = rowSelect.dataset.selected || rowSelect.value || "";
      setOptions(columnSelect, columnsByWorksheet[worksheetName] || [], columnSelected);
      setOptions(rowSelect, rowsByWorksheet[worksheetName] || [], rowSelected);
      columnSelect.dataset.selected = "";
      rowSelect.dataset.selected = "";
      updateCellRef(row);
    }

    worksheetSelect.addEventListener("change", function () {
      columnSelect.dataset.selected = "";
      rowSelect.dataset.selected = "";
      updateWorksheetLinkedFields();
    });
    columnSelect.addEventListener("change", function () {
      updateCellRef(row);
    });
    rowSelect.addEventListener("change", function () {
      updateCellRef(row);
    });

    if (removeButton) {
      removeButton.addEventListener("click", function () {
        const tbody = row.parentElement;
        if (!tbody) {
          return;
        }
        row.remove();
        refreshIndexes(tbody);
      });
    }

    updateWorksheetLinkedFields();
  }

  function refreshIndexes(tbody) {
    Array.from(tbody.querySelectorAll("tr.mapping-row")).forEach((row, index) => {
      const indexCell = row.querySelector(".mapping-index");
      if (indexCell) {
        indexCell.textContent = String(index + 1);
      }
      const sequenceInput = row.querySelector("input[name='mapping_sequence']");
      if (sequenceInput && (!sequenceInput.value || Number(sequenceInput.value) <= 0)) {
        sequenceInput.value = String(index + 1);
      }
    });
  }

  function createEmptyRow(workbookMeta) {
    const worksheetName = workbookMeta.worksheetNames[0] || "";
    const row = document.createElement("tr");
    row.className = "mapping-row";

    const worksheetSelect = buildSelect(
      "mapping_worksheet",
      "form-select form-select-sm mapping-worksheet",
    );
    worksheetSelect.dataset.selected = worksheetName;

    const columnSelect = buildSelect(
      "mapping_column",
      "form-select form-select-sm mapping-column",
    );
    const rowSelect = buildSelect(
      "mapping_row",
      "form-select form-select-sm mapping-row-number",
    );

    const cellRefInput = document.createElement("input");
    cellRefInput.type = "text";
    cellRefInput.className = "form-control form-control-sm mapping-cell-ref";
    cellRefInput.value = "";
    cellRefInput.readOnly = true;

    const requiredSelect = buildSelect("mapping_required", "form-select form-select-sm");
    requiredSelect.appendChild(buildOption("0", "non", true));
    requiredSelect.appendChild(buildOption("1", "oui"));

    const sequenceInput = document.createElement("input");
    sequenceInput.type = "number";
    sequenceInput.name = "mapping_sequence";
    sequenceInput.className = "form-control form-control-sm";
    sequenceInput.value = "";
    sequenceInput.min = "1";
    sequenceInput.step = "1";

    const mergedRange = document.createElement("span");
    mergedRange.className = "small text-muted mapping-merged-range";
    mergedRange.textContent = "-";

    const removeButton = document.createElement("button");
    removeButton.type = "button";
    removeButton.className = "btn btn-outline-danger btn-sm remove-mapping-row";
    removeButton.textContent = "Supprimer";

    appendCell(row, null, "mapping-index");
    appendCell(row, worksheetSelect);
    appendCell(row, columnSelect);
    appendCell(row, rowSelect);
    appendCell(row, cellRefInput);
    appendCell(row, buildSourceSelectElement());
    appendCell(row, buildTransformSelectElement());
    appendCell(row, requiredSelect);
    appendCell(row, sequenceInput);
    appendCell(row, mergedRange);
    appendCell(row, removeButton);
    return row;
  }

  function appendCell(row, child, className) {
    const cell = document.createElement("td");
    if (className) {
      cell.className = className;
    }
    if (child) {
      cell.appendChild(child);
    }
    row.appendChild(cell);
    return cell;
  }

  function buildSelect(name, className) {
    const select = document.createElement("select");
    select.name = name;
    select.className = className;
    return select;
  }

  function buildOption(value, text, selected) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = text;
    option.selected = Boolean(selected);
    return option;
  }

  function buildSourceSelectElement() {
    const firstSourceSelect = document.querySelector("#mapping-rows select[name='mapping_source_key']");
    if (!firstSourceSelect) {
      const select = buildSelect("mapping_source_key", "form-select form-select-sm");
      select.appendChild(buildOption("", "-- Choisir --"));
      return select;
    }
    const clone = firstSourceSelect.cloneNode(true);
    clone.value = "";
    return clone;
  }

  function buildTransformSelectElement() {
    const firstTransformSelect = document.querySelector("#mapping-rows select[name='mapping_transform']");
    if (!firstTransformSelect) {
      const select = buildSelect("mapping_transform", "form-select form-select-sm");
      select.appendChild(buildOption("", "none", true));
      select.appendChild(buildOption("upper", "upper"));
      select.appendChild(buildOption("date_fr", "date_fr"));
      return select;
    }
    const clone = firstTransformSelect.cloneNode(true);
    clone.value = "";
    return clone;
  }

  function init() {
    const tbody = document.getElementById("mapping-rows");
    if (!tbody) {
      return;
    }
    const workbookMeta = {
      worksheetNames: parseJsonScript("mapping-worksheet-names", []),
      columnsByWorksheet: parseJsonScript("mapping-columns-by-worksheet", {}),
      rowsByWorksheet: parseJsonScript("mapping-rows-by-worksheet", {}),
    };
    Array.from(tbody.querySelectorAll("tr.mapping-row")).forEach((row) => {
      configureRow(row, workbookMeta);
    });
    refreshIndexes(tbody);

    const addRowButton = document.getElementById("add-mapping-row");
    if (!addRowButton) {
      return;
    }
    addRowButton.addEventListener("click", function () {
      const row = createEmptyRow(workbookMeta);
      tbody.appendChild(row);
      configureRow(row, workbookMeta);
      refreshIndexes(tbody);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
