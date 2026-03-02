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
    row.innerHTML = `
      <td class="mapping-index"></td>
      <td><select name="mapping_worksheet" class="form-select form-select-sm mapping-worksheet" data-selected="${worksheetName}"></select></td>
      <td><select name="mapping_column" class="form-select form-select-sm mapping-column" data-selected=""></select></td>
      <td><select name="mapping_row" class="form-select form-select-sm mapping-row-number" data-selected=""></select></td>
      <td><input type="text" class="form-control form-control-sm mapping-cell-ref" value="" readonly></td>
      <td>${buildSourceSelectHtml()}</td>
      <td>${buildTransformSelectHtml()}</td>
      <td>
        <select name="mapping_required" class="form-select form-select-sm">
          <option value="0" selected>non</option>
          <option value="1">oui</option>
        </select>
      </td>
      <td><input type="number" name="mapping_sequence" class="form-control form-control-sm" value="" min="1" step="1"></td>
      <td><span class="small text-muted mapping-merged-range">-</span></td>
      <td><button type="button" class="btn btn-outline-danger btn-sm remove-mapping-row">Supprimer</button></td>
    `;
    return row;
  }

  function buildSourceSelectHtml() {
    const firstSourceSelect = document.querySelector("#mapping-rows select[name='mapping_source_key']");
    if (!firstSourceSelect) {
      return '<select name="mapping_source_key" class="form-select form-select-sm"><option value="">-- Choisir --</option></select>';
    }
    const clone = firstSourceSelect.cloneNode(true);
    clone.value = "";
    return clone.outerHTML;
  }

  function buildTransformSelectHtml() {
    const firstTransformSelect = document.querySelector("#mapping-rows select[name='mapping_transform']");
    if (!firstTransformSelect) {
      return '<select name="mapping_transform" class="form-select form-select-sm"><option value="" selected>none</option><option value="upper">upper</option><option value="date_fr">date_fr</option></select>';
    }
    const clone = firstTransformSelect.cloneNode(true);
    clone.value = "";
    return clone.outerHTML;
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
