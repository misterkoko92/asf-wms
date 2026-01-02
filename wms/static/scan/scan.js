(() => {
  const overlay = document.getElementById('scan-overlay');
  const video = document.getElementById('scan-video');
  const statusEl = document.getElementById('scan-status');
  const closeBtn = document.getElementById('scan-close');

  let activeInput = null;
  let stream = null;
  let detector = null;
  let zxingReader = null;
  let scanning = false;
  const ZXING_SRC = '/static/scan/zxing.min.js';

  function setupThemeToggle() {
    const toggle = document.getElementById('theme-toggle');
    if (!toggle) {
      return;
    }
    const root = document.documentElement;
    const THEME_KEY = 'scan-theme';
    const normalize = value => (value === 'atelier' ? 'atelier' : 'classic');
    let initialTheme = root.dataset.theme || 'classic';
    try {
      const stored = localStorage.getItem(THEME_KEY);
      if (stored) {
        initialTheme = stored;
      }
    } catch (err) {
      // Ignore storage errors.
    }

    const applyTheme = theme => {
      const normalized = normalize(theme);
      root.dataset.theme = normalized;
      toggle.textContent = normalized === 'atelier' ? 'Atelier' : 'Classique';
      toggle.setAttribute('aria-pressed', normalized === 'atelier' ? 'true' : 'false');
      toggle.title =
        normalized === 'atelier' ? 'Basculer vers Classique' : 'Basculer vers Atelier';
    };

    applyTheme(initialTheme);

    toggle.addEventListener('click', () => {
      const nextTheme = root.dataset.theme === 'atelier' ? 'classic' : 'atelier';
      applyTheme(nextTheme);
      try {
        localStorage.setItem(THEME_KEY, nextTheme);
      } catch (err) {
        // Ignore storage errors.
      }
    });
  }

  function setupUiToggle() {
    const toggle = document.getElementById('ui-toggle');
    if (!toggle) {
      return;
    }
    const root = document.documentElement;
    const UI_KEY = 'wms-ui';
    const UI_OPTIONS = ['classic', 'nova', 'studio'];
    const UI_LABELS = {
      classic: 'Classique',
      nova: 'Nouveau',
      studio: 'Studio'
    };
    const UI_TITLES = {
      classic: 'Basculer vers Nouveau',
      nova: 'Basculer vers Studio',
      studio: 'Basculer vers Classique'
    };
    const normalize = value => (UI_OPTIONS.includes(value) ? value : 'classic');
    let initialUi = root.dataset.ui || 'classic';
    try {
      const stored = localStorage.getItem(UI_KEY);
      if (stored) {
        initialUi = stored;
      }
    } catch (err) {
      // Ignore storage errors.
    }

    const applyUi = ui => {
      const normalized = normalize(ui);
      root.dataset.ui = normalized;
      toggle.textContent = UI_LABELS[normalized] || 'Classique';
      toggle.setAttribute('aria-pressed', normalized === 'classic' ? 'false' : 'true');
      toggle.title = UI_TITLES[normalized] || 'Basculer vers Nouveau';
    };

    applyUi(initialUi);

    toggle.addEventListener('click', () => {
      const current = normalize(root.dataset.ui);
      const currentIndex = UI_OPTIONS.indexOf(current);
      const nextUi = UI_OPTIONS[(currentIndex + 1) % UI_OPTIONS.length];
      applyUi(nextUi);
      try {
        localStorage.setItem(UI_KEY, nextUi);
      } catch (err) {
        // Ignore storage errors.
      }
    });
  }

  function setStatus(text) {
    if (statusEl) {
      statusEl.textContent = text;
    }
  }

  async function stopScan() {
    scanning = false;
    if (zxingReader) {
      try {
        zxingReader.reset();
      } catch (err) {
        // Ignore reset errors.
      }
      zxingReader = null;
    }
    if (stream) {
      stream.getTracks().forEach(track => track.stop());
      stream = null;
    }
    if (video && video.srcObject && !stream) {
      const videoStream = video.srcObject;
      if (videoStream && videoStream.getTracks) {
        videoStream.getTracks().forEach(track => track.stop());
      }
    }
    if (video) {
      video.srcObject = null;
    }
    if (overlay) {
      overlay.classList.remove('active');
    }
  }

  async function detectLoop() {
    if (!scanning || !detector || !video) {
      return;
    }
    try {
      const barcodes = await detector.detect(video);
      if (barcodes.length > 0) {
        const code = barcodes[0].rawValue || '';
        if (activeInput) {
          activeInput.value = code;
          activeInput.dispatchEvent(new Event('input', { bubbles: true }));
        }
        setStatus('Code detecte: ' + code);
        await stopScan();
        return;
      }
    } catch (err) {
      setStatus('Erreur scan: ' + err.message);
    }
    requestAnimationFrame(detectLoop);
  }

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = src;
      script.async = true;
      script.onload = resolve;
      script.onerror = reject;
      document.head.appendChild(script);
    });
  }

  async function ensureZXing() {
    if (window.ZXing && window.ZXing.BrowserMultiFormatReader) {
      return window.ZXing;
    }
    if (window.ZXingBrowser && window.ZXingBrowser.BrowserMultiFormatReader) {
      return window.ZXingBrowser;
    }
    await loadScript(ZXING_SRC);
    return window.ZXing || window.ZXingBrowser;
  }

  function handleDetectedCode(code) {
    if (activeInput) {
      activeInput.value = code;
      activeInput.dispatchEvent(new Event('input', { bubbles: true }));
    }
    setStatus('Code detecte: ' + code);
  }

  async function startZXingScan() {
    let ZXing;
    try {
      setStatus('Chargement du scanner...');
      if (overlay) {
        overlay.classList.add('active');
      }
      ZXing = await ensureZXing();
    } catch (err) {
      setStatus('Chargement du scanner impossible.');
      alert('Impossible de charger le module de scan. Verifiez la connexion.');
      await stopScan();
      return;
    }
    if (!ZXing || !ZXing.BrowserMultiFormatReader) {
      alert('Scan camera non supporte. Utilisez un scanner ou saisissez le code.');
      await stopScan();
      return;
    }
    zxingReader = new ZXing.BrowserMultiFormatReader();
    scanning = true;
    setStatus('Scan en cours...');
    if (overlay) {
      overlay.classList.add('active');
    }
    const callback = (result, err) => {
      if (!scanning) {
        return;
      }
      if (result) {
        const code = result.getText ? result.getText() : result.text || result;
        handleDetectedCode(code || '');
        stopScan();
        return;
      }
      if (err && err.name && err.name !== 'NotFoundException') {
        setStatus('Erreur scan: ' + (err.message || err.name));
      }
    };
    try {
      if (typeof zxingReader.decodeFromConstraints === 'function') {
        await zxingReader.decodeFromConstraints(
          { audio: false, video: { facingMode: { ideal: 'environment' } } },
          video,
          callback
        );
      } else {
        await zxingReader.decodeFromVideoDevice(null, video, callback);
      }
    } catch (err) {
      setStatus('Acces camera refuse.');
      await stopScan();
    }
  }

  async function startScan(input) {
    activeInput = input;
    setStatus('Chargement du scanner...');
    if (overlay) {
      overlay.classList.add('active');
    }
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      alert('Scan camera non supporte. Utilisez un scanner ou saisissez le code.');
      await stopScan();
      return;
    }
    if ('BarcodeDetector' in window) {
      detector = new BarcodeDetector({
        formats: ['qr_code', 'code_128', 'ean_13', 'ean_8', 'code_39', 'upc_a', 'upc_e']
      });
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: 'environment' },
          audio: false
        });
      } catch (err) {
        setStatus('Acces camera refuse.');
        await stopScan();
        return;
      }
      if (video) {
        video.srcObject = stream;
        await video.play();
      }
      scanning = true;
      setStatus('Scan en cours...');
      if (overlay) {
        overlay.classList.add('active');
      }
      requestAnimationFrame(detectLoop);
    } else {
      await startZXingScan();
    }
  }

  function setupProductDatalist() {
    const dataEl = document.getElementById('product-data');
    const datalist = document.getElementById('product-options');
    if (!dataEl || !datalist) {
      return;
    }
    let rawProducts = [];
    try {
      rawProducts = JSON.parse(dataEl.textContent || '[]');
    } catch (err) {
      return;
    }
    if (!Array.isArray(rawProducts) || rawProducts.length === 0) {
      return;
    }
    const products = rawProducts
      .filter(product => product && product.name)
      .map(product => ({
        name: product.name,
        nameLower: product.name.toLowerCase(),
        sku: product.sku || '',
        barcode: product.barcode || '',
        defaultLocationId: product.default_location_id || null,
        storageConditions: product.storage_conditions || ''
      }));
    if (products.length === 0) {
      return;
    }
    const inputs = document.querySelectorAll('input[list="product-options"]');
    if (!inputs.length) {
      return;
    }
    const MAX_OPTIONS = 40;
    const renderOptions = query => {
      const queryLower = (query || '').trim().toLowerCase();
      datalist.innerHTML = '';
      const fragment = document.createDocumentFragment();
      let count = 0;
      for (const product of products) {
        if (queryLower && !product.nameLower.startsWith(queryLower)) {
          continue;
        }
        const option = document.createElement('option');
        option.value = product.name;
        const labelParts = [];
        if (product.sku) {
          labelParts.push(product.sku);
        }
        if (product.barcode) {
          labelParts.push(product.barcode);
        }
        if (labelParts.length) {
          option.label = labelParts.join(' | ');
        }
        fragment.appendChild(option);
        count += 1;
        if (count >= MAX_OPTIONS) {
          break;
        }
      }
      datalist.appendChild(fragment);
    };

    const locationSelect = document.getElementById('id_location');
    const storageInput = document.getElementById('id_storage_conditions');

    const findProductMatch = value => {
      const code = (value || '').trim();
      if (!code) {
        return null;
      }
      const codeLower = code.toLowerCase();
      let match = products.find(product => product.nameLower === codeLower);
      if (match) {
        return match;
      }
      match = products.find(
        product => product.sku && product.sku.toLowerCase() === codeLower
      );
      if (match) {
        return match;
      }
      match = products.find(
        product => product.barcode && product.barcode.toLowerCase() === codeLower
      );
      if (match) {
        return match;
      }
      const prefixMatches = products.filter(product =>
        product.nameLower.startsWith(codeLower)
      );
      if (prefixMatches.length === 1) {
        return prefixMatches[0];
      }
      return null;
    };

    const applyProductDefaults = product => {
      if (!product) {
        return;
      }
      if (locationSelect) {
        locationSelect.value = product.defaultLocationId
          ? String(product.defaultLocationId)
          : '';
      }
      if (storageInput) {
        storageInput.value = product.storageConditions || '';
      }
    };

    const applyDefaultsFromValue = value => {
      applyProductDefaults(findProductMatch(value));
    };

    renderOptions('');
    inputs.forEach(input => {
      applyDefaultsFromValue(input.value);
      input.addEventListener('input', event => {
        applyDefaultsFromValue(event.target.value);
        renderOptions(event.target.value);
      });
      input.addEventListener('focus', event => {
        renderOptions(event.target.value);
      });
      input.addEventListener('change', event => {
        applyDefaultsFromValue(event.target.value);
      });
      input.addEventListener('blur', event => {
        applyDefaultsFromValue(event.target.value);
      });
    });
  }

  function setupPackLines() {
    const container = document.getElementById('pack-lines');
    if (!container) {
      return;
    }
    const addButton = document.getElementById('pack-add-line');
    const lineCountInput = document.getElementById('pack_line_count');
    const formatSelect = document.getElementById('id_carton_format');
    const customFields = document.getElementById('custom-carton-fields');
    const customLength = document.getElementById('id_carton_length_cm');
    const customWidth = document.getElementById('id_carton_width_cm');
    const customHeight = document.getElementById('id_carton_height_cm');
    const customWeight = document.getElementById('id_carton_max_weight_g');

    const productDataEl = document.getElementById('product-data');
    const formatDataEl = document.getElementById('carton-format-data');
    const lineDataEl = document.getElementById('pack-lines-data');
    const lineErrorsEl = document.getElementById('pack-lines-errors');

    let products = [];
    let formats = [];
    let lineValues = [];
    let lineErrors = {};

    try {
      products = JSON.parse(productDataEl ? productDataEl.textContent || '[]' : '[]');
    } catch (err) {
      products = [];
    }
    try {
      formats = JSON.parse(formatDataEl ? formatDataEl.textContent || '[]' : '[]');
    } catch (err) {
      formats = [];
    }
    try {
      lineValues = JSON.parse(lineDataEl ? lineDataEl.textContent || '[]' : '[]');
    } catch (err) {
      lineValues = [];
    }
    try {
      lineErrors = JSON.parse(lineErrorsEl ? lineErrorsEl.textContent || '{}' : '{}');
    } catch (err) {
      lineErrors = {};
    }

    const normalize = value => (value || '').toString().trim().toLowerCase();
    const parseNumber = value => {
      const parsed = parseFloat((value || '').toString().replace(',', '.'));
      return Number.isFinite(parsed) ? parsed : null;
    };

    const productEntries = products
      .filter(product => product && product.name)
      .map(product => ({
        name: product.name,
        nameLower: normalize(product.name),
        sku: product.sku || '',
        skuLower: normalize(product.sku || ''),
        barcode: product.barcode || '',
        barcodeLower: normalize(product.barcode || ''),
        key: normalize(product.sku) || normalize(product.barcode) || normalize(product.name),
        weightG: parseNumber(product.weight_g) || 0,
        availableStock: parseNumber(product.available_stock),
        volumeCm3: parseNumber(product.volume_cm3),
        lengthCm: parseNumber(product.length_cm),
        widthCm: parseNumber(product.width_cm),
        heightCm: parseNumber(product.height_cm)
      }));

    const findProduct = value => {
      const code = normalize(value);
      if (!code) {
        return null;
      }
      let match = productEntries.find(product => product.nameLower === code);
      if (match) {
        return match;
      }
      match = productEntries.find(product => product.skuLower && product.skuLower === code);
      if (match) {
        return match;
      }
      match = productEntries.find(
        product => product.barcodeLower && product.barcodeLower === code
      );
      if (match) {
        return match;
      }
      const prefixMatches = productEntries.filter(product =>
        product.nameLower.startsWith(code)
      );
      if (prefixMatches.length === 1) {
        return prefixMatches[0];
      }
      return null;
    };

    const getProductVolume = product => {
      if (!product) {
        return null;
      }
      if (product.volumeCm3) {
        return product.volumeCm3;
      }
      if (product.lengthCm && product.widthCm && product.heightCm) {
        return product.lengthCm * product.widthCm * product.heightCm;
      }
      return null;
    };

    const getCartonSize = () => {
      if (formatSelect && formatSelect.value && formatSelect.value !== 'custom') {
        const selected = formats.find(
          format => String(format.id) === String(formatSelect.value)
        );
        if (selected) {
          return {
            lengthCm: parseNumber(selected.length_cm),
            widthCm: parseNumber(selected.width_cm),
            heightCm: parseNumber(selected.height_cm),
            maxWeightG: parseNumber(selected.max_weight_g)
          };
        }
      }
      return {
        lengthCm: parseNumber(customLength && customLength.value),
        widthCm: parseNumber(customWidth && customWidth.value),
        heightCm: parseNumber(customHeight && customHeight.value),
        maxWeightG: parseNumber(customWeight && customWeight.value)
      };
    };

    const computeMaxUnits = (product, carton) => {
      if (!product || !carton) {
        return null;
      }
      const cartonVolume =
        carton.lengthCm && carton.widthCm && carton.heightCm
          ? carton.lengthCm * carton.widthCm * carton.heightCm
          : null;
      const productVolume = getProductVolume(product);
      let maxByVolume = null;
      if (cartonVolume && productVolume && productVolume > 0) {
        maxByVolume = Math.floor(cartonVolume / productVolume);
        if (maxByVolume < 1) {
          maxByVolume = 1;
        }
      }
      let maxByWeight = null;
      if (product.weightG && carton.maxWeightG) {
        maxByWeight = Math.floor(carton.maxWeightG / product.weightG);
        if (maxByWeight < 1) {
          maxByWeight = 1;
        }
      }
      if (maxByVolume && maxByWeight) {
        return Math.min(maxByVolume, maxByWeight);
      }
      return maxByVolume || maxByWeight;
    };

    const collectValues = () =>
      Array.from(container.querySelectorAll('.pack-line')).map(line => ({
        product_code: line.querySelector('.pack-line-product')?.value || '',
        quantity: line.querySelector('.pack-line-quantity')?.value || ''
      }));

    const sumPlannedQuantity = product => {
      if (!product) {
        return null;
      }
      const targetKey = product.key;
      if (!targetKey) {
        return null;
      }
      let total = 0;
      Array.from(container.querySelectorAll('.pack-line')).forEach(line => {
        const productInput = line.querySelector('.pack-line-product');
        const quantityInput = line.querySelector('.pack-line-quantity');
        const lineProduct = findProduct(productInput ? productInput.value : '');
        if (!lineProduct || lineProduct.key !== targetKey) {
          return;
        }
        const qty = parseInt(quantityInput ? quantityInput.value : '', 10);
        if (Number.isFinite(qty) && qty > 0) {
          total += qty;
        }
      });
      return total;
    };

    const updateLineMetrics = line => {
      const productInput = line.querySelector('.pack-line-product');
      const quantityInput = line.querySelector('.pack-line-quantity');
      const maxUnitsEl = line.querySelector('.pack-line-max');
      const equivEl = line.querySelector('.pack-line-equivalent');
      const availableEl = line.querySelector('.pack-line-available');
      const remainingEl = line.querySelector('.pack-line-remaining');
      if (!productInput || !quantityInput || !maxUnitsEl || !equivEl || !availableEl || !remainingEl) {
        return;
      }
      const product = findProduct(productInput.value);
      if (!product) {
        maxUnitsEl.textContent = 'N/A';
        equivEl.textContent = 'N/A';
        availableEl.textContent = 'N/A';
        remainingEl.textContent = 'N/A';
        remainingEl.classList.remove('metric-negative');
        return;
      }
      const carton = getCartonSize();
      const maxUnits = computeMaxUnits(product, carton);
      if (!maxUnits) {
        maxUnitsEl.textContent = 'N/A';
        equivEl.textContent = 'N/A';
      } else {
        maxUnitsEl.textContent = `${maxUnits} u.`;
        const qty = parseInt(quantityInput.value, 10);
        if (Number.isFinite(qty) && qty > 0) {
          equivEl.textContent = `${Math.ceil(qty / maxUnits)} carton(s)`;
        } else {
          equivEl.textContent = '-';
        }
      }
      const availableStock = Number.isFinite(product.availableStock)
        ? Math.floor(product.availableStock)
        : null;
      const planned = sumPlannedQuantity(product) ?? 0;
      if (availableStock === null) {
        availableEl.textContent = 'N/A';
        remainingEl.textContent = 'N/A';
        remainingEl.classList.remove('metric-negative');
        return;
      }
      const remaining = availableStock - planned;
      availableEl.textContent = `${availableStock} u.`;
      remainingEl.textContent = `${remaining} u.`;
      remainingEl.classList.toggle('metric-negative', remaining < 0);
    };

    const updateAllLineMetrics = () => {
      Array.from(container.querySelectorAll('.pack-line')).forEach(updateLineMetrics);
    };

    const buildLine = (index, value, errors) => {
      const line = document.createElement('div');
      line.className = 'pack-line';
      line.dataset.lineIndex = String(index);

      const title = document.createElement('div');
      title.className = 'pack-line-title';
      title.textContent = `Produit ${index}`;
      line.appendChild(title);

      const grid = document.createElement('div');
      grid.className = 'pack-line-grid';

      const productField = document.createElement('div');
      productField.className = 'pack-line-field';
      const productLabel = document.createElement('label');
      productLabel.textContent = 'Code produit';
      productField.appendChild(productLabel);

      const productInline = document.createElement('div');
      productInline.className = 'scan-inline';
      const productInput = document.createElement('input');
      productInput.type = 'text';
      productInput.id = `id_pack_line_${index}_product_code`;
      productInput.name = `line_${index}_product_code`;
      productInput.className = 'pack-line-product';
      productInput.setAttribute('list', 'product-options');
      productInput.setAttribute('autocomplete', 'off');
      productInput.value = value.product_code || '';

      const scanBtn = document.createElement('button');
      scanBtn.type = 'button';
      scanBtn.className = 'scan-scan-btn';
      scanBtn.dataset.scanTarget = productInput.id;
      scanBtn.textContent = 'Scan';

      productInline.appendChild(productInput);
      productInline.appendChild(scanBtn);
      productField.appendChild(productInline);
      grid.appendChild(productField);

      const quantityField = document.createElement('div');
      quantityField.className = 'pack-line-field';
      const quantityLabel = document.createElement('label');
      quantityLabel.textContent = 'Quantite';
      const quantityInput = document.createElement('input');
      quantityInput.type = 'number';
      quantityInput.name = `line_${index}_quantity`;
      quantityInput.className = 'pack-line-quantity';
      quantityInput.min = '1';
      quantityInput.step = '1';
      quantityInput.value = value.quantity || '';
      quantityField.appendChild(quantityLabel);
      quantityField.appendChild(quantityInput);
      grid.appendChild(quantityField);

      const metrics = document.createElement('div');
      metrics.className = 'pack-line-metrics';
      metrics.innerHTML = '<div>Max carton mono-produit: <span class=\"pack-line-max\">-</span></div><div>Equivalent cartons: <span class=\"pack-line-equivalent\">-</span></div><div>Quantite disponible en stock: <span class=\"pack-line-available\">-</span></div><div>Quantite restante apres preparation: <span class=\"pack-line-remaining\">-</span></div>';
      grid.appendChild(metrics);

      line.appendChild(grid);

      if (errors && errors.length) {
        errors.forEach(error => {
          const errorEl = document.createElement('div');
          errorEl.className = 'scan-message error';
          errorEl.textContent = error;
          line.appendChild(errorEl);
        });
      }

      productInput.addEventListener('input', updateAllLineMetrics);
      quantityInput.addEventListener('input', updateAllLineMetrics);
      productInput.addEventListener('change', updateAllLineMetrics);

      return line;
    };

    const renderLines = count => {
      const currentValues = collectValues();
      const values = currentValues.length ? currentValues : lineValues;
      container.innerHTML = '';
      for (let index = 1; index <= count; index += 1) {
        const value = values[index - 1] || {};
        const errors = lineErrors[String(index)] || [];
        container.appendChild(buildLine(index, value, errors));
      }
      if (lineCountInput) {
        lineCountInput.value = String(count);
      }
      updateAllLineMetrics();
    };

    const toggleCustomFields = () => {
      if (!customFields || !formatSelect) {
        return;
      }
      customFields.style.display = formatSelect.value === 'custom' ? 'block' : 'none';
    };

    const resolveCount = value => {
      const parsed = parseInt(value, 10);
      if (!Number.isFinite(parsed) || parsed < 1) {
        return 1;
      }
      return parsed;
    };

    const initialCount = resolveCount(lineCountInput ? lineCountInput.value : lineValues.length || 1);
    renderLines(initialCount);
    toggleCustomFields();

    if (addButton) {
      addButton.addEventListener('click', () => {
        const nextCount = resolveCount((lineCountInput && lineCountInput.value) || initialCount) + 1;
        renderLines(nextCount);
      });
    }

    if (formatSelect) {
      formatSelect.addEventListener('change', () => {
        toggleCustomFields();
        updateAllLineMetrics();
      });
    }

    [customLength, customWidth, customHeight, customWeight].forEach(input => {
      if (!input) {
        return;
      }
      input.addEventListener('input', () => {
        updateAllLineMetrics();
      });
    });
  }

  function setupShipmentBuilder() {
    const container = document.getElementById('shipment-lines');
    if (!container) {
      return;
    }
    const countInput = document.getElementById('id_carton_count');
    const totalWeightInput = document.getElementById('id_total_weight');
    const lineDataEl = document.getElementById('shipment-lines-data');
    const lineErrorsEl = document.getElementById('shipment-lines-errors');
    const cartonDataEl = document.getElementById('carton-data');
    const productDataEl = document.getElementById('product-data');

    let lineValues = [];
    let lineErrors = {};
    let cartons = [];
    let products = [];

    try {
      lineValues = JSON.parse(lineDataEl ? lineDataEl.textContent || '[]' : '[]');
    } catch (err) {
      lineValues = [];
    }
    try {
      lineErrors = JSON.parse(lineErrorsEl ? lineErrorsEl.textContent || '{}' : '{}');
    } catch (err) {
      lineErrors = {};
    }
    try {
      cartons = JSON.parse(cartonDataEl ? cartonDataEl.textContent || '[]' : '[]');
    } catch (err) {
      cartons = [];
    }
    try {
      products = JSON.parse(productDataEl ? productDataEl.textContent || '[]' : '[]');
    } catch (err) {
      products = [];
    }

    const cartonMap = new Map();
    cartons.forEach(carton => {
      if (carton && carton.id) {
        cartonMap.set(String(carton.id), carton);
      }
    });

    const productEntries = products
      .filter(product => product && product.name)
      .map(product => ({
        name: product.name,
        nameLower: product.name.toLowerCase(),
        sku: product.sku || '',
        barcode: product.barcode || '',
        weightG: product.weight_g || 0
      }));

    const findProductMatch = value => {
      const code = (value || '').trim();
      if (!code) {
        return null;
      }
      const codeLower = code.toLowerCase();
      let match = productEntries.find(product => product.nameLower === codeLower);
      if (match) {
        return match;
      }
      match = productEntries.find(
        product => product.sku && product.sku.toLowerCase() === codeLower
      );
      if (match) {
        return match;
      }
      match = productEntries.find(
        product => product.barcode && product.barcode.toLowerCase() === codeLower
      );
      if (match) {
        return match;
      }
      const prefixMatches = productEntries.filter(product =>
        product.nameLower.startsWith(codeLower)
      );
      if (prefixMatches.length === 1) {
        return prefixMatches[0];
      }
      return null;
    };

    const getProductWeight = value => {
      const product = findProductMatch(value);
      return product ? product.weightG || 0 : 0;
    };

    const readCurrentValues = () => {
      const values = [];
      container.querySelectorAll('.shipment-line').forEach(line => {
        values.push({
          carton_id: line.querySelector('.shipment-line-carton')?.value || '',
          product_code: line.querySelector('.shipment-line-product')?.value || '',
          quantity: line.querySelector('.shipment-line-quantity')?.value || ''
        });
      });
      return values;
    };

    const updateTotalWeight = () => {
      if (!totalWeightInput) {
        return;
      }
      let total = 0;
      container.querySelectorAll('.shipment-line').forEach(line => {
        const cartonId = line.querySelector('.shipment-line-carton')?.value || '';
        const productCode = line.querySelector('.shipment-line-product')?.value || '';
        const quantityRaw = line.querySelector('.shipment-line-quantity')?.value || '';
        if (cartonId) {
          const carton = cartonMap.get(cartonId);
          total += carton ? carton.weight_g || 0 : 0;
          return;
        }
        const quantity = parseInt(quantityRaw, 10);
        if (productCode && Number.isFinite(quantity) && quantity > 0) {
          total += getProductWeight(productCode) * quantity;
        }
      });
      totalWeightInput.value = String(total);
    };

    const updateCartonAvailability = () => {
      const selected = new Set();
      container.querySelectorAll('.shipment-line-carton').forEach(select => {
        const value = select.value || '';
        if (value) {
          selected.add(value);
        }
      });
      container.querySelectorAll('.shipment-line-carton').forEach(select => {
        const current = select.value || '';
        Array.from(select.options).forEach(option => {
          if (!option.value) {
            option.disabled = false;
            return;
          }
          option.disabled = selected.has(option.value) && option.value !== current;
        });
      });
    };

    const syncLineState = line => {
      const cartonSelect = line.querySelector('.shipment-line-carton');
      const productInput = line.querySelector('.shipment-line-product');
      const quantityInput = line.querySelector('.shipment-line-quantity');
      if (!cartonSelect || !productInput || !quantityInput) {
        return;
      }
      const hasCarton = Boolean(cartonSelect.value);
      if (hasCarton) {
        productInput.value = '';
        quantityInput.value = '';
      }
      productInput.disabled = hasCarton;
      quantityInput.disabled = hasCarton;
    };

    const buildField = (labelText, control) => {
      const field = document.createElement('div');
      field.className = 'shipment-line-field';
      const label = document.createElement('label');
      label.textContent = labelText;
      field.appendChild(label);
      field.appendChild(control);
      return field;
    };

    const renderLines = count => {
      const existingValues = readCurrentValues();
      const values = existingValues.length ? existingValues : lineValues;
      container.innerHTML = '';
      for (let index = 1; index <= count; index += 1) {
        const lineValue = values[index - 1] || {};
        const line = document.createElement('div');
        line.className = 'shipment-line';
        line.dataset.lineIndex = String(index);

        const title = document.createElement('div');
        title.className = 'shipment-line-title';
        title.textContent = `Colis ${index}`;
        line.appendChild(title);

        const grid = document.createElement('div');
        grid.className = 'shipment-line-grid';

        const cartonSelect = document.createElement('select');
        cartonSelect.name = `line_${index}_carton_id`;
        cartonSelect.className = 'shipment-line-carton';
        const defaultOption = document.createElement('option');
        defaultOption.value = '';
        defaultOption.textContent = 'Choisir un colis prepare';
        cartonSelect.appendChild(defaultOption);
        cartons.forEach(carton => {
          const option = document.createElement('option');
          option.value = String(carton.id);
          option.textContent = carton.weight_g
            ? `${carton.code} (${carton.weight_g} g)`
            : carton.code;
          cartonSelect.appendChild(option);
        });
        cartonSelect.value = lineValue.carton_id || '';

        const productInput = document.createElement('input');
        productInput.type = 'text';
        productInput.name = `line_${index}_product_code`;
        productInput.className = 'shipment-line-product';
        productInput.setAttribute('list', 'product-options');
        productInput.setAttribute('autocomplete', 'off');
        productInput.value = lineValue.product_code || '';

        const quantityInput = document.createElement('input');
        quantityInput.type = 'number';
        quantityInput.name = `line_${index}_quantity`;
        quantityInput.className = 'shipment-line-quantity';
        quantityInput.min = '1';
        quantityInput.step = '1';
        quantityInput.value = lineValue.quantity || '';

        grid.appendChild(buildField('Colis prepare', cartonSelect));
        grid.appendChild(buildField('Produit (si creation)', productInput));
        grid.appendChild(buildField('Quantite', quantityInput));
        line.appendChild(grid);

        const errors = lineErrors[String(index)];
        if (errors && errors.length) {
          errors.forEach(error => {
            const errorEl = document.createElement('div');
            errorEl.className = 'scan-message error';
            errorEl.textContent = error;
            line.appendChild(errorEl);
          });
        }

        cartonSelect.addEventListener('change', () => {
          syncLineState(line);
          updateTotalWeight();
          updateCartonAvailability();
        });
        productInput.addEventListener('input', () => {
          if (productInput.value || quantityInput.value) {
            cartonSelect.value = '';
          }
          syncLineState(line);
          updateTotalWeight();
          updateCartonAvailability();
        });
        quantityInput.addEventListener('input', () => {
          if (productInput.value || quantityInput.value) {
            cartonSelect.value = '';
          }
          syncLineState(line);
          updateTotalWeight();
          updateCartonAvailability();
        });

        syncLineState(line);
        container.appendChild(line);
      }
      updateCartonAvailability();
      updateTotalWeight();
    };

    const resolveCount = value => {
      const parsed = parseInt(value, 10);
      if (!Number.isFinite(parsed) || parsed < 1) {
        return 1;
      }
      return parsed;
    };

    const initialCount = resolveCount(countInput ? countInput.value : 1);
    renderLines(initialCount);

    if (countInput) {
      const handleCountChange = event => {
        const nextCount = resolveCount(event.target.value);
        event.target.value = String(nextCount);
        renderLines(nextCount);
      };
      countInput.addEventListener('input', handleCountChange);
      countInput.addEventListener('change', handleCountChange);
    }
  }

  function setupShipmentContactFilters() {
    const destinationSelect = document.getElementById('id_destination');
    const recipientSelect = document.getElementById('id_recipient_contact');
    const correspondentSelect = document.getElementById('id_correspondent_contact');
    const destinationsEl = document.getElementById('destination-data');
    const recipientsEl = document.getElementById('recipient-contacts-data');
    const correspondentsEl = document.getElementById('correspondent-contacts-data');

    if (!destinationSelect || !recipientSelect || !correspondentSelect || !destinationsEl) {
      return;
    }

    let destinations = [];
    let recipients = [];
    let correspondents = [];

    try {
      destinations = JSON.parse(destinationsEl.textContent || '[]');
    } catch (err) {
      destinations = [];
    }
    try {
      recipients = JSON.parse(recipientsEl ? recipientsEl.textContent || '[]' : '[]');
    } catch (err) {
      recipients = [];
    }
    try {
      correspondents = JSON.parse(
        correspondentsEl ? correspondentsEl.textContent || '[]' : '[]'
      );
    } catch (err) {
      correspondents = [];
    }

    const destinationMap = new Map(
      destinations.map(destination => [String(destination.id), destination])
    );
    const normalize = value => (value || '').toString().trim().toLowerCase();

    const renderOptions = (select, options, selectedValue) => {
      const fragment = document.createDocumentFragment();
      const empty = document.createElement('option');
      empty.value = '';
      empty.textContent = '---';
      fragment.appendChild(empty);
      options.forEach(option => {
        const optionEl = document.createElement('option');
        optionEl.value = String(option.id);
        optionEl.textContent = option.name;
        fragment.appendChild(optionEl);
      });
      select.innerHTML = '';
      select.appendChild(fragment);
      if (selectedValue && options.some(option => String(option.id) === String(selectedValue))) {
        select.value = String(selectedValue);
      } else if (options.length === 1) {
        select.value = String(options[0].id);
      } else {
        select.value = '';
      }
    };

    const updateContacts = () => {
      const destination = destinationMap.get(String(destinationSelect.value));
      const selectedRecipient = recipientSelect.value;
      const selectedCorrespondent = correspondentSelect.value;
      let recipientOptions = recipients;
      let correspondentOptions = correspondents;

      if (destination) {
        const country = normalize(destination.country);
        if (country) {
          recipientOptions = recipients.filter(recipient =>
            (recipient.countries || []).some(entry => normalize(entry) === country)
          );
        } else {
          recipientOptions = [];
        }
        if (destination.correspondent_contact_id) {
          correspondentOptions = correspondents.filter(
            correspondent =>
              String(correspondent.id) === String(destination.correspondent_contact_id)
          );
        } else {
          correspondentOptions = [];
        }
      }

      renderOptions(recipientSelect, recipientOptions, selectedRecipient);
      renderOptions(correspondentSelect, correspondentOptions, selectedCorrespondent);
    };

    destinationSelect.addEventListener('change', updateContacts);
    updateContacts();
  }

  function setupReceiptLines() {
    const container = document.getElementById('receipt-lines');
    if (!container) {
      return;
    }
    const addButton = document.getElementById('receipt-add-line');
    const countInput = document.getElementById('receipt_line_count');
    const lineDataEl = document.getElementById('receipt-lines-data');
    const lineErrorsEl = document.getElementById('receipt-lines-errors');
    const locationDataEl = document.getElementById('receipt-location-data');
    const statusDataEl = document.getElementById('receipt-status-data');
    const productDataEl = document.getElementById('product-data');

    let lineValues = [];
    let lineErrors = {};
    let locations = [];
    let statuses = [];
    let products = [];

    try {
      lineValues = JSON.parse(lineDataEl ? lineDataEl.textContent : '[]');
    } catch (err) {
      lineValues = [];
    }
    try {
      lineErrors = JSON.parse(lineErrorsEl ? lineErrorsEl.textContent : '{}') || {};
    } catch (err) {
      lineErrors = {};
    }
    try {
      locations = JSON.parse(locationDataEl ? locationDataEl.textContent : '[]');
    } catch (err) {
      locations = [];
    }
    try {
      statuses = JSON.parse(statusDataEl ? statusDataEl.textContent : '[]');
    } catch (err) {
      statuses = [];
    }
    try {
      const rawProducts = JSON.parse(productDataEl ? productDataEl.textContent : '[]');
      products = rawProducts
        .filter(product => product && product.name)
        .map(product => ({
          name: product.name,
          nameLower: product.name.toLowerCase(),
          sku: product.sku || '',
          barcode: product.barcode || '',
          defaultLocationId: product.default_location_id || null,
          storageConditions: product.storage_conditions || ''
        }));
    } catch (err) {
      products = [];
    }

    const findProductMatch = value => {
      const code = (value || '').trim();
      if (!code) {
        return null;
      }
      const codeLower = code.toLowerCase();
      let match = products.find(product => product.nameLower === codeLower);
      if (match) {
        return match;
      }
      match = products.find(product => product.sku && product.sku.toLowerCase() === codeLower);
      if (match) {
        return match;
      }
      match = products.find(
        product => product.barcode && product.barcode.toLowerCase() === codeLower
      );
      if (match) {
        return match;
      }
      const prefixMatches = products.filter(product =>
        product.nameLower.startsWith(codeLower)
      );
      if (prefixMatches.length === 1) {
        return prefixMatches[0];
      }
      return null;
    };

    const readCurrentValues = () => {
      const values = [];
      const lines = container.querySelectorAll('.receipt-line');
      lines.forEach(line => {
        const index = line.dataset.lineIndex;
        values.push({
          product_code: line.querySelector(`[name="line_${index}_product_code"]`)?.value || '',
          quantity: line.querySelector(`[name="line_${index}_quantity"]`)?.value || '',
          lot_code: line.querySelector(`[name="line_${index}_lot_code"]`)?.value || '',
          expires_on: line.querySelector(`[name="line_${index}_expires_on"]`)?.value || '',
          lot_status: line.querySelector(`[name="line_${index}_lot_status"]`)?.value || '',
          location: line.querySelector(`[name="line_${index}_location"]`)?.value || '',
          storage_conditions:
            line.querySelector(`[name="line_${index}_storage_conditions"]`)?.value || ''
        });
      });
      return values;
    };

    const buildField = (labelText, control) => {
      const field = document.createElement('div');
      field.className = 'pack-line-field';
      const label = document.createElement('label');
      label.textContent = labelText;
      field.appendChild(label);
      field.appendChild(control);
      return field;
    };

    const applyDefaults = (product, locationSelect, storageInput) => {
      if (!product) {
        return;
      }
      if (locationSelect && !locationSelect.value && product.defaultLocationId) {
        locationSelect.value = String(product.defaultLocationId);
      }
      if (storageInput && !storageInput.value) {
        storageInput.value = product.storageConditions || '';
      }
    };

    const renderLines = count => {
      const existingValues = readCurrentValues();
      const values = existingValues.length ? existingValues : lineValues;
      container.innerHTML = '';
      for (let index = 1; index <= count; index += 1) {
        const lineValue = values[index - 1] || {};
        const line = document.createElement('div');
        line.className = 'pack-line receipt-line';
        line.dataset.lineIndex = String(index);

        const title = document.createElement('div');
        title.className = 'pack-line-title';
        title.textContent = `Ligne ${index}`;
        line.appendChild(title);

        const grid = document.createElement('div');
        grid.className = 'pack-line-grid receipt-line-grid';

        const productInput = document.createElement('input');
        productInput.type = 'text';
        productInput.name = `line_${index}_product_code`;
        productInput.id = `id_line_${index}_product_code`;
        productInput.setAttribute('list', 'product-options');
        productInput.setAttribute('autocomplete', 'off');
        productInput.value = lineValue.product_code || '';

        const scanButton = document.createElement('button');
        scanButton.type = 'button';
        scanButton.className = 'scan-scan-btn';
        scanButton.textContent = 'Scan';
        scanButton.setAttribute('data-scan-target', productInput.id);

        const productWrap = document.createElement('div');
        productWrap.className = 'scan-inline';
        productWrap.appendChild(productInput);
        productWrap.appendChild(scanButton);

        const quantityInput = document.createElement('input');
        quantityInput.type = 'number';
        quantityInput.name = `line_${index}_quantity`;
        quantityInput.min = '1';
        quantityInput.step = '1';
        quantityInput.value = lineValue.quantity || '';

        const lotCodeInput = document.createElement('input');
        lotCodeInput.type = 'text';
        lotCodeInput.name = `line_${index}_lot_code`;
        lotCodeInput.value = lineValue.lot_code || '';

        const expiresInput = document.createElement('input');
        expiresInput.type = 'date';
        expiresInput.name = `line_${index}_expires_on`;
        expiresInput.value = lineValue.expires_on || '';

        const statusSelect = document.createElement('select');
        statusSelect.name = `line_${index}_lot_status`;
        const statusDefault = document.createElement('option');
        statusDefault.value = '';
        statusDefault.textContent = 'Auto';
        statusSelect.appendChild(statusDefault);
        statuses.forEach(status => {
          const option = document.createElement('option');
          option.value = status[0];
          option.textContent = status[1];
          statusSelect.appendChild(option);
        });
        statusSelect.value = lineValue.lot_status || '';

        const locationSelect = document.createElement('select');
        locationSelect.name = `line_${index}_location`;
        const locationDefault = document.createElement('option');
        locationDefault.value = '';
        locationDefault.textContent = 'Emplacement auto';
        locationSelect.appendChild(locationDefault);
        locations.forEach(location => {
          const option = document.createElement('option');
          option.value = String(location.id);
          option.textContent = location.label;
          locationSelect.appendChild(option);
        });
        locationSelect.value = lineValue.location || '';

        const storageInput = document.createElement('input');
        storageInput.type = 'text';
        storageInput.name = `line_${index}_storage_conditions`;
        storageInput.value = lineValue.storage_conditions || '';

        grid.appendChild(buildField('Produit', productWrap));
        grid.appendChild(buildField('Quantite', quantityInput));
        grid.appendChild(buildField('Lot', lotCodeInput));
        grid.appendChild(buildField('Peremption', expiresInput));
        grid.appendChild(buildField('Statut', statusSelect));
        grid.appendChild(buildField('Emplacement', locationSelect));
        grid.appendChild(buildField('Conditions', storageInput));

        productInput.addEventListener('input', () => {
          const product = findProductMatch(productInput.value);
          applyDefaults(product, locationSelect, storageInput);
        });
        productInput.addEventListener('blur', () => {
          const product = findProductMatch(productInput.value);
          applyDefaults(product, locationSelect, storageInput);
        });
        applyDefaults(findProductMatch(productInput.value), locationSelect, storageInput);

        line.appendChild(grid);
        const errors = lineErrors[String(index)];
        if (errors && errors.length) {
          errors.forEach(error => {
            const errorEl = document.createElement('div');
            errorEl.className = 'scan-message error';
            errorEl.textContent = error;
            line.appendChild(errorEl);
          });
        }
        container.appendChild(line);
      }
      if (countInput) {
        countInput.value = String(count);
      }
    };

    const resolveCount = value => {
      const parsed = parseInt(value, 10);
      if (!Number.isFinite(parsed) || parsed < 1) {
        return 1;
      }
      return parsed;
    };

    const initialCount = resolveCount(countInput ? countInput.value : 1);
    renderLines(initialCount);

    if (addButton) {
      addButton.addEventListener('click', () => {
        const nextCount = resolveCount(countInput ? countInput.value : initialCount) + 1;
        renderLines(nextCount);
      });
    }
  }

  function setupLiveSync() {
    const banner = document.getElementById('scan-sync-banner');
    if (!banner) {
      return;
    }
    const syncUrl = banner.dataset.syncUrl;
    if (!syncUrl) {
      return;
    }
    const intervalRaw = parseInt(banner.dataset.syncInterval, 10);
    const intervalMs = Number.isFinite(intervalRaw) && intervalRaw > 0 ? intervalRaw : 8000;
    const reloadButton = document.getElementById('scan-sync-reload');

    let lastVersion = null;
    let isDirty = false;
    let isPolling = false;

    const markDirty = event => {
      if (event.target && event.target.matches('input, textarea, select')) {
        isDirty = true;
      }
    };

    document.addEventListener('input', markDirty);
    document.addEventListener('change', markDirty);

    const showBanner = () => {
      banner.classList.add('active');
    };

    const hideBanner = () => {
      banner.classList.remove('active');
    };

    const canAutoReload = () => {
      if (isDirty) {
        return false;
      }
      if (overlay && overlay.classList.contains('active')) {
        return false;
      }
      return true;
    };

    const triggerReload = () => {
      window.location.reload();
    };

    const handleUpdate = () => {
      if (canAutoReload()) {
        triggerReload();
      } else {
        showBanner();
      }
    };

    const fetchSync = async () => {
      if (isPolling || document.hidden) {
        return;
      }
      isPolling = true;
      try {
        const response = await fetch(syncUrl, {
          cache: 'no-store',
          headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });
        if (!response.ok) {
          return;
        }
        const data = await response.json();
        const version = data && data.version ? Number(data.version) : null;
        if (!version) {
          return;
        }
        if (lastVersion === null) {
          lastVersion = version;
          hideBanner();
          return;
        }
        if (version !== lastVersion) {
          lastVersion = version;
          handleUpdate();
        }
      } catch (err) {
        // Ignore network issues.
      } finally {
        isPolling = false;
      }
    };

    if (reloadButton) {
      reloadButton.addEventListener('click', triggerReload);
    }

    fetchSync();
    setInterval(fetchSync, intervalMs);
  }

  document.addEventListener('click', event => {
    const trigger = event.target.closest('[data-scan-target]');
    if (!trigger) {
      return;
    }
    const targetId = trigger.getAttribute('data-scan-target');
    const input = document.getElementById(targetId);
    if (!input) {
      return;
    }
    startScan(input);
  });

  setupThemeToggle();
  setupUiToggle();
  setupProductDatalist();
  setupPackLines();
  setupShipmentBuilder();
  setupShipmentContactFilters();
  setupReceiptLines();
  setupLiveSync();

  const receivedOnInput = document.getElementById('id_received_on');
  if (receivedOnInput && !receivedOnInput.value) {
    receivedOnInput.value = new Date().toISOString().slice(0, 10);
  }

  if (closeBtn) {
    closeBtn.addEventListener('click', () => {
      stopScan();
    });
  }

  if (overlay) {
    overlay.addEventListener('click', event => {
      if (event.target === overlay) {
        stopScan();
      }
    });
  }
})();
