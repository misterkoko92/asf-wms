(function() {
  const tableToolsCore = window.WmsTableToolsCore;
  if (!tableToolsCore) {
    return;
  }
  const { cleanText, normalizeText, compareCellValues, extractCellText } = tableToolsCore;

  function setupTableTools() {
    const tables = Array.from(document.querySelectorAll('table[data-table-tools="1"]'));
    if (!tables.length) {
      return;
    }

    tables.forEach(table => {
      const thead = table.tHead;
      const tbody = table.tBodies && table.tBodies[0];
      if (!thead || !tbody || !thead.rows.length) {
        return;
      }

      const headerRow = thead.rows[0];
      const headerCells = Array.from(headerRow.cells).filter(
        cell => cell.tagName && cell.tagName.toUpperCase() === 'TH'
      );
      if (!headerCells.length) {
        return;
      }

      const rows = Array.from(tbody.rows).map((row, index) => ({
        row,
        originalIndex: index
      }));
      let sortColumn = -1;
      let sortDirection = 0;
      const filterInputs = [];

      const getRowValue = (entry, columnIndex) =>
        extractCellText(entry.row.cells[columnIndex]);

      const updateHeaderState = () => {
        headerCells.forEach((cell, index) => {
          const isSorted = index === sortColumn && sortDirection !== 0;
          cell.classList.toggle('scan-table-sortable', true);
          cell.classList.toggle('is-sorted', isSorted);
          cell.classList.toggle('is-desc', isSorted && sortDirection < 0);
          cell.setAttribute('aria-sort', !isSorted ? 'none' : (sortDirection > 0 ? 'ascending' : 'descending'));
        });
      };

      const applyTools = () => {
        const orderedRows = rows.slice();
        if (sortColumn >= 0 && sortDirection !== 0) {
          orderedRows.sort((left, right) => {
            const compareResult = compareCellValues(
              getRowValue(left, sortColumn),
              getRowValue(right, sortColumn)
            );
            if (compareResult === 0) {
              return left.originalIndex - right.originalIndex;
            }
            return compareResult * sortDirection;
          });
        } else {
          orderedRows.sort((left, right) => left.originalIndex - right.originalIndex);
        }

        orderedRows.forEach(entry => {
          tbody.appendChild(entry.row);
        });

        const filters = filterInputs.map(input => normalizeText(input.value));
        orderedRows.forEach(entry => {
          const keep = filters.every((term, columnIndex) => {
            if (!term) {
              return true;
            }
            return normalizeText(getRowValue(entry, columnIndex)).includes(term);
          });
          entry.row.style.display = keep ? '' : 'none';
        });

        updateHeaderState();
      };

      headerCells.forEach((cell, index) => {
        cell.classList.add('scan-table-sortable');
        cell.setAttribute('role', 'button');
        cell.setAttribute('tabindex', '0');
        cell.setAttribute('aria-sort', 'none');
        const onSort = event => {
          if (
            event.target &&
            event.target.closest('a, button, input, select, textarea, form, label')
          ) {
            return;
          }
          if (sortColumn !== index) {
            sortColumn = index;
            sortDirection = 1;
          } else if (sortDirection === 1) {
            sortDirection = -1;
          } else if (sortDirection === -1) {
            sortDirection = 0;
            sortColumn = -1;
          } else {
            sortDirection = 1;
          }
          applyTools();
        };
        cell.addEventListener('click', onSort);
        cell.addEventListener('keydown', event => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            onSort(event);
          }
        });
      });

      const filterRow = document.createElement('tr');
      filterRow.className = 'scan-table-filter-row';
      headerCells.forEach(cell => {
        const filterCell = document.createElement('th');
        const input = document.createElement('input');
        input.type = 'search';
        input.className = 'scan-table-filter-input';
        input.placeholder = 'Filtrer';
        input.autocomplete = 'off';
        input.setAttribute('aria-label', 'Filtrer ' + (cleanText(cell.textContent) || 'colonne'));
        input.addEventListener('input', applyTools);
        filterInputs.push(input);
        filterCell.appendChild(input);
        filterRow.appendChild(filterCell);
      });
      thead.appendChild(filterRow);

      applyTools();
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupTableTools);
  } else {
    setupTableTools();
  }
})();
