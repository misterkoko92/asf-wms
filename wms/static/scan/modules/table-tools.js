(function(window) {
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

    return cleanText([...textParts, ...selectedValues, ...typedValues].join(' '));
  }

  window.WmsTableToolsCore = {
    cleanText,
    compareCellValues,
    extractCellText,
    normalizeText
  };
})(window);
