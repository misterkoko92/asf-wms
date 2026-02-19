(function() {
  function cleanText(value) {
    return (value || '')
      .toString()
      .replace(/\s+/g, ' ')
      .trim();
  }

  function normalizeText(value) {
    const input = cleanText(value);
    if (!input) {
      return '';
    }
    if (typeof input.normalize === 'function') {
      return input
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .toLowerCase();
    }
    return input.toLowerCase();
  }

  function parseDateValue(value) {
    const text = cleanText(value);
    if (!text) {
      return null;
    }
    const match = text.match(
      /^(\d{1,2})\/(\d{1,2})\/(\d{2,4})(?:\s+(\d{1,2})h(\d{1,2}))?$/
    );
    if (!match) {
      return null;
    }
    let year = parseInt(match[3], 10);
    if (year < 100) {
      year += 2000;
    }
    const month = parseInt(match[2], 10) - 1;
    const day = parseInt(match[1], 10);
    const hour = match[4] ? parseInt(match[4], 10) : 0;
    const minute = match[5] ? parseInt(match[5], 10) : 0;
    const stamp = new Date(year, month, day, hour, minute).getTime();
    return Number.isFinite(stamp) ? stamp : null;
  }

  function parseNumericValue(value) {
    const text = cleanText(value);
    if (!text) {
      return null;
    }
    const normalized = text
      .replace(/\s/g, '')
      .replace(',', '.')
      .replace(/[^0-9.+-]/g, '');
    if (!normalized || ['-', '+', '.', '-.', '+.'].includes(normalized)) {
      return null;
    }
    const parsed = Number(normalized);
    return Number.isFinite(parsed) ? parsed : null;
  }

  function compareCellValues(leftValue, rightValue) {
    const leftDate = parseDateValue(leftValue);
    const rightDate = parseDateValue(rightValue);
    if (leftDate !== null && rightDate !== null) {
      return leftDate - rightDate;
    }

    const leftNumber = parseNumericValue(leftValue);
    const rightNumber = parseNumericValue(rightValue);
    if (leftNumber !== null && rightNumber !== null) {
      return leftNumber - rightNumber;
    }

    return String(leftValue || '').localeCompare(String(rightValue || ''), 'fr', {
      sensitivity: 'base',
      numeric: true
    });
  }

  function extractCellText(cell) {
    if (!cell) {
      return '';
    }

    const selectedValues = Array.from(cell.querySelectorAll('select'))
      .map(select => {
        const option = select.selectedOptions && select.selectedOptions[0];
        return option ? cleanText(option.textContent) : '';
      })
      .filter(Boolean);

    const typedValues = Array.from(cell.querySelectorAll('input, textarea'))
      .filter(field => {
        if (!field || !field.tagName) {
          return false;
        }
        if (field.tagName.toLowerCase() === 'textarea') {
          return true;
        }
        const type = String(field.type || '').toLowerCase();
        return ![
          'hidden',
          'password',
          'file',
          'checkbox',
          'radio',
          'submit',
          'button',
          'reset'
        ].includes(type);
      })
      .map(field => cleanText(field.value))
      .filter(Boolean);

    const textParts = [];
    const walker = document.createTreeWalker(cell, NodeFilter.SHOW_TEXT);
    let node = walker.nextNode();
    while (node) {
      const parentTag = node.parentNode && node.parentNode.tagName
        ? node.parentNode.tagName.toUpperCase()
        : '';
      if (!['OPTION', 'SCRIPT', 'STYLE'].includes(parentTag)) {
        const text = cleanText(node.textContent);
        if (text) {
          textParts.push(text);
        }
      }
      node = walker.nextNode();
    }

    return cleanText([].concat(textParts, selectedValues, typedValues).join(' '));
  }

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
