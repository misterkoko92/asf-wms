(() => {
  const overlay = document.getElementById('scan-overlay');
  const video = document.getElementById('scan-video');
  const statusEl = document.getElementById('scan-status');
  const closeBtn = document.getElementById('scan-close');
  const scanTitle = document.getElementById('scan-modal-title');
  const captureBtn = document.getElementById('scan-capture');
  const cameraFacingButtons = document.querySelectorAll('[data-scan-camera-facing]');

  let activeInput = null;
  let stream = null;
  let detector = null;
  let zxingReader = null;
  let zxingControls = null;
  let scanning = false;
  let scanStartInFlight = false;
  let scanSessionId = 0;
  let activeScanTrigger = null;
  let ocrActiveInput = null;
  let ocrProducts = [];
  let ocrOverlay = null;
  let ocrStatusEl = null;
  let ocrListEl = null;
  let ocrRawEl = null;
  let ocrRetryBtn = null;
  let ocrCancelBtn = null;
  let ocrSessionId = 0;
  let packProductResolver = null;
  let productResolver = null;
  let selectedCameraFacingMode = 'environment';
  const ZXING_SRC = '/static/scan/zxing.min.js';
  const OCR_DISABLED_MESSAGE = 'OCR indisponible. Utilisez la saisie manuelle.';
  const CAMERA_RETRY_DELAYS_MS = [160, 320, 640];
  const CAMERA_RETRYABLE_ERROR_NAMES = new Set(['AbortError', 'NotReadableError', 'TrackStartError']);
  const CAMERA_PERMISSION_ERROR_NAMES = new Set([
    'NotAllowedError',
    'PermissionDeniedError',
    'SecurityError'
  ]);
  const CAMERA_RETRYABLE_MESSAGE_SNIPPETS = [
    'aborterror',
    'notreadableerror',
    'trackstarterror',
    'camera-restarting',
    'device in use',
    'could not start video source',
    'starting video failed',
    'device already in use',
    'hardware error'
  ];

  function setStatus(text) {
    if (statusEl) {
      statusEl.textContent = text;
    }
  }

  function getCameraVideoConstraints() {
    return { facingMode: { ideal: selectedCameraFacingMode } };
  }

  function getCameraMediaConstraints() {
    return {
      video: getCameraVideoConstraints(),
      audio: false
    };
  }

  function syncCameraFacingControls() {
    cameraFacingButtons.forEach(button => {
      const isActive = button.dataset.scanCameraFacing === selectedCameraFacingMode;
      button.classList.toggle('is-active', isActive);
      button.setAttribute('aria-pressed', isActive ? 'true' : 'false');
    });
  }

  function restartScanWithSelectedCamera(previousMode, previousBarcodeInput, previousOcrInput) {
    stopScan().then(() => {
      if (previousMode === 'ocr' && previousOcrInput) {
        startOcrScan(previousOcrInput);
        return;
      }
      if (previousBarcodeInput) {
        startScan(previousBarcodeInput);
      }
    });
  }

  function setupCameraFacingControls() {
    if (!cameraFacingButtons.length) {
      return;
    }
    syncCameraFacingControls();
    cameraFacingButtons.forEach(button => {
      button.addEventListener('click', () => {
        const nextMode = button.dataset.scanCameraFacing || 'environment';
        if (nextMode === selectedCameraFacingMode) {
          return;
        }
        const previousMode = overlay.dataset.mode;
        const previousBarcodeInput = activeInput;
        const previousOcrInput = ocrActiveInput;
        selectedCameraFacingMode = nextMode;
        syncCameraFacingControls();
        if (!overlay || !overlay.classList.contains('active')) {
          return;
        }
        restartScanWithSelectedCamera(previousMode, previousBarcodeInput, previousOcrInput);
      });
    });
  }

  function wait(ms) {
    return new Promise(resolve => window.setTimeout(resolve, ms));
  }

  function stopStreamTracks(targetStream) {
    if (!targetStream || typeof targetStream.getTracks !== 'function') {
      return;
    }
    targetStream.getTracks().forEach(track => {
      try {
        track.stop();
      } catch (err) {
        // Ignore track stop errors.
      }
    });
  }

  function releaseCameraStream() {
    const currentStream = stream;
    const attachedStream =
      video && video.srcObject && video.srcObject !== currentStream ? video.srcObject : null;
    stopStreamTracks(currentStream);
    stopStreamTracks(attachedStream);
    stream = null;
  }

  function releaseVideoElement() {
    if (!video) {
      return;
    }
    try {
      video.pause();
    } catch (err) {
      // Ignore pause errors.
    }
    video.srcObject = null;
    video.removeAttribute('src');
  }

  function resetZxingReader() {
    if (zxingControls && typeof zxingControls.stop === 'function') {
      try {
        zxingControls.stop();
      } catch (err) {
        // Ignore ZXing stop errors.
      }
    }
    zxingControls = null;
    if (!zxingReader) {
      return;
    }
    try {
      zxingReader.reset();
    } catch (err) {
      // Ignore reset errors.
    }
    zxingReader = null;
  }

  function isPermissionCameraError(err) {
    return !!(err && CAMERA_PERMISSION_ERROR_NAMES.has(err.name || ''));
  }

  function isRetryableCameraError(err) {
    if (!err) {
      return false;
    }
    if (CAMERA_RETRYABLE_ERROR_NAMES.has(err.name || '')) {
      return true;
    }
    const message = `${err.name || ''} ${err.message || ''}`.toLowerCase();
    return CAMERA_RETRYABLE_MESSAGE_SNIPPETS.some(snippet => message.includes(snippet));
  }

  async function retryTransientCameraStart(startFn, retryLabel) {
    let lastError = null;
    for (let attempt = 0; attempt <= CAMERA_RETRY_DELAYS_MS.length; attempt += 1) {
      try {
        return await startFn(attempt);
      } catch (err) {
        lastError = err;
        if (!isRetryableCameraError(err) || attempt === CAMERA_RETRY_DELAYS_MS.length) {
          throw err;
        }
        releaseCameraStream();
        releaseVideoElement();
        setStatus(retryLabel || 'Réactivation caméra...');
        await wait(CAMERA_RETRY_DELAYS_MS[attempt]);
      }
    }
    throw lastError;
  }

  async function handleCameraStartFailure(err) {
    if (isPermissionCameraError(err)) {
      setStatus('Accès caméra refusé.');
    } else if (isRetryableCameraError(err)) {
      setStatus('Caméra indisponible. Réessayez.');
    } else {
      setStatus('Démarrage caméra impossible.');
    }
    await stopScan();
  }

  function dispatchValueEvent(input) {
    if (!input) {
      return;
    }
    const tagName = input.tagName ? input.tagName.toLowerCase() : '';
    const eventName = tagName === 'select' ? 'change' : 'input';
    input.dispatchEvent(new Event(eventName, { bubbles: true }));
  }

  function blurElement(element) {
    if (element && typeof element.blur === 'function') {
      element.blur();
    }
  }

  function releaseScanInteraction() {
    blurElement(activeScanTrigger);
    blurElement(activeInput);
    if (document.activeElement && document.activeElement !== document.body) {
      blurElement(document.activeElement);
    }
    activeScanTrigger = null;
  }

  function applyScanValue(input, code) {
    if (!input) {
      return;
    }
    const tagName = input.tagName ? input.tagName.toLowerCase() : '';
    if (input.classList.contains('pack-line-product') && packProductResolver) {
      const matched = packProductResolver(code);
      if (matched && matched.codeValue) {
        input.value = matched.codeValue;
        dispatchValueEvent(input);
        return;
      }
    }
    if (tagName === 'select' && productResolver) {
      const matched = productResolver(code);
      if (matched && matched.codeValue) {
        const valueToSet = matched.codeValue;
        const hasOption = Array.from(input.options || []).some(
          option => option.value === valueToSet
        );
        if (!hasOption) {
          const option = document.createElement('option');
          option.value = valueToSet;
          option.textContent = matched.name
            ? matched.brand
              ? `${matched.name} — ${matched.brand}`
              : matched.name
            : valueToSet;
          input.appendChild(option);
        }
        input.value = valueToSet;
        dispatchValueEvent(input);
        return;
      }
    }
    if (tagName === 'select') {
      const hasOption = Array.from(input.options || []).some(
        option => option.value === code
      );
      if (!hasOption && code) {
        const option = document.createElement('option');
        option.value = code;
        option.textContent = code;
        input.appendChild(option);
      }
      input.value = code;
      dispatchValueEvent(input);
      return;
    }
    input.value = code;
    dispatchValueEvent(input);
  }

  function normalizeText(value) {
    return (value || '')
      .toString()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/[^a-zA-Z0-9\s-]/g, ' ')
      .replace(/\s+/g, ' ')
      .trim()
      .toLowerCase();
  }

  function buildFaqSectionId(title, usedIds) {
    const slug = normalizeText(title)
      .replace(/\s+/g, '-')
      .replace(/-+/g, '-')
      .replace(/^-|-$/g, '');
    const baseSlug = slug || 'section';
    let index = 1;
    let sectionId = `faq-${baseSlug}`;
    while (usedIds.has(sectionId) || document.getElementById(sectionId)) {
      index += 1;
      sectionId = `faq-${baseSlug}-${index}`;
    }
    usedIds.add(sectionId);
    return sectionId;
  }

  function addUniqueCodeCandidate(candidates, value) {
    const candidate = (value || '').toString().trim().toLowerCase();
    if (candidate && !candidates.includes(candidate)) {
      candidates.push(candidate);
    }
  }

  function addGtinCandidateVariants(candidates, gtin) {
    addUniqueCodeCandidate(candidates, gtin);
    if (gtin.length === 14 && gtin.startsWith('0')) {
      addUniqueCodeCandidate(candidates, gtin.slice(1));
    }
  }

  function extractUdiCandidateCodes(value) {
    const raw = (value || '').toString().trim();
    if (!raw) {
      return [];
    }
    const candidates = [];
    addUniqueCodeCandidate(candidates, raw);

    Array.from(raw.matchAll(/\(01\)\s*(\d{14})/g)).forEach(match => {
      addGtinCandidateVariants(candidates, match[1]);
    });

    let compact = raw.replace(/[\s\x1d]/g, '');
    [']C1', ']d2', ']e0'].some(prefix => {
      if (compact.toLowerCase().startsWith(prefix.toLowerCase())) {
        compact = compact.slice(prefix.length);
        return true;
      }
      return false;
    });
    Array.from(compact.matchAll(/(?:^|[^\d])01(\d{14})/g)).forEach(match => {
      addGtinCandidateVariants(candidates, match[1]);
    });

    return candidates;
  }

  function createProductMatcher(entries) {
    return value => {
      const raw = (value || '').trim();
      if (!raw) {
        return null;
      }
      const rawLower = raw.toLowerCase();
      const rawNorm = normalizeText(raw);
      const exactCodeFields = ['barcodeLower', 'eanLower'];
      for (const codeField of exactCodeFields) {
        const match = entries.find(
          product => product[codeField] && product[codeField] === rawLower
        );
        if (match) {
          return match;
        }
      }
      const udiCandidates = extractUdiCandidateCodes(raw);
      for (const candidate of udiCandidates) {
        for (const codeField of exactCodeFields) {
          const match = entries.find(
            product => product[codeField] && product[codeField] === candidate
          );
          if (match) {
            return match;
          }
        }
      }
      let match = entries.find(
        product => product.skuLower && product.skuLower === rawLower
      );
      if (match) {
        return match;
      }
      match = entries.find(
        product =>
          product.nameLower === rawLower ||
          (product.nameNorm && product.nameNorm === rawNorm)
      );
      if (match) {
        return match;
      }
      const prefixMatches = entries.filter(
        product =>
          product.nameLower.startsWith(rawLower) ||
          (product.nameNorm && product.nameNorm.startsWith(rawNorm))
      );
      if (prefixMatches.length === 1) {
        return prefixMatches[0];
      }
      return null;
    };
  }

  function setScanMode(mode) {
    if (overlay) {
      if (mode) {
        overlay.dataset.mode = mode;
      } else {
        overlay.removeAttribute('data-mode');
      }
    }
    if (scanTitle) {
      scanTitle.textContent = mode === 'ocr' ? 'Camera OCR' : 'Camera scan';
    }
  }

  async function stopScan() {
    scanSessionId += 1;
    scanning = false;
    detector = null;
    scanStartInFlight = false;
    resetZxingReader();
    releaseCameraStream();
    releaseVideoElement();
    if (overlay) {
      overlay.classList.remove('active');
    }
    releaseScanInteraction();
    activeInput = null;
    setScanMode('');
  }

  async function detectLoop(sessionId) {
    if (sessionId !== scanSessionId || !scanning || !detector || !video) {
      return;
    }
    try {
      const barcodes = await detector.detect(video);
      if (barcodes.length > 0) {
        const code = barcodes[0].rawValue || '';
        handleDetectedCode(code);
        await stopScan();
        return;
      }
    } catch (err) {
      setStatus('Erreur scan: ' + err.message);
    }
    requestAnimationFrame(() => detectLoop(sessionId));
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
      applyScanValue(activeInput, code);
    }
    setStatus('Code detecte: ' + code);
  }

  async function startZXingScan(sessionId) {
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
    if (sessionId !== scanSessionId) {
      return;
    }
    if (!ZXing || !ZXing.BrowserMultiFormatReader) {
      alert('Scan camera non supporte. Utilisez un scanner ou saisissez le code.');
      await stopScan();
      return;
    }
    scanning = true;
    setStatus('Scan en cours...');
    if (overlay) {
      overlay.classList.add('active');
    }
    const callback = (result, err) => {
      if (sessionId !== scanSessionId || !scanning) {
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
      await retryTransientCameraStart(async attempt => {
        if (attempt > 0) {
          resetZxingReader();
        }
        zxingReader = new ZXing.BrowserMultiFormatReader();
        if (typeof zxingReader.decodeFromConstraints === 'function') {
          zxingControls = await zxingReader.decodeFromConstraints(
            getCameraMediaConstraints(),
            video,
            callback
          );
          return zxingControls;
        }
        zxingControls = await zxingReader.decodeFromVideoDevice(null, video, callback);
        return zxingControls;
      }, 'Réactivation caméra...');
    } catch (err) {
      await handleCameraStartFailure(err);
    }
  }

  async function startScan(input) {
    if (scanStartInFlight || scanning) {
      await stopScan();
    }
    scanStartInFlight = true;
    const sessionId = ++scanSessionId;
    activeInput = input;
    setScanMode('barcode');
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
        stream = await retryTransientCameraStart(
          () =>
            navigator.mediaDevices.getUserMedia(getCameraMediaConstraints()),
          'Réactivation caméra...'
        );
      } catch (err) {
        await handleCameraStartFailure(err);
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
      requestAnimationFrame(() => detectLoop(sessionId));
    } else {
      await startZXingScan(sessionId);
    }
    if (sessionId === scanSessionId) {
      scanStartInFlight = false;
    }
  }

  function setOcrProducts(products) {
    ocrProducts = Array.isArray(products) ? products : [];
  }

  function ensureOcrOverlay() {
    if (ocrOverlay) {
      return;
    }
    ocrOverlay = document.createElement('div');
    ocrOverlay.id = 'scan-ocr-overlay';
    ocrOverlay.className = 'scan-choice-overlay';
    ocrOverlay.innerHTML = `
      <div class="scan-choice-modal">
        <div class="scan-choice-header">
          <strong>Selection produit</strong>
          <button type="button" class="scan-choice-close btn-tertiary">Fermer</button>
        </div>
        <div class="scan-choice-status" id="scan-ocr-status"></div>
        <div class="scan-choice-raw" id="scan-ocr-raw"></div>
        <div class="scan-choice-list" id="scan-ocr-list"></div>
        <div class="scan-choice-actions">
          <button type="button" class="scan-scan-btn" id="scan-ocr-retry">Reprendre</button>
          <button type="button" class="scan-submit secondary" id="scan-ocr-cancel">Annuler</button>
        </div>
      </div>
    `;
    document.body.appendChild(ocrOverlay);
    ocrStatusEl = ocrOverlay.querySelector('#scan-ocr-status');
    ocrListEl = ocrOverlay.querySelector('#scan-ocr-list');
    ocrRawEl = ocrOverlay.querySelector('#scan-ocr-raw');
    ocrRetryBtn = ocrOverlay.querySelector('#scan-ocr-retry');
    ocrCancelBtn = ocrOverlay.querySelector('#scan-ocr-cancel');

    const close = () => closeOcrOverlay();
    const closeBtn = ocrOverlay.querySelector('.scan-choice-close');
    if (closeBtn) {
      closeBtn.addEventListener('click', close);
    }
    if (ocrCancelBtn) {
      ocrCancelBtn.addEventListener('click', close);
    }
    if (ocrRetryBtn) {
      ocrRetryBtn.addEventListener('click', () => {
        closeOcrOverlay();
        if (ocrActiveInput) {
          startOcrScan(ocrActiveInput);
        }
      });
    }
    ocrOverlay.addEventListener('click', event => {
      if (event.target === ocrOverlay) {
        close();
      }
    });
  }

  function openOcrOverlay() {
    ensureOcrOverlay();
    if (ocrOverlay) {
      ocrOverlay.classList.add('active');
    }
  }

  function closeOcrOverlay() {
    if (ocrOverlay) {
      ocrOverlay.classList.remove('active');
    }
    ocrSessionId += 1;
  }

  function setOcrOverlayStatus(text) {
    if (ocrStatusEl) {
      ocrStatusEl.textContent = text || '';
    }
  }

  function setOcrOverlayRaw(text) {
    if (!ocrRawEl) {
      return;
    }
    if (text) {
      ocrRawEl.textContent = 'Texte detecte: ' + text;
      ocrRawEl.style.display = 'block';
    } else {
      ocrRawEl.textContent = '';
      ocrRawEl.style.display = 'none';
    }
  }

  function renderOcrMatches(matches) {
    if (!ocrListEl) {
      return;
    }
    ocrListEl.innerHTML = '';
    if (!matches.length) {
      return;
    }
    const fragment = document.createDocumentFragment();
    matches.forEach(match => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'scan-choice-item';
      const nameEl = document.createElement('strong');
      nameEl.textContent = match.name;
      button.appendChild(nameEl);
      const metaEl = document.createElement('span');
      metaEl.textContent = match.brand ? match.brand : 'Marque inconnue';
      button.appendChild(metaEl);
      button.addEventListener('click', () => {
        if (ocrActiveInput) {
          applyScanValue(ocrActiveInput, match.codeValue || match.name);
          ocrActiveInput.focus();
        }
        closeOcrOverlay();
      });
      fragment.appendChild(button);
    });
    ocrListEl.appendChild(fragment);
  }

  function buildOcrMatches(text) {
    const normalized = normalizeText(text);
    if (!normalized || !ocrProducts.length) {
      return [];
    }
    const tokens = normalized.split(/\s+/).filter(token => token.length >= 3);
    const matches = [];
    ocrProducts.forEach(product => {
      const nameNorm = product.nameNorm || normalizeText(product.name);
      let score = 0;
      if (nameNorm.includes(normalized)) {
        score += 3;
      }
      tokens.forEach(token => {
        if (nameNorm.includes(token)) {
          score += 1;
        }
      });
      if (score > 0) {
        matches.push({ ...product, score });
      }
    });
    matches.sort((a, b) => {
      if (b.score !== a.score) {
        return b.score - a.score;
      }
      return a.name.localeCompare(b.name, 'fr', { sensitivity: 'base' });
    });
    return matches.slice(0, 30);
  }

  function captureOcrFrame() {
    if (!video || !video.videoWidth || !video.videoHeight) {
      return null;
    }
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    if (!ctx) {
      return null;
    }
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    return canvas;
  }

  async function runOcrCapture() {
    const sessionId = (ocrSessionId += 1);
    openOcrOverlay();
    setOcrOverlayStatus(OCR_DISABLED_MESSAGE);
    setOcrOverlayRaw('');
    if (ocrListEl) {
      ocrListEl.innerHTML = '';
    }
    if (sessionId !== ocrSessionId) {
      return;
    }
  }

  async function startOcrScan() {
    ocrActiveInput = null;
    await stopScan();
    setStatus(OCR_DISABLED_MESSAGE);
    alert(OCR_DISABLED_MESSAGE);
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
        nameNorm: normalizeText(product.name),
        sku: product.sku || '',
        skuLower: (product.sku || '').toLowerCase(),
        barcode: product.barcode || '',
        barcodeLower: (product.barcode || '').toLowerCase(),
        ean: product.ean || '',
        eanLower: (product.ean || '').toLowerCase(),
        brand: product.brand || '',
        codeValue: product.sku || product.barcode || product.ean || product.name || '',
        defaultLocationId: product.default_location_id || null,
        storageConditions: product.storage_conditions || ''
      }));
    if (products.length === 0) {
      return;
    }
    const inputs = document.querySelectorAll('input[list="product-options"]');
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
        if (product.ean) {
          labelParts.push(product.ean);
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

    const productMatcher = createProductMatcher(products);
    productResolver = value => productMatcher(value);

    if (!inputs.length) {
      return;
    }

    const pickerConfig = document.getElementById('scan-product-picker-config');
    const preferredPickerMode = pickerConfig ? pickerConfig.dataset.pickerMode || '' : '';
    const useSelectFilter = preferredPickerMode
      ? preferredPickerMode === 'filter_select'
      : products.length <= 250;

    const sortedProducts = [...products].sort((a, b) =>
      (a.name || '').localeCompare(b.name || '', 'fr', { sensitivity: 'base' })
    );

    const buildOptionLabel = product =>
      product.brand ? `${product.name} — ${product.brand}` : product.name;

    const replaceWithSelect = input => {
      const select = document.createElement('select');
      const attributes = Array.from(input.attributes);
      attributes.forEach(attr => {
        if (attr.name === 'type' || attr.name === 'list') {
          return;
        }
        select.setAttribute(attr.name, attr.value);
      });
      const filterInput = document.createElement('input');
      filterInput.type = 'text';
      filterInput.className = 'scan-select-filter';
      filterInput.placeholder = 'Rechercher produit';
      filterInput.setAttribute('autocomplete', 'off');

      const stack = document.createElement('div');
      stack.className = 'scan-select-stack';
      stack.appendChild(filterInput);
      stack.appendChild(select);

      const placeholder = document.createElement('option');
      placeholder.value = '';
      placeholder.textContent = '---';
      select.appendChild(placeholder);
      sortedProducts.forEach(product => {
        const option = document.createElement('option');
        option.value = product.codeValue || product.name;
        option.textContent = buildOptionLabel(product);
        select.appendChild(option);
      });
      if (input.value) {
        const match = productMatcher(input.value);
        if (match && match.codeValue) {
          select.value = match.codeValue;
        } else {
          const fallback = document.createElement('option');
          fallback.value = input.value;
          fallback.textContent = input.value;
          select.appendChild(fallback);
          select.value = input.value;
        }
      }
      input.replaceWith(stack);
      return { select, filterInput };
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
      applyProductDefaults(productMatcher(value));
    };

    renderOptions('');
    inputs.forEach(input => {
      let target = input;
      let filterInput = null;
      if (useSelectFilter) {
        const replacement = replaceWithSelect(input);
        target = replacement.select;
        filterInput = replacement.filterInput;
      }
      applyDefaultsFromValue(target.value);
      if (useSelectFilter) {
        const filterSelectOptions = query => {
          const normalized = normalizeText(query);
          const currentValue = target.value;
          target.innerHTML = '';
          const placeholder = document.createElement('option');
          placeholder.value = '';
          placeholder.textContent = '---';
          target.appendChild(placeholder);
          let matched = false;
          sortedProducts.forEach(product => {
            const label = buildOptionLabel(product);
            const labelNorm = normalizeText(label);
            if (normalized && !labelNorm.includes(normalized)) {
              return;
            }
            matched = true;
            const option = document.createElement('option');
            option.value = product.codeValue || product.name;
            option.textContent = label;
            target.appendChild(option);
          });
          if (!matched && normalized) {
            const customOption = document.createElement('option');
            customOption.value = query;
            customOption.textContent = `Nouveau : ${query}`;
            target.appendChild(customOption);
            target.value = query;
            return true;
          }
          if (currentValue) {
            target.value = currentValue;
          }
          return false;
        };
        if (filterInput) {
          filterInput.addEventListener('input', event => {
            const autoSelected = filterSelectOptions(event.target.value);
            applyDefaultsFromValue(target.value);
            if (autoSelected) {
              dispatchValueEvent(target);
            }
          });
        }
        target.addEventListener('change', event => {
          applyDefaultsFromValue(event.target.value);
          if (filterInput) {
          if (event.target.value) {
            const match = productMatcher(event.target.value);
            filterInput.value = match
              ? buildOptionLabel(match)
              : event.target.value;
            } else {
              filterInput.value = '';
            }
          }
        });
      } else {
        target.addEventListener('input', event => {
          applyDefaultsFromValue(event.target.value);
          renderOptions(event.target.value);
        });
        target.addEventListener('focus', event => {
          renderOptions(event.target.value);
        });
        target.addEventListener('change', event => {
          applyDefaultsFromValue(event.target.value);
        });
        target.addEventListener('blur', event => {
          applyDefaultsFromValue(event.target.value);
        });
      }
    });
  }

  function setupPackLines() {
    const container = document.getElementById('pack-lines');
    if (!container) {
      return;
    }
    const packPage = document.getElementById('pack-page');
    const preparateurMode =
      !!packPage && packPage.dataset.preparateurPackMode === '1';
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
    const locationDataEl = document.getElementById('pack-location-data');

    let products = [];
    let formats = [];
    let lineValues = [];
    let lineErrors = {};
    let locations = [];

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
    try {
      locations = JSON.parse(locationDataEl ? locationDataEl.textContent || '[]' : '[]');
    } catch (err) {
      locations = [];
    }

    const normalize = value => (value || '').toString().trim().toLowerCase();
    const emptyPackLineValue = () => ({
      product_code: '',
      quantity: '',
      expires_on: '',
      pack_family_override: ''
    });
    const parseNumber = value => {
      const parsed = parseFloat((value || '').toString().replace(',', '.'));
      return Number.isFinite(parsed) ? parsed : null;
    };

    const productEntries = products
      .filter(product => product && product.name)
      .map(product => ({
        name: product.name,
        brand: product.brand || '',
        nameLower: normalize(product.name),
        nameNorm: normalizeText(product.name),
        sku: product.sku || '',
        skuLower: normalize(product.sku || ''),
        barcode: product.barcode || '',
        barcodeLower: normalize(product.barcode || ''),
        ean: product.ean || '',
        eanLower: normalize(product.ean || ''),
        codeValue: product.sku || product.barcode || product.ean || product.name || '',
        codeLower: normalize(product.sku || product.barcode || product.ean || product.name || ''),
        key:
          normalize(product.sku) ||
          normalize(product.barcode) ||
          normalize(product.ean) ||
          normalize(product.name),
        weightG: parseNumber(product.weight_g),
        availableStock: parseNumber(product.available_stock),
        volumeCm3: parseNumber(product.volume_cm3),
        lengthCm: parseNumber(product.length_cm),
        widthCm: parseNumber(product.width_cm),
        heightCm: parseNumber(product.height_cm)
        ,
        categoryRoot: (product.category_root || '').toString().trim().toUpperCase()
      }));

    setOcrProducts(
      productEntries.map(product => ({
        name: product.name,
        brand: product.brand || '',
        nameNorm: product.nameNorm || normalizeText(product.name),
        codeValue: product.codeValue || product.name || ''
      }))
    );

    const productMatcher = createProductMatcher(productEntries);
    const findProduct = value => productMatcher(value);
    packProductResolver = value => productMatcher(value);
    const unknownProductModalEl = document.getElementById('pack-unknown-product-modal');
    const unknownProductSourceDisplay = document.getElementById(
      'pack-unknown-product-source-display'
    );
    const unknownProductLineIndexInput = document.getElementById(
      'id_unknown_product_line_index'
    );
    const unknownProductSourceInput = document.getElementById(
      'id_unknown_product_source_code'
    );
    const unknownProductNameInput = document.getElementById('id_unknown_product_name');
    const unknownProductBarcodeInput = document.getElementById('id_unknown_product_barcode');
    const unknownProductLocationInput = document.getElementById(
      'id_unknown_product_location'
    );
    const unknownProductWarehouseSelect = document.getElementById(
      'id_unknown_product_location_warehouse'
    );
    const unknownProductZoneSelect = document.getElementById(
      'id_unknown_product_location_zone'
    );
    const unknownProductAisleSelect = document.getElementById(
      'id_unknown_product_location_aisle'
    );
    const unknownProductShelfSelect = document.getElementById(
      'id_unknown_product_location_shelf'
    );
    const canCreateUnknownProduct =
      preparateurMode &&
      !!unknownProductModalEl &&
      !!unknownProductLocationInput &&
      !!unknownProductWarehouseSelect &&
      !!unknownProductZoneSelect &&
      !!unknownProductAisleSelect &&
      !!unknownProductShelfSelect;

    const uniqueValues = values => Array.from(new Set(values.filter(value => !!value)));

    const setSelectOptions = (select, values, selectedValue) => {
      if (!select) {
        return;
      }
      const nextSelectedValue = values.includes(selectedValue) ? selectedValue : '';
      select.innerHTML = '';
      const placeholder = document.createElement('option');
      placeholder.value = '';
      placeholder.textContent = 'Choisir';
      select.appendChild(placeholder);
      values.forEach(value => {
        const option = document.createElement('option');
        option.value = value;
        option.textContent = value;
        select.appendChild(option);
      });
      select.value = nextSelectedValue;
    };

    const refreshUnknownProductLocationSelectors = () => {
      if (!canCreateUnknownProduct) {
        return;
      }
      const initialLocation = locations.find(
        location => String(location.id) === String(unknownProductLocationInput.value || '')
      );
      if (initialLocation) {
        if (!unknownProductWarehouseSelect.dataset.selected) {
          unknownProductWarehouseSelect.dataset.selected = initialLocation.warehouse || '';
        }
        if (!unknownProductZoneSelect.dataset.selected) {
          unknownProductZoneSelect.dataset.selected = initialLocation.zone || '';
        }
        if (!unknownProductAisleSelect.dataset.selected) {
          unknownProductAisleSelect.dataset.selected = initialLocation.aisle || '';
        }
        if (!unknownProductShelfSelect.dataset.selected) {
          unknownProductShelfSelect.dataset.selected = initialLocation.shelf || '';
        }
      }

      const selectedWarehouse =
        unknownProductWarehouseSelect.value || unknownProductWarehouseSelect.dataset.selected || '';
      const warehouseValues = uniqueValues(locations.map(location => location.warehouse || ''));
      setSelectOptions(unknownProductWarehouseSelect, warehouseValues, selectedWarehouse);
      unknownProductWarehouseSelect.dataset.selected = '';

      const zoneValues = uniqueValues(
        locations
          .filter(location => !unknownProductWarehouseSelect.value || location.warehouse === unknownProductWarehouseSelect.value)
          .map(location => location.zone || '')
      );
      const selectedZone =
        unknownProductZoneSelect.value || unknownProductZoneSelect.dataset.selected || '';
      setSelectOptions(unknownProductZoneSelect, zoneValues, selectedZone);
      unknownProductZoneSelect.dataset.selected = '';

      const aisleValues = uniqueValues(
        locations
          .filter(location => {
            if (unknownProductWarehouseSelect.value && location.warehouse !== unknownProductWarehouseSelect.value) {
              return false;
            }
            if (unknownProductZoneSelect.value && location.zone !== unknownProductZoneSelect.value) {
              return false;
            }
            return true;
          })
          .map(location => location.aisle || '')
      );
      const selectedAisle =
        unknownProductAisleSelect.value || unknownProductAisleSelect.dataset.selected || '';
      setSelectOptions(unknownProductAisleSelect, aisleValues, selectedAisle);
      unknownProductAisleSelect.dataset.selected = '';

      const shelfValues = uniqueValues(
        locations
          .filter(location => {
            if (unknownProductWarehouseSelect.value && location.warehouse !== unknownProductWarehouseSelect.value) {
              return false;
            }
            if (unknownProductZoneSelect.value && location.zone !== unknownProductZoneSelect.value) {
              return false;
            }
            if (unknownProductAisleSelect.value && location.aisle !== unknownProductAisleSelect.value) {
              return false;
            }
            return true;
          })
          .map(location => location.shelf || '')
      );
      const selectedShelf =
        unknownProductShelfSelect.value || unknownProductShelfSelect.dataset.selected || '';
      setSelectOptions(unknownProductShelfSelect, shelfValues, selectedShelf);
      unknownProductShelfSelect.dataset.selected = '';

      const selectedLocation = locations.find(location => {
        return (
          location.warehouse === unknownProductWarehouseSelect.value &&
          location.zone === unknownProductZoneSelect.value &&
          location.aisle === unknownProductAisleSelect.value &&
          location.shelf === unknownProductShelfSelect.value
        );
      });
      unknownProductLocationInput.value = selectedLocation ? String(selectedLocation.id) : '';
    };

    const openUnknownProductModal = ({ lineIndex, sourceCode }) => {
      if (!canCreateUnknownProduct || !window.bootstrap || !window.bootstrap.Modal) {
        return;
      }
      const normalizedSourceCode = (sourceCode || '').toString().trim();
      if (unknownProductLineIndexInput) {
        unknownProductLineIndexInput.value = String(lineIndex || '');
      }
      if (unknownProductSourceInput) {
        unknownProductSourceInput.value = normalizedSourceCode;
      }
      if (unknownProductSourceDisplay) {
        unknownProductSourceDisplay.textContent = normalizedSourceCode || '-';
      }
      if (unknownProductBarcodeInput && !unknownProductBarcodeInput.value && normalizedSourceCode) {
        unknownProductBarcodeInput.value = normalizedSourceCode;
      }
      refreshUnknownProductLocationSelectors();
      window.bootstrap.Modal.getOrCreateInstance(unknownProductModalEl).show();
      if (unknownProductNameInput && !unknownProductNameInput.value) {
        unknownProductNameInput.focus();
      }
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
        quantity: line.querySelector('.pack-line-quantity')?.value || '',
        expires_on: line.querySelector('.pack-line-expires-on')?.value || '',
        pack_family_override:
          line.querySelector('.pack-line-family')?.value || ''
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

      const header = document.createElement('div');
      header.className = 'pack-line-header';
      const title = document.createElement('div');
      title.className = 'pack-line-title';
      title.textContent = `Produit ${index}`;
      header.appendChild(title);

      const removeButton = document.createElement('button');
      removeButton.type = 'button';
      removeButton.className = 'scan-scan-btn btn btn-outline-danger btn-sm pack-line-remove-btn';
      removeButton.textContent = 'Retirer';
      header.appendChild(removeButton);
      line.appendChild(header);

      const grid = document.createElement('div');
      grid.className = 'pack-line-grid';

      const searchField = document.createElement('div');
      searchField.className = 'pack-line-field pack-line-search-field';
      const searchLabel = document.createElement('label');
      searchLabel.textContent = 'Rechercher un produit';
      searchField.appendChild(searchLabel);

      const productInput = document.createElement('select');
      productInput.id = `id_pack_line_${index}_product_code`;
      productInput.name = `line_${index}_product_code`;
      productInput.className = 'pack-line-product';

      const filterInput = document.createElement('input');
      filterInput.type = 'text';
      filterInput.className = 'scan-select-filter';
      filterInput.placeholder = 'Rechercher un produit';
      filterInput.setAttribute('autocomplete', 'off');
      searchField.appendChild(filterInput);
      grid.appendChild(searchField);

      const scanField = document.createElement('div');
      scanField.className = 'pack-line-field pack-line-scan-field';
      const scanBtn = document.createElement('button');
      scanBtn.type = 'button';
      scanBtn.className = 'scan-scan-btn btn btn-tertiary';
      scanBtn.dataset.scanTarget = productInput.id;
      scanBtn.textContent = 'Scanner un code barre / QR Code';
      scanField.appendChild(scanBtn);
      grid.appendChild(scanField);

      const selectField = document.createElement('div');
      selectField.className = 'pack-line-field pack-line-select-field';
      const selectLabel = document.createElement('label');
      selectLabel.textContent = 'Produit';
      selectField.appendChild(selectLabel);

      const placeholder = document.createElement('option');
      placeholder.value = '';
      placeholder.textContent = '---';
      productInput.appendChild(placeholder);

      const sortedProducts = [...productEntries].sort((a, b) =>
        a.name.localeCompare(b.name, 'fr', { sensitivity: 'base' })
      );
      const optionLabel = product =>
        product.brand ? `${product.name} — ${product.brand}` : product.name;

      const rebuildOptions = query => {
        const normalized = normalizeText(query);
        const selectedValue = productInput.value;
        let matched = false;
        productInput.innerHTML = '';
        const baseOption = document.createElement('option');
        baseOption.value = '';
        baseOption.textContent = '---';
        productInput.appendChild(baseOption);
        sortedProducts.forEach(product => {
          if (!product.name) {
            return;
          }
          const label = optionLabel(product);
          if (normalized) {
            const labelNorm = normalizeText(label);
            if (!labelNorm.includes(normalized)) {
              return;
            }
          }
          matched = true;
          const option = document.createElement('option');
          option.value = product.codeValue || product.name;
          option.textContent = label;
          productInput.appendChild(option);
        });
        if (!matched && query) {
          const customOption = document.createElement('option');
          customOption.value = query;
          customOption.textContent = `Nouveau : ${query}`;
          productInput.appendChild(customOption);
        }
        if (selectedValue) {
          productInput.value = selectedValue;
        }
      };

      rebuildOptions('');

      if (value.product_code) {
        const initialMatch = findProduct(value.product_code);
        if (initialMatch && initialMatch.codeValue) {
          productInput.value = initialMatch.codeValue;
        } else {
          if (productInput.value !== value.product_code) {
            const fallbackOption = document.createElement('option');
            fallbackOption.value = value.product_code;
            fallbackOption.textContent = value.product_code;
            productInput.appendChild(fallbackOption);
          }
          productInput.value = value.product_code;
        }
      }
      if (productInput.value) {
        const initialSelectedProduct = findProduct(productInput.value);
        filterInput.value = initialSelectedProduct
          ? optionLabel(initialSelectedProduct)
          : value.product_code || productInput.value;
      }

      selectField.appendChild(productInput);
      grid.appendChild(selectField);

      const quantityField = document.createElement('div');
      quantityField.className = 'pack-line-field pack-line-quantity-field';
      const quantityLabel = document.createElement('label');
      quantityLabel.textContent = 'Quantité';
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

      const expiresOnField = document.createElement('div');
      expiresOnField.className = 'pack-line-field pack-line-expires-field';
      const expiresOnLabel = document.createElement('label');
      expiresOnLabel.textContent = 'Date de péremption';
      const expiresOnInput = document.createElement('input');
      expiresOnInput.type = 'date';
      expiresOnInput.name = `line_${index}_expires_on`;
      expiresOnInput.className = 'pack-line-expires-on';
      expiresOnInput.value = value.expires_on || '';
      expiresOnField.appendChild(expiresOnLabel);
      expiresOnField.appendChild(expiresOnInput);
      grid.appendChild(expiresOnField);

      let familyField = null;
      let familySelect = null;
      let familyStatus = null;
      if (preparateurMode) {
        familyField = document.createElement('div');
        familyField.className = 'pack-line-field pack-line-family-field';
        const familyLabel = document.createElement('label');
        familyLabel.textContent = 'Type MM/CN';
        familySelect = document.createElement('select');
        familySelect.name = `line_${index}_pack_family_override`;
        familySelect.className = 'pack-line-family';
        [
          { value: '', label: 'Choisir' },
          { value: 'MM', label: 'MM' },
          { value: 'CN', label: 'CN' }
        ].forEach(optionData => {
          const option = document.createElement('option');
          option.value = optionData.value;
          option.textContent = optionData.label;
          familySelect.appendChild(option);
        });
        familySelect.value = value.pack_family_override || '';
        familyStatus = document.createElement('div');
        familyStatus.className = 'scan-help mt-2';
        familyField.appendChild(familyLabel);
        familyField.appendChild(familySelect);
        familyField.appendChild(familyStatus);
        grid.appendChild(familyField);
      }

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

      filterInput.addEventListener('input', event => {
        rebuildOptions(event.target.value);
      });
      filterInput.addEventListener('change', event => {
        const rawValue = (event.target.value || '').trim();
        if (!rawValue) {
          return;
        }
        const matched = findProduct(rawValue);
        if (matched && matched.codeValue) {
          productInput.value = matched.codeValue;
        } else {
          rebuildOptions(rawValue);
          productInput.value = rawValue;
        }
        dispatchValueEvent(productInput);
      });

      const updateFamilyControls = () => {
        if (!preparateurMode || !familyField || !familySelect || !familyStatus) {
          return;
        }
        const product = findProduct(productInput.value);
        const resolvedFamily =
          product && ['MM', 'CN'].includes(product.categoryRoot)
            ? product.categoryRoot
            : '';
        if (!product) {
          familyField.style.display = 'none';
          familyStatus.textContent = '';
          return;
        }
        if (resolvedFamily) {
          familyField.style.display = 'none';
          familySelect.value = '';
          return;
        }
        familyField.style.display = 'block';
        familyStatus.textContent = 'Choisissez manuellement MM ou CN.';
        familyField.appendChild(familyStatus);
      };

      productInput.addEventListener('change', event => {
        updateAllLineMetrics();
        const selectedValue = (event.target.value || '').trim();
        const match = findProduct(selectedValue);
        if (event.target.value) {
          if (match) {
            filterInput.value = optionLabel(match);
          } else {
            filterInput.value = selectedValue;
          }
        } else {
          filterInput.value = '';
        }
        updateFamilyControls();
        if (preparateurMode && selectedValue && !match) {
          openUnknownProductModal({
            lineIndex: index,
            sourceCode: selectedValue
          });
        }
      });
      quantityInput.addEventListener('input', updateAllLineMetrics);
      productInput.addEventListener('change', updateAllLineMetrics);
      updateFamilyControls();
      removeButton.addEventListener('click', () => {
        const currentValues = collectValues();
        currentValues.splice(index - 1, 1);
        lineErrors = {};
        renderLines(Math.max(1, currentValues.length), currentValues);
      });

      return line;
    };

    const renderLines = (count, valuesOverride = null) => {
      const currentValues = collectValues();
      const values = Array.isArray(valuesOverride)
        ? valuesOverride
        : currentValues.length
          ? currentValues
          : lineValues;
      container.innerHTML = '';
      for (let index = 1; index <= count; index += 1) {
        const value = values[index - 1] || emptyPackLineValue();
        const errors = lineErrors[String(index)] || [];
        container.appendChild(buildLine(index, value, errors));
      }
      if (lineCountInput) {
        lineCountInput.value = String(count);
      }
      container.dispatchEvent(
        new CustomEvent('wms:enhance-number-inputs', {
          bubbles: true,
          detail: { root: container }
        })
      );
      container.dispatchEvent(
        new CustomEvent('wms:enhance-date-inputs', {
          bubbles: true,
          detail: { root: container }
        })
      );
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

    if (canCreateUnknownProduct) {
      [
        unknownProductWarehouseSelect,
        unknownProductZoneSelect,
        unknownProductAisleSelect,
        unknownProductShelfSelect
      ].forEach(select => {
        if (!select) {
          return;
        }
        select.addEventListener('change', refreshUnknownProductLocationSelectors);
      });
      refreshUnknownProductLocationSelectors();
    }

    const initialCount = resolveCount(lineCountInput ? lineCountInput.value : lineValues.length || 1);
    renderLines(initialCount);
    toggleCustomFields();

    if (
      canCreateUnknownProduct &&
      unknownProductModalEl.dataset.openOnLoad === '1' &&
      window.bootstrap &&
      window.bootstrap.Modal
    ) {
      window.setTimeout(() => {
        refreshUnknownProductLocationSelectors();
        window.bootstrap.Modal.getOrCreateInstance(unknownProductModalEl).show();
      }, 0);
    }

    if (addButton) {
      addButton.addEventListener('click', () => {
        const nextCount = resolveCount((lineCountInput && lineCountInput.value) || initialCount) + 1;
        lineErrors = {};
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
    const destinationDataEl = document.getElementById('destination-data');
    const recipientDataEl = document.getElementById('recipient-contacts-data');
    const shipmentForm = document.getElementById('shipment-form');
    const mismatchOverlay = document.getElementById('shipment-preassignment-overlay');
    const mismatchMessage = document.getElementById('shipment-preassignment-message');
    const mismatchAcceptButton = document.getElementById('shipment-preassignment-accept');
    const mismatchRejectButton = document.getElementById('shipment-preassignment-reject');
    const recipientPreferenceOverlay = document.getElementById(
      'shipment-recipient-preference-overlay'
    );
    const recipientPreferenceMessage = document.getElementById(
      'shipment-recipient-preference-message'
    );
    const recipientPreferenceAcceptButton = document.getElementById(
      'shipment-recipient-preference-accept'
    );
    const recipientPreferenceRejectButton = document.getElementById(
      'shipment-recipient-preference-reject'
    );
    const creationModeInputs = Array.from(
      shipmentForm ? shipmentForm.querySelectorAll('input[name="creation_mode"]') : []
    );
    const plannedCartonCountField = document.getElementById(
      'shipment-planned-carton-count-field'
    );
    const withCartonsFields = document.getElementById('shipment-with-cartons-fields');

    let lineValues = [];
    let lineErrors = {};
    let cartons = [];
    let products = [];
    let destinations = [];
    let recipientContacts = [];

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
    try {
      destinations = JSON.parse(destinationDataEl ? destinationDataEl.textContent || '[]' : '[]');
    } catch (err) {
      destinations = [];
    }
    try {
      recipientContacts = JSON.parse(
        recipientDataEl ? recipientDataEl.textContent || '[]' : '[]'
      );
    } catch (err) {
      recipientContacts = [];
    }

    const cartonMap = new Map();
    cartons.forEach(carton => {
      if (carton && carton.id) {
        cartonMap.set(String(carton.id), carton);
      }
    });
    const destinationMap = new Map();
    destinations.forEach(destination => {
      if (destination && destination.id) {
        destinationMap.set(String(destination.id), destination);
      }
    });
    const recipientContactMap = new Map();
    recipientContacts.forEach(recipientContact => {
      if (recipientContact && recipientContact.id) {
        recipientContactMap.set(String(recipientContact.id), recipientContact);
      }
    });

    const parseNumber = value => {
      const parsed = parseFloat((value || '').toString().replace(',', '.'));
      return Number.isFinite(parsed) ? parsed : null;
    };

    const productEntries = products
      .filter(product => product && product.name)
      .map(product => ({
        id: product.id,
        name: product.name,
        nameLower: product.name.toLowerCase(),
        sku: product.sku || '',
        barcode: product.barcode || '',
        ean: product.ean || '',
        brand: product.brand || '',
        codeValue: product.sku || product.barcode || product.ean || product.name || '',
        codeLower: (product.sku || product.barcode || product.ean || product.name || '')
          .toString()
          .toLowerCase(),
        key:
          (product.sku || '').toString().toLowerCase() ||
          (product.barcode || '').toString().toLowerCase() ||
          (product.ean || '').toString().toLowerCase() ||
          (product.name || '').toString().toLowerCase(),
        weightG: parseNumber(product.weight_g) || 0,
        availableStock: parseNumber(product.available_stock),
        volumeCm3: parseNumber(product.volume_cm3),
        lengthCm: parseNumber(product.length_cm),
        widthCm: parseNumber(product.width_cm),
        heightCm: parseNumber(product.height_cm)
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
      match = productEntries.find(
        product => product.ean && product.ean.toLowerCase() === codeLower
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

    const DEFAULT_CARTON = {
      lengthCm: 40,
      widthCm: 30,
      heightCm: 30,
      maxWeightG: 8000
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

    const computeMaxUnits = product => {
      if (!product) {
        return null;
      }
      const cartonVolume = DEFAULT_CARTON.lengthCm * DEFAULT_CARTON.widthCm * DEFAULT_CARTON.heightCm;
      const productVolume = getProductVolume(product);
      let maxByVolume = null;
      if (cartonVolume && productVolume && productVolume > 0) {
        maxByVolume = Math.floor(cartonVolume / productVolume);
        if (maxByVolume < 1) {
          maxByVolume = 1;
        }
      }
      let maxByWeight = null;
      if (product.weightG && DEFAULT_CARTON.maxWeightG) {
        maxByWeight = Math.floor(DEFAULT_CARTON.maxWeightG / product.weightG);
        if (maxByWeight < 1) {
          maxByWeight = 1;
        }
      }
      if (maxByVolume && maxByWeight) {
        return Math.min(maxByVolume, maxByWeight);
      }
      return maxByVolume || maxByWeight;
    };

    const sumPlannedQuantity = product => {
      if (!product || !product.key) {
        return null;
      }
      let total = 0;
      container.querySelectorAll('.shipment-line').forEach(line => {
        const productInput = line.querySelector('.shipment-line-product');
        const quantityInput = line.querySelector('.shipment-line-quantity');
        const lineProduct = findProductMatch(productInput ? productInput.value : '');
        if (!lineProduct || lineProduct.key !== product.key) {
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
      const productInput = line.querySelector('.shipment-line-product');
      const quantityInput = line.querySelector('.shipment-line-quantity');
      const maxEl = line.querySelector('.shipment-line-max');
      const equivEl = line.querySelector('.shipment-line-equivalent');
      const availableEl = line.querySelector('.shipment-line-available');
      const remainingEl = line.querySelector('.shipment-line-remaining');
      if (!productInput || !quantityInput || !maxEl || !equivEl || !availableEl || !remainingEl) {
        return;
      }
      if (!productInput.value) {
        maxEl.textContent = '-';
        equivEl.textContent = '-';
        availableEl.textContent = '-';
        remainingEl.textContent = '-';
        remainingEl.classList.remove('metric-negative');
        return;
      }
      const product = findProductMatch(productInput.value);
      if (!product) {
        maxEl.textContent = 'indisponible';
        equivEl.textContent = 'indisponible';
        availableEl.textContent = 'indisponible';
        remainingEl.textContent = 'indisponible';
        remainingEl.classList.remove('metric-negative');
        return;
      }
      const productVolume = getProductVolume(product);
      const hasWeight = Number.isFinite(product.weightG) && product.weightG > 0;
      if (!productVolume || !hasWeight) {
        maxEl.textContent = 'indisponible';
        equivEl.textContent = 'indisponible';
      } else {
        const maxUnits = computeMaxUnits(product);
        if (!maxUnits) {
          maxEl.textContent = 'indisponible';
          equivEl.textContent = 'indisponible';
        } else {
          maxEl.textContent = `${maxUnits} u.`;
          const qty = parseInt(quantityInput.value, 10);
          if (Number.isFinite(qty) && qty > 0) {
            equivEl.textContent = `${Math.ceil(qty / maxUnits)} carton(s)`;
          } else {
            equivEl.textContent = '-';
          }
        }
      }
      const availableStock = Number.isFinite(product.availableStock)
        ? Math.floor(product.availableStock)
        : null;
      const planned = sumPlannedQuantity(product) ?? 0;
      if (availableStock === null) {
        availableEl.textContent = 'indisponible';
        remainingEl.textContent = 'indisponible';
        remainingEl.classList.remove('metric-negative');
        return;
      }
      const remaining = availableStock - planned;
      availableEl.textContent = `${availableStock} u.`;
      remainingEl.textContent = `${remaining} u.`;
      remainingEl.classList.toggle('metric-negative', remaining < 0);
    };

    const updateAllLineMetrics = () => {
      container.querySelectorAll('.shipment-line').forEach(updateLineMetrics);
    };

    const readCurrentValues = () => {
      const values = [];
      container.querySelectorAll('.shipment-line').forEach(line => {
        values.push({
          carton_id: line.querySelector('.shipment-line-carton')?.value || '',
          product_code: line.querySelector('.shipment-line-product')?.value || '',
          quantity: line.querySelector('.shipment-line-quantity')?.value || '',
          expires_on: line.querySelector('.shipment-line-expires-on')?.value || ''
        });
      });
      return values;
    };

    const isPreparingWithoutCartons = () => {
      const selected = creationModeInputs.find(input => input.checked);
      return selected ? selected.value === 'without_cartons' : false;
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
      const expiresOnInput = line.querySelector('.shipment-line-expires-on');
      const productField = line.querySelector('.shipment-line-product-field');
      const quantityField = line.querySelector('.shipment-line-quantity-field');
      const expiresField = line.querySelector('.shipment-line-expires-field');
      const filterInput = line.querySelector('.scan-select-filter');
      const mismatchConfirmedInput = line.querySelector('.shipment-line-preassigned-confirmed');
      const preferenceOverrideConfirmedInput = line.querySelector(
        '.shipment-line-recipient-preference-confirmed'
      );
      if (!cartonSelect || !productInput || !quantityInput) {
        return;
      }
      const hasCarton = Boolean(cartonSelect.value);
      if (hasCarton) {
        productInput.value = '';
        quantityInput.value = '';
        if (expiresOnInput) {
          expiresOnInput.value = '';
        }
        if (filterInput) {
          filterInput.value = '';
        }
      }
      if (mismatchConfirmedInput) {
        mismatchConfirmedInput.value = '';
      }
      if (preferenceOverrideConfirmedInput) {
        preferenceOverrideConfirmedInput.value = '';
      }
      productInput.disabled = hasCarton;
      quantityInput.disabled = hasCarton;
      if (expiresOnInput) {
        expiresOnInput.disabled = hasCarton;
      }
      if (filterInput) {
        filterInput.disabled = hasCarton;
      }
      if (productField) {
        productField.style.display = hasCarton ? 'none' : '';
      }
      if (quantityField) {
        quantityField.style.display = hasCarton ? 'none' : '';
      }
      if (expiresField) {
        expiresField.style.display = hasCarton ? 'none' : '';
      }
      const metrics = line.querySelector('.shipment-line-metrics');
      if (metrics) {
        metrics.style.display = hasCarton ? 'none' : '';
      }
      const scanBtn = line.querySelector('.shipment-line-scan');
      if (scanBtn) {
        scanBtn.disabled = hasCarton;
      }
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

    const setMismatchOverlayVisible = visible => {
      if (!mismatchOverlay) {
        return;
      }
      mismatchOverlay.hidden = !visible;
      mismatchOverlay.setAttribute('aria-hidden', visible ? 'false' : 'true');
      mismatchOverlay.classList.toggle('active', visible);
      mismatchOverlay.classList.toggle('scan-hidden', !visible);
    };

    const setRecipientPreferenceOverlayVisible = visible => {
      if (!recipientPreferenceOverlay) {
        return;
      }
      recipientPreferenceOverlay.hidden = !visible;
      recipientPreferenceOverlay.setAttribute('aria-hidden', visible ? 'false' : 'true');
      recipientPreferenceOverlay.classList.toggle('active', visible);
      recipientPreferenceOverlay.classList.toggle('scan-hidden', !visible);
    };

    const requestPreassignmentConfirmation = message =>
      new Promise(resolve => {
        if (
          !mismatchOverlay ||
          !mismatchMessage ||
          !mismatchAcceptButton ||
          !mismatchRejectButton
        ) {
          resolve(window.confirm(message));
          return;
        }
        mismatchMessage.textContent = message;
        setMismatchOverlayVisible(true);

        const cleanup = accepted => {
          mismatchAcceptButton.removeEventListener('click', handleAccept);
          mismatchRejectButton.removeEventListener('click', handleReject);
          setMismatchOverlayVisible(false);
          resolve(accepted);
        };

        const handleAccept = () => cleanup(true);
        const handleReject = () => cleanup(false);

        mismatchAcceptButton.addEventListener('click', handleAccept);
        mismatchRejectButton.addEventListener('click', handleReject);
      });

    const requestRecipientPreferenceConfirmation = message =>
      new Promise(resolve => {
        if (
          !recipientPreferenceOverlay ||
          !recipientPreferenceMessage ||
          !recipientPreferenceAcceptButton ||
          !recipientPreferenceRejectButton
        ) {
          resolve(window.confirm(message));
          return;
        }
        recipientPreferenceMessage.textContent = message;
        setRecipientPreferenceOverlayVisible(true);

        const cleanup = accepted => {
          recipientPreferenceAcceptButton.removeEventListener('click', handleAccept);
          recipientPreferenceRejectButton.removeEventListener('click', handleReject);
          setRecipientPreferenceOverlayVisible(false);
          resolve(accepted);
        };

        const handleAccept = () => cleanup(true);
        const handleReject = () => cleanup(false);

        recipientPreferenceAcceptButton.addEventListener('click', handleAccept);
        recipientPreferenceRejectButton.addEventListener('click', handleReject);
      });

    const buildPreassignmentMismatchMessage = (carton, destinationId) => {
      const template =
        shipmentForm?.dataset.preassignmentMismatchTemplate ||
        'Ce colis est déjà affecté pour __EXPECTED__. Souhaitez vous vraiment l\'affecter à cette expédition pour __CURRENT__ ?';
      const expectedLabel =
        carton.preassigned_destination_iata ||
        carton.preassigned_destination_label ||
        carton.code ||
        '';
      const destination = destinationMap.get(String(destinationId));
      const currentLabel =
        (destination && (destination.iata_code || destination.label || destination.city)) || '';
      return template
        .replace('__EXPECTED__', expectedLabel)
        .replace('__CURRENT__', currentLabel);
    };

    const compatibilityBucketLabels = {
      tres_adaptes: 'Tres adapte',
      compatibles: 'Compatible',
      a_eviter: 'A eviter',
      incompatibles: 'Incompatible'
    };

    const buildCartonGroupLabels = recipientPreferenceContext => {
      const destination =
        destinationMap.get(String(recipientPreferenceContext?.destinationId || '')) || null;
      const destinationLabel =
        (destination && (destination.iata_code || destination.label || destination.city)) ||
        'la destination';
      return {
        compatible_preassigned_selected: `1. Compatibles · pré-affectés à ${destinationLabel}`,
        compatible_unassigned: '2. Compatibles · sans pré-affectation',
        compatible_other_destination: '3. Compatibles · pré-affectés ailleurs',
        incompatible: '4. Incompatibles'
      };
    };

    const resolveCartonCompatibilityBucket = (carton, recipientPreferenceContext) => {
      const recipientOrganizationId =
        recipientPreferenceContext && recipientPreferenceContext.recipientOrganizationId;
      if (!recipientOrganizationId) {
        return '';
      }
      const compatibility =
        carton.compatibility_by_recipient_organization_id &&
        carton.compatibility_by_recipient_organization_id[String(recipientOrganizationId)];
      return compatibility && compatibility.bucket ? compatibility.bucket : '';
    };

    const resolveCartonSelectionGroup = (carton, recipientPreferenceContext) => {
      const compatibilityBucket = resolveCartonCompatibilityBucket(
        carton,
        recipientPreferenceContext
      );
      if (compatibilityBucket === 'incompatibles') {
        return {
          key: 'incompatible',
          noteHtml: 'Groupe 4 · incompatible pour ce destinataire'
        };
      }
      const destinationId = String(recipientPreferenceContext?.destinationId || '');
      const preassignedDestinationId = String(carton.preassigned_destination_id || '');
      if (preassignedDestinationId && destinationId && preassignedDestinationId === destinationId) {
        return {
          key: 'compatible_preassigned_selected',
          noteHtml: 'Groupe 1 · compatible et déjà pré-affecté à cette destination'
        };
      }
      if (!preassignedDestinationId) {
        return {
          key: 'compatible_unassigned',
          noteHtml: 'Groupe 2 · compatible sans pré-affectation'
        };
      }
      const otherDestinationIata = carton.preassigned_destination_iata || '';
      return {
        key: 'compatible_other_destination',
        noteHtml: otherDestinationIata
          ? `Groupe 3 · compatible mais pré-affecté à <strong>${otherDestinationIata}</strong>`
          : 'Groupe 3 · compatible mais pré-affecté à une autre destination'
      };
    };

    const buildCartonOptionLabel = (carton, recipientPreferenceContext, selectionGroup) => {
      const baseLabel = carton.weight_g
        ? `${carton.label || carton.code} (${carton.weight_g} g)`
        : carton.label || carton.code;
      const withSource = carton.source_label
        ? `${baseLabel} · ${carton.source_label}`
        : baseLabel;
      const compatibilityBucket = resolveCartonCompatibilityBucket(
        carton,
        recipientPreferenceContext
      );
      const bucketLabel =
        compatibilityBucket
          ? compatibilityBucketLabels[compatibilityBucket] || compatibilityBucket
          : '';
      const mismatchDestinationLabel =
        selectionGroup &&
        selectionGroup.key === 'compatible_other_destination' &&
        carton.preassigned_destination_iata
          ? ` · ${carton.preassigned_destination_iata}`
          : '';
      const labelWithGroup = bucketLabel ? `${withSource} [${bucketLabel}]` : withSource;
      return `${labelWithGroup}${mismatchDestinationLabel}`;
    };

    const getRecipientPreferenceContext = () => {
      const recipientId = document.getElementById('id_recipient_contact')?.value || '';
      const destinationId = document.getElementById('id_destination')?.value || '';
      const recipientContact = recipientContactMap.get(String(recipientId));
      const recipientOrganizationId =
        recipientContact?.recipient_organization_ids_by_destination_id?.[String(destinationId)] ||
        '';
      const refusedProducts =
        recipientContact?.refused_products_by_destination_id?.[String(destinationId)] || [];
      return {
        recipientId: String(recipientId || ''),
        destinationId: String(destinationId || ''),
        recipientOrganizationId: String(recipientOrganizationId || ''),
        refusedProducts,
        refusedProductIds: new Set(refusedProducts.map(product => String(product.id))),
      };
    };

    const updateCartonGroupNote = line => {
      const note = line.querySelector('.shipment-line-group-note');
      const cartonSelect = line.querySelector('.shipment-line-carton');
      if (!note || !cartonSelect || !cartonSelect.value) {
        if (note) {
          note.hidden = true;
          note.innerHTML = '';
        }
        return;
      }
      const carton = cartonMap.get(String(cartonSelect.value));
      if (!carton) {
        note.hidden = true;
        note.innerHTML = '';
        return;
      }
      const selectionGroup = resolveCartonSelectionGroup(
        carton,
        getRecipientPreferenceContext()
      );
      note.innerHTML = selectionGroup.noteHtml || '';
      note.hidden = !note.innerHTML;
    };

    const rebuildCartonSelectOptions = select => {
      const recipientPreferenceContext = getRecipientPreferenceContext();
      const groupLabels = buildCartonGroupLabels(recipientPreferenceContext);
      const selectedValue = select.value || '';
      select.innerHTML = '';
      const defaultOption = document.createElement('option');
      defaultOption.value = '';
      defaultOption.textContent = 'Entrer un produit ou choisir un colis prêt';
      select.appendChild(defaultOption);

      const groups = new Map();
      cartons.forEach(carton => {
        const selectionGroup = resolveCartonSelectionGroup(carton, recipientPreferenceContext);
        let group = groups.get(selectionGroup.key);
        if (!group) {
          group = document.createElement('optgroup');
          group.label = groupLabels[selectionGroup.key];
          group.dataset.shipmentCartonGroup = selectionGroup.key;
          groups.set(selectionGroup.key, group);
          select.appendChild(group);
        }
        const option = document.createElement('option');
        option.value = String(carton.id);
        option.textContent = buildCartonOptionLabel(
          carton,
          recipientPreferenceContext,
          selectionGroup
        );
        option.dataset.shipmentGroupKey = selectionGroup.key;
        if (selectionGroup.key === 'compatible_other_destination') {
          option.style.fontWeight = '700';
        }
        group.appendChild(option);
      });
      select.value = selectedValue;
    };

    const updateCartonOptionLabels = () => {
      container.querySelectorAll('.shipment-line').forEach(line => {
        const select = line.querySelector('.shipment-line-carton');
        if (!select) {
          return;
        }
        rebuildCartonSelectOptions(select);
        updateCartonGroupNote(line);
      });
      updateCartonAvailability();
    };

    const buildRecipientPreferenceCartonMessage = (carton, conflicts) => {
      const productLabels = conflicts.map(product => product.label).join(', ');
      const productNoun = conflicts.length > 1 ? 'ces produits' : 'ce produit';
      return (
        `Attention : le colis ${carton.code} contient ${productLabels}. ` +
        `Le destinataire a indique ne pas vouloir ${productNoun}. ` +
        'Voulez vous continuer ou choisir un autre colis ?'
      );
    };

    const buildRecipientPreferenceProductMessage = product => {
      return (
        `Attention : le destinataire a indique ne pas vouloir ${product.label || product.name}. ` +
        'Voulez vous continuer ou modifier la ligne ?'
      );
    };

    const renderLines = count => {
      const existingValues = readCurrentValues();
      const values = existingValues.length ? existingValues : lineValues;
      container.innerHTML = '';
      if (count < 1) {
        updateTotalWeight();
        updateAllLineMetrics();
        return;
      }
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
        rebuildCartonSelectOptions(cartonSelect);
        cartonSelect.value = lineValue.carton_id || '';

        const productInput = document.createElement('select');
        productInput.name = `line_${index}_product_code`;
        productInput.className = 'shipment-line-product';
        productInput.id = `id_shipment_line_${index}_product_code`;

        const filterInput = document.createElement('input');
        filterInput.type = 'text';
        filterInput.className = 'scan-select-filter';
        filterInput.placeholder = 'Rechercher produit';
        filterInput.setAttribute('autocomplete', 'off');

        const productStack = document.createElement('div');
        productStack.className = 'scan-select-stack';
        productStack.appendChild(filterInput);
        productStack.appendChild(productInput);

        const optionLabel = product =>
          product.brand ? `${product.name} — ${product.brand}` : product.name;

        const rebuildOptions = query => {
          const normalized = normalizeText(query);
          const selectedValue = productInput.value;
          productInput.innerHTML = '';
          const baseOption = document.createElement('option');
          baseOption.value = '';
          baseOption.textContent = '---';
          productInput.appendChild(baseOption);
          productEntries.forEach(product => {
            const label = optionLabel(product);
            if (normalized) {
              const labelNorm = normalizeText(label);
              if (!labelNorm.includes(normalized)) {
                return;
              }
            }
            const option = document.createElement('option');
            option.value = product.codeValue || product.name;
            option.textContent = label;
            productInput.appendChild(option);
          });
          if (selectedValue) {
            productInput.value = selectedValue;
          }
        };

        rebuildOptions('');

        const scanBtn = document.createElement('button');
        scanBtn.type = 'button';
        scanBtn.className = 'scan-scan-btn shipment-line-scan';
        scanBtn.dataset.scanTarget = productInput.id;
        scanBtn.textContent = 'Scan';

        const productWrap = document.createElement('div');
        productWrap.className = 'scan-inline';
        productWrap.appendChild(productStack);
        productWrap.appendChild(scanBtn);

        const quantityInput = document.createElement('input');
        quantityInput.type = 'number';
        quantityInput.name = `line_${index}_quantity`;
        quantityInput.className = 'shipment-line-quantity';
        quantityInput.min = '1';
        quantityInput.step = '1';
        quantityInput.value = lineValue.quantity || '';

        const expiresOnInput = document.createElement('input');
        expiresOnInput.type = 'date';
        expiresOnInput.name = `line_${index}_expires_on`;
        expiresOnInput.className = 'shipment-line-expires-on';
        expiresOnInput.value = lineValue.expires_on || '';

        const mismatchConfirmedInput = document.createElement('input');
        mismatchConfirmedInput.type = 'hidden';
        mismatchConfirmedInput.name = `line_${index}_preassigned_destination_confirmed`;
        mismatchConfirmedInput.className = 'shipment-line-preassigned-confirmed';
        const preferenceOverrideConfirmedInput = document.createElement('input');
        preferenceOverrideConfirmedInput.type = 'hidden';
        preferenceOverrideConfirmedInput.name = `line_${index}_recipient_preference_override_confirmed`;
        preferenceOverrideConfirmedInput.className = 'shipment-line-recipient-preference-confirmed';

        grid.appendChild(buildField('Colis prepare', cartonSelect));
        const productField = buildField('Produit', productWrap);
        productField.classList.add('shipment-line-product-field');
        const quantityField = buildField('Quantite', quantityInput);
        quantityField.classList.add('shipment-line-quantity-field');
        const expiresField = buildField('Date de peremption', expiresOnInput);
        expiresField.classList.add('shipment-line-expires-field');
        grid.appendChild(productField);
        grid.appendChild(quantityField);
        grid.appendChild(expiresField);

        const metrics = document.createElement('div');
        metrics.className = 'shipment-line-metrics';
        metrics.innerHTML =
          '<div>Max carton mono-produit (40x30x30cm): <span class="shipment-line-max">-</span></div>' +
          '<div>Equivalent cartons (40x30x30cm): <span class="shipment-line-equivalent">-</span></div>' +
          '<div>Quantite disponible en stock: <span class="shipment-line-available">-</span></div>' +
          '<div>Quantite restante apres preparation: <span class="shipment-line-remaining">-</span></div>';
        grid.appendChild(metrics);
        line.appendChild(grid);
        const cartonGroupNote = document.createElement('div');
        cartonGroupNote.className = 'shipment-line-group-note';
        cartonGroupNote.hidden = true;
        line.appendChild(cartonGroupNote);
        line.appendChild(mismatchConfirmedInput);
        line.appendChild(preferenceOverrideConfirmedInput);

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
          updateCartonGroupNote(line);
          updateTotalWeight();
          updateCartonAvailability();
          updateAllLineMetrics();
        });
        if (lineValue.product_code) {
          const initialMatch = findProductMatch(lineValue.product_code);
          if (initialMatch && initialMatch.codeValue) {
            productInput.value = initialMatch.codeValue;
            filterInput.value = optionLabel(initialMatch);
          } else {
            productInput.value = lineValue.product_code;
            filterInput.value = lineValue.product_code;
          }
        }

        filterInput.addEventListener('input', event => {
          rebuildOptions(event.target.value);
        });

        productInput.addEventListener('change', () => {
          if (productInput.value || quantityInput.value) {
            cartonSelect.value = '';
          }
          syncLineState(line);
          updateCartonGroupNote(line);
          updateTotalWeight();
          updateCartonAvailability();
          if (productInput.value) {
            const match = findProductMatch(productInput.value);
            if (match) {
              filterInput.value = optionLabel(match);
            }
          }
          updateAllLineMetrics();
        });
        quantityInput.addEventListener('input', () => {
          if (productInput.value || quantityInput.value) {
            cartonSelect.value = '';
          }
          syncLineState(line);
          updateCartonGroupNote(line);
          updateTotalWeight();
          updateCartonAvailability();
          updateAllLineMetrics();
        });
        expiresOnInput.addEventListener('input', () => {
          if (productInput.value || quantityInput.value || expiresOnInput.value) {
            cartonSelect.value = '';
          }
          syncLineState(line);
          updateCartonGroupNote(line);
          updateTotalWeight();
          updateCartonAvailability();
          updateAllLineMetrics();
        });

        syncLineState(line);
        updateCartonGroupNote(line);
        container.appendChild(line);
      }
      updateCartonAvailability();
      updateCartonOptionLabels();
      updateTotalWeight();
      updateAllLineMetrics();
    };

    let lastShipmentSubmitter = null;
    if (shipmentForm) {
      shipmentForm
        .querySelectorAll('button[type="submit"], input[type="submit"]')
        .forEach(button => {
          button.addEventListener('click', () => {
            lastShipmentSubmitter = button;
          });
        });

      shipmentForm.addEventListener('submit', async event => {
        const submitter = event.submitter || lastShipmentSubmitter;
        const submitterAction =
          submitter && submitter.name === 'action' ? submitter.value : '';
        if (submitterAction === 'save_draft' || submitterAction === 'save_draft_pack') {
          return;
        }
        const destinationId = document.getElementById('id_destination')?.value || '';
        if (!destinationId) {
          return;
        }
        const recipientPreferenceContext = getRecipientPreferenceContext();

        const mismatches = [];
        const preferenceMismatches = [];
        container.querySelectorAll('.shipment-line').forEach(line => {
          const confirmInput = line.querySelector('.shipment-line-preassigned-confirmed');
          const preferenceConfirmInput = line.querySelector(
            '.shipment-line-recipient-preference-confirmed'
          );
          if (confirmInput) {
            confirmInput.value = '';
          }
          if (preferenceConfirmInput) {
            preferenceConfirmInput.value = '';
          }
          const cartonId = line.querySelector('.shipment-line-carton')?.value || '';
          if (cartonId) {
            const carton = cartonMap.get(cartonId);
            const preassignedDestinationId =
              carton && carton.preassigned_destination_id
                ? String(carton.preassigned_destination_id)
                : '';
            if (preassignedDestinationId && preassignedDestinationId !== String(destinationId)) {
              mismatches.push({ carton, confirmInput, destinationId });
            }
            if (
              carton &&
              recipientPreferenceContext.refusedProductIds.size &&
              Array.isArray(carton.product_rows)
            ) {
              const conflicts = carton.product_rows.filter(product =>
                recipientPreferenceContext.refusedProductIds.has(String(product.id))
              );
              if (conflicts.length) {
                preferenceMismatches.push({
                  type: 'carton',
                  carton,
                  conflicts,
                  confirmInput: preferenceConfirmInput
                });
              }
            }
            return;
          }
          if (!recipientPreferenceContext.refusedProductIds.size) {
            return;
          }
          const productValue = line.querySelector('.shipment-line-product')?.value || '';
          const product = findProductMatch(productValue);
          if (!product || !recipientPreferenceContext.refusedProductIds.has(String(product.id))) {
            return;
          }
          preferenceMismatches.push({
            type: 'product',
            product,
            confirmInput: preferenceConfirmInput
          });
        });

        if (!mismatches.length && !preferenceMismatches.length) {
          return;
        }

        event.preventDefault();
        for (const mismatch of mismatches) {
          const accepted = await requestPreassignmentConfirmation(
            buildPreassignmentMismatchMessage(mismatch.carton, mismatch.destinationId)
          );
          if (!accepted) {
            return;
          }
          if (mismatch.confirmInput) {
            mismatch.confirmInput.value = '1';
          }
        }

        for (const mismatch of preferenceMismatches) {
          const accepted = await requestRecipientPreferenceConfirmation(
            mismatch.type === 'carton'
              ? buildRecipientPreferenceCartonMessage(mismatch.carton, mismatch.conflicts)
              : buildRecipientPreferenceProductMessage(mismatch.product)
          );
          if (!accepted) {
            return;
          }
          if (mismatch.confirmInput) {
            mismatch.confirmInput.value = '1';
          }
        }

        lastShipmentSubmitter = null;
        shipmentForm.submit();
      });
    }

    const resolveCount = value => {
      if (isPreparingWithoutCartons()) {
        return 0;
      }
      const parsed = parseInt(value, 10);
      if (!Number.isFinite(parsed) || parsed < 1) {
        return 1;
      }
      return parsed;
    };

    const syncShipmentCreationMode = () => {
      const withoutCartons = isPreparingWithoutCartons();
      if (plannedCartonCountField) {
        plannedCartonCountField.hidden = !withoutCartons;
        plannedCartonCountField.classList.toggle('scan-hidden', !withoutCartons);
      }
      if (withCartonsFields) {
        withCartonsFields.hidden = withoutCartons;
        withCartonsFields.classList.toggle('scan-hidden', withoutCartons);
      }
      if (withoutCartons) {
        const currentValues = readCurrentValues();
        if (currentValues.length) {
          lineValues = currentValues;
        }
        renderLines(0);
        return;
      }
      renderLines(resolveCount(countInput ? countInput.value : lineValues.length || 1));
    };

    const initialCount = resolveCount(countInput ? countInput.value : 1);
    renderLines(initialCount);
    syncShipmentCreationMode();
    creationModeInputs.forEach(input => {
      input.addEventListener('change', syncShipmentCreationMode);
    });

    const destinationSelect = document.getElementById('id_destination');
    const recipientSelect = document.getElementById('id_recipient_contact');
    if (destinationSelect) {
      destinationSelect.addEventListener('change', updateCartonOptionLabels);
    }
    if (recipientSelect) {
      recipientSelect.addEventListener('change', updateCartonOptionLabels);
    }

    if (countInput) {
      const handleCountChange = event => {
        const nextCount = resolveCount(event.target.value);
        if (nextCount > 0) {
          event.target.value = String(nextCount);
        }
        renderLines(nextCount);
      };
      countInput.addEventListener('input', handleCountChange);
      countInput.addEventListener('change', handleCountChange);
    }
  }

  function setupShipmentContactFilters() {
    const shipmentForm = document.getElementById('shipment-form');
    const destinationSelect = document.getElementById('id_destination');
    const shipperSelect = document.getElementById('id_shipper_contact');
    const recipientSelect = document.getElementById('id_recipient_contact');
    const correspondentSelect = document.getElementById('id_correspondent_contact');
    const shipperSection = document.getElementById('shipment-shipper-section');
    const recipientSection = document.getElementById('shipment-recipient-section');
    const correspondentSection = document.getElementById('shipment-correspondent-section');
    const detailsSection = document.getElementById('shipment-details-section');
    const shipperEmptyMessage = document.getElementById('shipper-empty-message');
    const recipientEmptyMessage = document.getElementById('recipient-empty-message');
    const correspondentEmptyMessage = document.getElementById('correspondent-empty-message');
    const correspondentSelectWrap = document.getElementById('shipment-correspondent-select-wrap');
    const correspondentSingle = document.getElementById('shipment-correspondent-single');
    const destinationsEl = document.getElementById('destination-data');
    const shippersEl = document.getElementById('shipper-contacts-data');
    const recipientsEl = document.getElementById('recipient-contacts-data');
    const correspondentsEl = document.getElementById('correspondent-contacts-data');

    if (
      !destinationSelect ||
      !shipperSelect ||
      !recipientSelect ||
      !correspondentSelect ||
      !destinationsEl
    ) {
      return;
    }

    let destinations = [];
    let shippers = [];
    let recipients = [];
    let correspondents = [];

    const normalizeEntries = value => {
      if (Array.isArray(value)) {
        return value;
      }
      if (value && typeof value === 'object') {
        return Object.values(value);
      }
      return [];
    };

    try {
      destinations = normalizeEntries(JSON.parse(destinationsEl.textContent || '[]'));
    } catch (err) {
      destinations = [];
    }
    try {
      shippers = normalizeEntries(
        JSON.parse(shippersEl ? shippersEl.textContent || '[]' : '[]')
      );
    } catch (err) {
      shippers = [];
    }
    try {
      recipients = normalizeEntries(
        JSON.parse(recipientsEl ? recipientsEl.textContent || '[]' : '[]')
      );
    } catch (err) {
      recipients = [];
    }
    try {
      correspondents = normalizeEntries(
        JSON.parse(correspondentsEl ? correspondentsEl.textContent || '[]' : '[]')
      );
    } catch (err) {
      correspondents = [];
    }

    const asId = value => (value || value === 0 ? String(value).trim() : '');
    const shipperSelectorGuidance =
      (shipmentForm && shipmentForm.dataset.shipperSelectorGuidance) ||
      "Si l'expéditeur souhaité n'apparait pas ici, vérifier la page Gestion -> Contact pour créer/modifier/ajouter un trio expéditeur - destinataire - destination";
    const recipientSelectorGuidance =
      (shipmentForm && shipmentForm.dataset.recipientSelectorGuidance) ||
      "Si le destinataire souhaité n'apparait pas ici, vérifier la page Gestion -> Contact pour créer/modifier/ajouter un trio expéditeur - destinataire - destination";
    const selectValue = select => asId(select && select.value ? select.value : '');
    const asIdList = values =>
      Array.isArray(values)
        ? values
            .map(entry => asId(entry))
            .filter(Boolean)
        : [];
    const setVisible = (element, visible) => {
      if (!element) {
        return;
      }
      element.classList.toggle('scan-hidden', !visible);
      element.hidden = !visible;
    };

    const destinationMap = new Map(
      destinations.map(destination => [String(destination.id), destination])
    );
    const correspondentsById = new Map(
      correspondents
        .map(correspondent => [asId(correspondent && correspondent.id), correspondent])
        .filter(([correspondentId]) => Boolean(correspondentId))
    );
    const allCorrespondentIds = new Set(correspondentsById.keys());
    const matchesExplicitDestination = (contact, destinationId) => {
      if (!contact || !destinationId) {
        return false;
      }
      const explicitDestinationIds = asIdList(contact.allowed_destination_ids);
      if (!explicitDestinationIds.length) {
        return false;
      }
      return explicitDestinationIds.includes(String(destinationId));
    };
    const matchesDestination = (contact, destinationId) => {
      if (!contact || !destinationId) {
        return false;
      }
      const scopedDestinationIds = asIdList(contact.allowed_destination_ids);
      if (scopedDestinationIds.length) {
        return scopedDestinationIds.includes(String(destinationId));
      }
      if (contact.default_destination_id) {
        return String(contact.default_destination_id) === String(destinationId);
      }
      return true;
    };
    const matchesRecipientPair = (recipient, shipperId, destinationId) => {
      if (!recipient || !shipperId || !destinationId) {
        return false;
      }
      const bindingPairs = Array.isArray(recipient.binding_pairs)
        ? recipient.binding_pairs
        : [];
      if (!bindingPairs.length) {
        return false;
      }
      return bindingPairs.some(
        pair =>
          asId(pair && pair.shipper_id) === String(shipperId) &&
          asId(pair && pair.destination_id) === String(destinationId)
      );
    };
    const sortUniqueOptions = options => {
      const uniqueOptionsById = new Map();
      options.forEach(option => {
        const optionId = asId(option && option.id);
        if (!optionId || uniqueOptionsById.has(optionId)) {
          return;
        }
        uniqueOptionsById.set(optionId, option);
      });
      return [...uniqueOptionsById.values()].sort((left, right) =>
        String(left.name || '').localeCompare(String(right.name || ''), 'fr', {
          sensitivity: 'base'
        })
      );
    };

    const renderOptions = (select, options, selectedValue) => {
      const normalizedOptions = sortUniqueOptions(options).map(option => ({
        ...option,
        disabled: Boolean(option && option.disabled)
      }));
      const fragment = document.createDocumentFragment();
      const empty = document.createElement('option');
      empty.value = '';
      empty.textContent = '---';
      fragment.appendChild(empty);

      const optionIds = new Set();
      const enabledOptionIds = new Set();
      normalizedOptions.forEach(option => {
        const optionEl = document.createElement('option');
        optionEl.value = String(option.id);
        optionEl.textContent = option.name;
        optionEl.disabled = Boolean(option.disabled);
        fragment.appendChild(optionEl);
        optionIds.add(String(option.id));
        if (!option.disabled) {
          enabledOptionIds.add(String(option.id));
        }
      });
      select.innerHTML = '';
      select.appendChild(fragment);
      if (selectedValue && optionIds.has(String(selectedValue))) {
        select.value = String(selectedValue);
      } else {
        select.value = '';
      }
      return {
        optionIds,
        enabledOptionIds,
        options: normalizedOptions
      };
    };

    const renderGroupedOptions = (select, groups, selectedValue) => {
      const fragment = document.createDocumentFragment();
      const empty = document.createElement('option');
      empty.value = '';
      empty.textContent = '---';
      fragment.appendChild(empty);

      const optionIds = new Set();
      const enabledOptionIds = new Set();
      const renderedOptions = [];
      let hasVisibleGroup = false;

      groups.forEach(group => {
        const groupOptions = Array.isArray(group)
          ? group
          : Array.isArray(group && group.options)
            ? group.options
            : [];
        const groupMessage = Array.isArray(group)
          ? ''
          : String((group && group.message) || '').trim();
        const visibleOptions = sortUniqueOptions(groupOptions)
          .map(option => ({
            ...option,
            disabled: Boolean(option && option.disabled)
          }))
          .filter(option => !optionIds.has(String(option.id)));
        if (!visibleOptions.length && !groupMessage) {
          return;
        }
        if (hasVisibleGroup) {
          const separator = document.createElement('option');
          separator.value = '';
          separator.textContent = '------';
          separator.disabled = true;
          fragment.appendChild(separator);
        }
        if (groupMessage) {
          const messageOption = document.createElement('option');
          messageOption.value = '';
          messageOption.textContent = groupMessage;
          messageOption.disabled = true;
          fragment.appendChild(messageOption);
          hasVisibleGroup = true;
          return;
        }
        visibleOptions.forEach(option => {
          const optionEl = document.createElement('option');
          optionEl.value = String(option.id);
          optionEl.textContent = option.name;
          optionEl.disabled = Boolean(option.disabled);
          fragment.appendChild(optionEl);
          optionIds.add(String(option.id));
          if (!option.disabled) {
            enabledOptionIds.add(String(option.id));
          }
          renderedOptions.push(option);
        });
        hasVisibleGroup = true;
      });

      select.innerHTML = '';
      select.appendChild(fragment);
      if (selectedValue && optionIds.has(String(selectedValue))) {
        select.value = String(selectedValue);
      } else {
        select.value = '';
      }
      return {
        optionIds,
        enabledOptionIds,
        options: renderedOptions
      };
    };

    const decorateOption = (option, extra = {}) => ({
      ...option,
      ...extra
    });

    const isPriorityShipper = shipper =>
      Boolean(shipper && shipper.is_priority_shipper);

    const buildCorrespondentRecipientLabel = (correspondentId, destinationId) => {
      const correspondent = correspondentsById.get(asId(correspondentId));
      if (!correspondent) {
        return '';
      }
      const labelsByDestinationId =
        correspondent.recipient_labels_by_destination_id || {};
      return labelsByDestinationId[String(destinationId)] || correspondent.name || '';
    };

    const isHiddenCorrespondentRecipient = (
      recipient,
      destinationCorrespondentRecipientId
    ) => {
      const recipientId = asId(recipient && recipient.id);
      if (!recipientId || !allCorrespondentIds.has(recipientId)) {
        return false;
      }
      return recipientId !== destinationCorrespondentRecipientId;
    };

    const renderShipperOptions = (select, destinationId, selectedValue) => {
      const priorityOptions = shippers
        .filter(shipper => isPriorityShipper(shipper))
        .map(shipper =>
          decorateOption(shipper, {
            disabled: !matchesExplicitDestination(shipper, destinationId)
          })
        );
      const destinationOptions = shippers
        .filter(
          shipper =>
            !isPriorityShipper(shipper) && matchesExplicitDestination(shipper, destinationId)
        )
        .map(shipper => decorateOption(shipper));
      return renderGroupedOptions(
        select,
        [
          { options: priorityOptions },
          { options: destinationOptions },
          { message: shipperSelectorGuidance }
        ],
        selectedValue
      );
    };

    const setCorrespondentSingleDisplay = option => {
      const hasSingleOption = Boolean(option);
      if (correspondentSelectWrap) {
        correspondentSelectWrap.classList.toggle('scan-hidden', hasSingleOption);
        correspondentSelectWrap.hidden = hasSingleOption;
      }
      if (correspondentSingle) {
        correspondentSingle.textContent = hasSingleOption ? option.name : '';
        correspondentSingle.classList.toggle('scan-hidden', !hasSingleOption);
        correspondentSingle.hidden = !hasSingleOption;
      }
    };

    const updateContacts = () => {
      const destinationId = selectValue(destinationSelect);
      const selectedShipper = selectValue(shipperSelect);
      const selectedRecipient = selectValue(recipientSelect);
      const selectedCorrespondent = selectValue(correspondentSelect);

      if (!destinationId) {
        renderOptions(shipperSelect, [], '');
        renderOptions(recipientSelect, [], '');
        renderOptions(correspondentSelect, [], '');
        setCorrespondentSingleDisplay(null);
        setVisible(shipperSection, false);
        setVisible(recipientSection, false);
        setVisible(correspondentSection, false);
        setVisible(detailsSection, false);
        setVisible(shipperEmptyMessage, false);
        setVisible(recipientEmptyMessage, false);
        setVisible(correspondentEmptyMessage, false);
        return;
      }

      setVisible(shipperSection, true);
      const destination = destinationMap.get(destinationId) || null;
      const shipperRender = renderShipperOptions(
        shipperSelect,
        destinationId,
        selectedShipper
      );
      const resolvedShipper = selectValue(shipperSelect);
      const resolvedShipperEntry =
        shippers.find(shipper => asId(shipper.id) === resolvedShipper) || null;
      const resolvedShipperOrgId = asId(
        resolvedShipperEntry &&
          (resolvedShipperEntry.organization_id || resolvedShipperEntry.id)
      );
      setVisible(shipperEmptyMessage, shipperRender.enabledOptionIds.size === 0);

      const canShowRecipientAndCorrespondent = Boolean(resolvedShipper);
      setVisible(recipientSection, canShowRecipientAndCorrespondent);
      setVisible(correspondentSection, canShowRecipientAndCorrespondent);

      let recipientOptions = [];
      let correspondentOptions = [];
      if (canShowRecipientAndCorrespondent) {
        const destinationCorrespondentRecipientId = asId(
          destination && destination.correspondent_contact_id
        );
        const destinationRecipients = recipients.filter(recipient =>
          matchesDestination(recipient, destinationId) &&
          !isHiddenCorrespondentRecipient(
            recipient,
            destinationCorrespondentRecipientId
          )
        );
        const isRecipientPairMatched = recipient =>
          matchesRecipientPair(recipient, resolvedShipperOrgId, destinationId);
        const priorityRecipientOptions = destinationRecipients
          .filter(
            recipient => asId(recipient.id) === destinationCorrespondentRecipientId
          )
          .map(recipient =>
            decorateOption(recipient, {
              name:
                buildCorrespondentRecipientLabel(recipient.id, destinationId) ||
                recipient.name,
              disabled: !isRecipientPairMatched(recipient)
            })
          );
        const pairRecipientOptions = destinationRecipients
          .filter(
            recipient =>
              asId(recipient.id) !== destinationCorrespondentRecipientId &&
              isRecipientPairMatched(recipient)
          )
          .map(recipient => decorateOption(recipient));
        recipientOptions = [
          { options: priorityRecipientOptions },
          { options: pairRecipientOptions },
          { message: recipientSelectorGuidance }
        ];
        correspondentOptions = correspondents.filter(correspondent =>
          matchesDestination(correspondent, destinationId)
        );
        if (destination && destination.correspondent_contact_id) {
          correspondentOptions = correspondentOptions.filter(
            correspondent =>
              String(correspondent.id) === String(destination.correspondent_contact_id)
          );
        } else {
          correspondentOptions = [];
        }
      }

      const recipientRender = renderGroupedOptions(
        recipientSelect,
        recipientOptions,
        selectedRecipient
      );
      const correspondentRender = renderOptions(
        correspondentSelect,
        correspondentOptions,
        selectedCorrespondent
      );
      const singleCorrespondentOption =
        correspondentRender.options.length === 1 ? correspondentRender.options[0] : null;
      if (singleCorrespondentOption) {
        correspondentSelect.value = String(singleCorrespondentOption.id);
      }
      setCorrespondentSingleDisplay(singleCorrespondentOption);
      setVisible(
        recipientEmptyMessage,
        canShowRecipientAndCorrespondent && recipientRender.enabledOptionIds.size === 0
      );
      setVisible(
        correspondentEmptyMessage,
        canShowRecipientAndCorrespondent && correspondentRender.enabledOptionIds.size === 0
      );

      const canShowDetails =
        canShowRecipientAndCorrespondent &&
        Boolean(selectValue(recipientSelect)) &&
        Boolean(selectValue(correspondentSelect));
      setVisible(detailsSection, canShowDetails);
    };

    const isEditMode = shipmentForm && shipmentForm.dataset.shipmentEdit === '1';
    const isBoundForm = shipmentForm && shipmentForm.dataset.formBound === '1';
    if (!isEditMode && !isBoundForm) {
      shipperSelect.value = '';
      recipientSelect.value = '';
      correspondentSelect.value = '';
    }

    destinationSelect.addEventListener('change', updateContacts);
    shipperSelect.addEventListener('change', updateContacts);
    recipientSelect.addEventListener('change', updateContacts);
    correspondentSelect.addEventListener('change', updateContacts);
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
          ean: product.ean || '',
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
      match = products.find(product => product.ean && product.ean.toLowerCase() === codeLower);
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
        scanButton.textContent = 'Scanner un code barre ou QR Code';
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

  function setupTableTools() {
    const tableToolsCore = window.WmsTableToolsCore;
    if (!tableToolsCore) {
      return;
    }
    const tables = Array.from(
      document.querySelectorAll('table.scan-table[data-table-tools="1"]')
    );
    if (!tables.length) {
      return;
    }

    const {
      cleanText,
      compareCellValues,
      extractCellText,
      normalizeText: normalizeTableText
    } = tableToolsCore;
    const normalizedFilterText = value => normalizeTableText(cleanText(value));

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
      const headerCount = headerCells.length;
      if (!headerCount) {
        return;
      }

      const groups = [];
      let currentGroup = null;
      Array.from(tbody.rows).forEach(row => {
        const isPrimaryRow = row.cells.length === headerCount;
        if (isPrimaryRow || !currentGroup) {
          currentGroup = {
            primary: row,
            extras: [],
            originalIndex: groups.length
          };
          groups.push(currentGroup);
          return;
        }
        currentGroup.extras.push(row);
      });

      if (!groups.length) {
        return;
      }

      let sortColumn = -1;
      let sortDirection = 0;
      const filterInputs = [];

      const getGroupValue = (group, columnIndex) =>
        extractCellText(group.primary.cells[columnIndex]);

      const updateHeaderState = () => {
        headerCells.forEach((cell, index) => {
          const isSorted = index === sortColumn && sortDirection !== 0;
          cell.classList.toggle('is-sorted', isSorted);
          cell.classList.toggle('is-desc', isSorted && sortDirection < 0);
          if (!isSorted) {
            cell.setAttribute('aria-sort', 'none');
          } else {
            cell.setAttribute('aria-sort', sortDirection > 0 ? 'ascending' : 'descending');
          }
        });
      };

      const applyTools = () => {
        const orderedGroups = [...groups];
        if (sortColumn >= 0 && sortDirection !== 0) {
          orderedGroups.sort((leftGroup, rightGroup) => {
            const compareResult = compareCellValues(
              getGroupValue(leftGroup, sortColumn),
              getGroupValue(rightGroup, sortColumn)
            );
            if (compareResult === 0) {
              return leftGroup.originalIndex - rightGroup.originalIndex;
            }
            return compareResult * sortDirection;
          });
        } else {
          orderedGroups.sort((leftGroup, rightGroup) => leftGroup.originalIndex - rightGroup.originalIndex);
        }

        orderedGroups.forEach(group => {
          tbody.appendChild(group.primary);
          group.extras.forEach(extra => tbody.appendChild(extra));
        });

        const filters = filterInputs.map(input => normalizedFilterText(input.value));
        orderedGroups.forEach(group => {
          const keep = filters.every((term, columnIndex) => {
            if (!term) {
              return true;
            }
            return normalizedFilterText(getGroupValue(group, columnIndex)).includes(term);
          });
          const displayValue = keep ? '' : 'none';
          group.primary.style.display = displayValue;
          group.extras.forEach(extra => {
            extra.style.display = displayValue;
          });
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
        input.setAttribute('aria-label', `Filtrer ${cleanText(cell.textContent) || 'colonne'}`);
        input.addEventListener('input', applyTools);
        filterInputs.push(input);
        filterCell.appendChild(input);
        filterRow.appendChild(filterCell);
      });
      thead.appendChild(filterRow);

      applyTools();
    });
  }

  function setupAdminContactsCrud() {
    const root = document.querySelector('[data-admin-contacts-crud="1"]');
    if (!root) {
      return;
    }

    const contactForm = root.querySelector('[data-admin-contact-form="1"]');
    const businessField = contactForm
      ? contactForm.querySelector('[name="business_type"]')
      : null;
    const entityField = contactForm
      ? contactForm.querySelector('[name="entity_type"]')
      : null;
    const entityWrapper = contactForm
      ? contactForm.querySelector('[data-contact-entity-wrapper="1"]')
      : null;

    const lockedEntityTypes = {
      shipper: 'organization',
      recipient: 'organization',
      correspondent: 'organization',
      volunteer: 'person'
    };

    const resolveContactEntityType = businessType => {
      const forcedEntityType = lockedEntityTypes[businessType];
      if (forcedEntityType) {
        if (entityField) {
          entityField.value = forcedEntityType;
        }
        return forcedEntityType;
      }
      return entityField && entityField.value ? entityField.value : '';
    };

    const resolveRequiredFields = (businessType, entityType) => {
      const required = new Set();
      if (['shipper', 'recipient', 'correspondent'].includes(businessType)) {
        required.add('organization_name');
        required.add('first_name');
        required.add('last_name');
      }
      if (businessType === 'recipient' || businessType === 'correspondent') {
        required.add('destination_id');
      }
      if (businessType === 'recipient') {
        required.add('allowed_shipper_ids');
        required.add('legal_form');
        required.add('beneficiary_count');
      }
      if (businessType === 'volunteer') {
        required.add('first_name');
        required.add('last_name');
      }
      if (['donor', 'transporter', 'partner', 'other'].includes(businessType)) {
        required.add('entity_type');
        if (entityType === 'person') {
          required.add('first_name');
          required.add('last_name');
        } else if (entityType === 'organization') {
          required.add('organization_name');
        }
      }
      return required;
    };

    const splitDatasetValues = value =>
      String(value || '')
        .split(',')
        .map(item => item.trim())
        .filter(Boolean);

    const oppositeDuplicateChoice = value => {
      if (value === 'existing') {
        return 'new';
      }
      if (value === 'new') {
        return 'existing';
      }
      return '';
    };

    const buildDuplicateExplanation = ({
      actionValue,
      keepValue,
      existingLabel,
      newLabel,
      duplicateName
    }) => {
      const keepLabel = keepValue === 'new' ? newLabel : existingLabel;
      const deleteLabel = keepValue === 'new' ? existingLabel : newLabel;
      if (actionValue === 'merge') {
        return `Les données vides de la fiche ${keepLabel} seront complétées par celles de la fiche ${deleteLabel} lorsqu'elles sont disponibles. La fiche ${deleteLabel} sera ensuite supprimée.`;
      }
      if (actionValue === 'replace') {
        return `La fiche ${keepLabel} sera conservée et la fiche ${deleteLabel} sera supprimée.`;
      }
      if (actionValue === 'duplicate') {
        return `La fiche ${existingLabel} sera conservée. Une nouvelle fiche ${newLabel} sera créée avec un suffixe " - doublon", par exemple "${duplicateName}".`;
      }
      return 'Choisissez une action pour afficher son explication détaillée.';
    };

    const syncDuplicateReviewState = container => {
      const actionSelect = container.querySelector('[data-duplicate-action="1"]');
      if (!actionSelect) {
        return;
      }
      const targetGroups = container.querySelectorAll('[data-duplicate-target-group="1"]');
      const keepDeleteGroups = container.querySelectorAll('[data-duplicate-keep-delete-group="1"]');
      const keepSelect = container.querySelector('[data-duplicate-keep-choice="1"]');
      const deleteSelect = container.querySelector('[data-duplicate-delete-choice="1"]');
      const explanation = container.querySelector('[data-duplicate-explanation="1"]');
      const targetSelect = container.querySelector('[data-duplicate-target-select="1"]');
      const alwaysShowTarget = container.dataset.duplicateAlwaysShowTarget === '1';
      const needsTarget = ['replace', 'merge'].includes(actionSelect.value);
      targetGroups.forEach(group => {
        group.hidden = !(alwaysShowTarget || needsTarget);
      });
      keepDeleteGroups.forEach(group => {
        group.hidden = !needsTarget;
      });
      if (keepSelect && deleteSelect) {
        if (!keepSelect.value && deleteSelect.value) {
          keepSelect.value = oppositeDuplicateChoice(deleteSelect.value);
        }
        if (!deleteSelect.value && keepSelect.value) {
          deleteSelect.value = oppositeDuplicateChoice(keepSelect.value);
        }
      }
      if (explanation) {
        const selectedOption = targetSelect?.selectedOptions?.[0];
        const existingLabel =
          selectedOption?.dataset?.duplicateLabel ||
          selectedOption?.textContent?.trim() ||
          'la fiche déjà présente';
        const newLabel = container.dataset.duplicateNewLabel || 'le nouvel ajout';
        const duplicateName =
          container.dataset.duplicateNewDuplicateName || `${newLabel} - doublon`;
        explanation.textContent = buildDuplicateExplanation({
          actionValue: actionSelect.value,
          keepValue: keepSelect?.value || 'existing',
          existingLabel,
          newLabel,
          duplicateName
        });
      }
    };

    const managedRequiredFieldNames = [
      'entity_type',
      'organization_name',
      'first_name',
      'last_name',
      'destination_id',
      'allowed_shipper_ids',
      'legal_form',
      'beneficiary_count'
    ];

    const setSectionFieldsDisabled = (section, shouldHide) => {
      section.querySelectorAll('input, select, textarea').forEach(field => {
        if (field.type === 'hidden') {
          return;
        }
        field.disabled = shouldHide;
      });
    };

    const syncManagedRequiredState = requiredFields => {
      managedRequiredFieldNames.forEach(fieldName => {
        contactForm.querySelectorAll(`[name="${fieldName}"]`).forEach(field => {
          if (field.type === 'hidden') {
            return;
          }
          field.required = requiredFields.has(fieldName) && !field.disabled;
        });
      });
    };

    const applyContactFieldVisibility = () => {
      if (!contactForm || !businessField) {
        return;
      }
      const businessType = businessField.value || '';
      const entityType = resolveContactEntityType(businessType);
      const detailsReady = Boolean(businessType) && Boolean(entityType);

      if (entityField) {
        entityField.disabled = Boolean(lockedEntityTypes[businessType]);
      }
      if (entityWrapper) {
        entityWrapper.hidden = false;
      }

      contactForm.querySelectorAll('[data-contact-stage="details"]').forEach(section => {
        section.hidden = !detailsReady;
        setSectionFieldsDisabled(section, !detailsReady);
      });

      if (!detailsReady) {
        syncManagedRequiredState(new Set());
        contactForm.querySelectorAll('[data-required-marker]').forEach(marker => {
          marker.hidden = marker.dataset.requiredMarker !== 'entity_type';
        });
        syncDuplicateReviewState(contactForm);
        return;
      }

      contactForm
        .querySelectorAll('[data-contact-field-group], [data-contact-businesses], [data-contact-entities]')
        .forEach(section => {
          const supportedBusinesses = splitDatasetValues(section.dataset.contactBusinesses);
          const supportedEntities = splitDatasetValues(section.dataset.contactEntities);
          const fieldGroup = section.dataset.contactFieldGroup || '';
          const matchesBusiness =
            !supportedBusinesses.length || supportedBusinesses.includes(businessType);
          let matchesEntity =
            !supportedEntities.length || supportedEntities.includes(entityType);
          if (fieldGroup === 'person' && ['donor', 'transporter', 'partner', 'other'].includes(businessType)) {
            matchesEntity = entityType === 'person';
          }
          const shouldHide = !(matchesBusiness && matchesEntity);
          section.hidden = shouldHide;
          setSectionFieldsDisabled(section, shouldHide);
        });

      const requiredFields = resolveRequiredFields(businessType, entityType);
      syncManagedRequiredState(requiredFields);
      contactForm.querySelectorAll('[data-required-marker]').forEach(marker => {
        marker.hidden = !requiredFields.has(marker.dataset.requiredMarker);
      });

      syncDuplicateReviewState(contactForm);
    };

    if (contactForm && businessField) {
      businessField.addEventListener('change', applyContactFieldVisibility);
      if (entityField) {
        entityField.addEventListener('change', applyContactFieldVisibility);
      }
      applyContactFieldVisibility();
    }

    root
      .querySelectorAll('form, [data-duplicate-review-root="1"]')
      .forEach(container => {
      const duplicateActionSelect = container.querySelector('[data-duplicate-action="1"]');
      if (!duplicateActionSelect) {
        return;
      }
      duplicateActionSelect.addEventListener('change', () => {
        syncDuplicateReviewState(container);
      });
      container.querySelector('[data-duplicate-target-select="1"]')?.addEventListener('change', () => {
        syncDuplicateReviewState(container);
      });
      const keepSelect = container.querySelector('[data-duplicate-keep-choice="1"]');
      const deleteSelect = container.querySelector('[data-duplicate-delete-choice="1"]');
      if (keepSelect && deleteSelect) {
        keepSelect.addEventListener('change', () => {
          const opposite = oppositeDuplicateChoice(keepSelect.value);
          if (opposite && deleteSelect.value !== opposite) {
            deleteSelect.value = opposite;
          }
          syncDuplicateReviewState(container);
        });
        deleteSelect.addEventListener('change', () => {
          const opposite = oppositeDuplicateChoice(deleteSelect.value);
          if (opposite && keepSelect.value !== opposite) {
            keepSelect.value = opposite;
          }
          syncDuplicateReviewState(container);
        });
      }
      syncDuplicateReviewState(container);
    });

    const actionPanel = document.getElementById('scan-admin-contact-action-panel');
    const actionForm = document.getElementById('scan-admin-contact-action-form');
    const actionValueInput = document.getElementById('scan-admin-contact-action-value');
    const actionContactIdInput = document.getElementById('scan-admin-contact-action-contact-id');
    const actionSourceIdInput = document.getElementById('scan-admin-contact-action-source-id');
    const actionTitle = document.getElementById('scan-admin-contact-action-title');
    const actionDescription = document.getElementById('scan-admin-contact-action-description');
    const actionSubmit = document.getElementById('scan-admin-contact-action-submit');
    const actionCancel = document.getElementById('scan-admin-contact-action-cancel');
    const mergeTargetGroup = document.getElementById(
      'scan-admin-contact-action-merge-target-group'
    );
    const mergeTargetSelect = document.getElementById('scan-admin-contact-action-target-id');

    if (!actionPanel || !actionForm || !actionValueInput || !actionSubmit) {
      return;
    }

    let activeActionSelect = null;

    const resetActionPanel = () => {
      actionPanel.hidden = true;
      actionValueInput.value = '';
      actionContactIdInput.value = '';
      actionSourceIdInput.value = '';
      if (mergeTargetGroup) {
        mergeTargetGroup.hidden = true;
      }
      if (mergeTargetSelect) {
        mergeTargetSelect.required = false;
        mergeTargetSelect.value = '';
        Array.from(mergeTargetSelect.options).forEach(option => {
          option.hidden = false;
          option.disabled = false;
        });
      }
      if (activeActionSelect) {
        activeActionSelect.value = '';
      }
      activeActionSelect = null;
    };

    const filterMergeTargets = ({ sourceId, contactType }) => {
      if (!mergeTargetSelect) {
        return;
      }
      Array.from(mergeTargetSelect.options).forEach(option => {
        if (!option.value) {
          option.hidden = false;
          option.disabled = false;
          return;
        }
        const matchesType = option.dataset.contactType === contactType;
        const sameContact = option.value === sourceId;
        option.hidden = !(matchesType && !sameContact);
        option.disabled = !(matchesType && !sameContact);
      });
      mergeTargetSelect.value = '';
    };

    const openActionPanel = ({ action, contactId, contactType, contactName }) => {
      actionPanel.hidden = false;
      if (action === 'deactivate') {
        actionValueInput.value = 'deactivate_contact';
        actionContactIdInput.value = contactId;
        actionSourceIdInput.value = '';
        if (mergeTargetGroup) {
          mergeTargetGroup.hidden = true;
        }
        if (mergeTargetSelect) {
          mergeTargetSelect.required = false;
          mergeTargetSelect.value = '';
        }
        if (actionTitle) {
          actionTitle.textContent = 'Désactiver le contact';
        }
        if (actionDescription) {
          actionDescription.textContent = `Confirmer la désactivation de ${contactName}.`;
        }
        actionSubmit.textContent = 'Désactiver';
        if (typeof actionPanel.scrollIntoView === 'function') {
          actionPanel.scrollIntoView({ block: 'nearest' });
        }
        return;
      }

      actionValueInput.value = 'merge_contact';
      actionContactIdInput.value = '';
      actionSourceIdInput.value = contactId;
      if (mergeTargetGroup) {
        mergeTargetGroup.hidden = false;
      }
      if (mergeTargetSelect) {
        mergeTargetSelect.required = true;
      }
      filterMergeTargets({ sourceId: contactId, contactType });
      if (actionTitle) {
        actionTitle.textContent = 'Fusionner un contact';
      }
      if (actionDescription) {
        actionDescription.textContent = `Choisissez la fiche cible pour fusionner ${contactName}.`;
      }
      actionSubmit.textContent = 'Fusionner';
      if (typeof actionPanel.scrollIntoView === 'function') {
        actionPanel.scrollIntoView({ block: 'nearest' });
      }
    };

    root.addEventListener('change', event => {
      if (!(event.target instanceof Element)) {
        return;
      }
      const actionSelect = event.target.closest('[data-contact-action-select="1"]');
      if (!actionSelect) {
        return;
      }
      const action = actionSelect.value;
      if (!action) {
        if (activeActionSelect === actionSelect) {
          resetActionPanel();
        }
        return;
      }
      if (action === 'edit') {
        const editUrl = actionSelect.dataset.editUrl;
        actionSelect.value = '';
        if (editUrl) {
          window.location.assign(editUrl);
        }
        return;
      }
      if (activeActionSelect && activeActionSelect !== actionSelect) {
        activeActionSelect.value = '';
      }
      activeActionSelect = actionSelect;
      openActionPanel({
        action,
        contactId: actionSelect.dataset.contactId || '',
        contactType: actionSelect.dataset.contactType || '',
        contactName: actionSelect.dataset.contactName || ''
      });
    });

    if (actionCancel) {
      actionCancel.addEventListener('click', resetActionPanel);
    }

    actionForm.addEventListener('submit', event => {
      if (actionValueInput.value !== 'merge_contact' || !mergeTargetSelect) {
        return;
      }
      if (!mergeTargetSelect.value) {
        event.preventDefault();
        mergeTargetSelect.focus();
      }
    });
  }

  function setupFaqEnhancements() {
    const faqContent = document.getElementById('scan-faq-content');
    const summaryList = document.getElementById('scan-faq-summary-list');
    if (!faqContent || !summaryList) {
      return;
    }
    if (faqContent.dataset.faqInitialized === 'true') {
      return;
    }
    faqContent.dataset.faqInitialized = 'true';

    const sections = faqContent.querySelectorAll('[data-faq-section="true"]');
    if (!sections.length) {
      return;
    }

    const collapsible = faqContent.dataset.faqCollapsible === 'true';
    const defaultExpanded = faqContent.dataset.faqDefaultExpanded === 'true';
    const openOnSummaryClick = faqContent.dataset.faqOpenOnSummaryClick === 'true';
    const usedIds = new Set();
    const sectionOpeners = new Map();
    const summaryGroups = new Map();
    summaryList
      .querySelectorAll('[data-faq-summary-group]')
      .forEach(groupSection => {
        const list = groupSection.querySelector('.scan-faq-nav-group-list');
        if (!list) {
          return;
        }
        list.innerHTML = '';
        groupSection.hidden = false;
        summaryGroups.set(groupSection.dataset.faqSummaryGroup, {
          section: groupSection,
          list,
        });
      });

    sections.forEach(card => {
      const title = card.querySelector('h2.ui-comp-title');
      if (!title) {
        return;
      }
      const titleText = title.textContent.trim();
      if (!titleText) {
        return;
      }

      if (!card.id) {
        card.id = buildFaqSectionId(titleText, usedIds);
      } else {
        usedIds.add(card.id);
      }

      if (collapsible) {
        const bodyId = `${card.id}-content`;
        let content = card.querySelector('.scan-faq-card-body');
        if (!content) {
          content = document.createElement('div');
          content.className = 'scan-faq-card-body';
          while (title.nextSibling) {
            content.appendChild(title.nextSibling);
          }
          card.appendChild(content);
        }
        content.id = bodyId;

        title.classList.add('scan-faq-title');
        let toggleButton = title.querySelector('.scan-faq-toggle');
        if (!toggleButton) {
          toggleButton = document.createElement('button');
          toggleButton.type = 'button';
          toggleButton.className = 'btn btn-tertiary btn-sm scan-faq-toggle';
          title.appendChild(toggleButton);
        }
        toggleButton.setAttribute('aria-controls', bodyId);

        const setExpanded = expanded => {
          content.hidden = !expanded;
          card.classList.toggle('scan-faq-collapsed', !expanded);
          toggleButton.setAttribute('aria-expanded', expanded ? 'true' : 'false');
          toggleButton.textContent = expanded ? 'Masquer' : 'Afficher';
        };

        setExpanded(defaultExpanded);
        toggleButton.addEventListener('click', () => {
          const expanded = toggleButton.getAttribute('aria-expanded') === 'true';
          setExpanded(!expanded);
        });
        sectionOpeners.set(card.id, () => setExpanded(true));
      }

      const summaryItem = document.createElement('li');
      summaryItem.className = 'scan-faq-summary-item';
      const summaryLink = document.createElement('a');
      summaryLink.className = 'scan-faq-summary-link scan-faq-nav-link';
      summaryLink.href = `#${card.id}`;
      summaryLink.textContent = titleText;
      if (openOnSummaryClick && sectionOpeners.has(card.id)) {
        summaryLink.addEventListener('click', () => {
          const openCard = sectionOpeners.get(card.id);
          if (openCard) {
            openCard();
          }
        });
      }
      summaryItem.appendChild(summaryLink);
      const groupKey = card.dataset.faqGroup || 'foundations';
      let summaryGroup = summaryGroups.get(groupKey);
      if (!summaryGroup) {
        const fallbackSection = document.createElement('section');
        fallbackSection.className = 'scan-faq-nav-group';
        fallbackSection.dataset.faqSummaryGroup = groupKey;
        const fallbackHeading = document.createElement('h3');
        fallbackHeading.className = 'scan-faq-nav-group-heading';
        fallbackHeading.textContent = card.dataset.faqGroupTitle || groupKey;
        const fallbackList = document.createElement('ul');
        fallbackList.className = 'scan-faq-nav-group-list';
        fallbackSection.appendChild(fallbackHeading);
        fallbackSection.appendChild(fallbackList);
        summaryList.appendChild(fallbackSection);
        summaryGroup = {
          section: fallbackSection,
          list: fallbackList,
        };
        summaryGroups.set(groupKey, summaryGroup);
      }
      summaryGroup.section.hidden = false;
      summaryGroup.list.appendChild(summaryItem);
    });

    if (openOnSummaryClick && collapsible) {
      const hashId = (window.location.hash || '').replace(/^#/, '');
      if (hashId && sectionOpeners.has(hashId)) {
        const openCard = sectionOpeners.get(hashId);
        if (openCard) {
          openCard();
        }
      }
    }
  }

  document.addEventListener('click', event => {
    const trigger = event.target.closest('[data-scan-target]');
    if (!trigger) {
      return;
    }
    event.preventDefault();
    const targetId = trigger.getAttribute('data-scan-target');
    const input = document.getElementById(targetId);
    if (!input) {
      return;
    }
    activeScanTrigger = trigger;
    blurElement(trigger);
    startScan(input);
  });

  document.addEventListener('click', event => {
    const trigger = event.target.closest('[data-ocr-target]');
    if (!trigger) {
      return;
    }
    event.preventDefault();
    const targetId = trigger.getAttribute('data-ocr-target');
    const input = document.getElementById(targetId);
    if (!input) {
      return;
    }
    activeScanTrigger = trigger;
    blurElement(trigger);
    startOcrScan(input);
  });

  function closePackSuccessModal() {
    const modal = document.getElementById('pack-success-modal');
    const backdrop = document.getElementById('pack-success-backdrop');
    if (modal) {
      modal.style.display = 'none';
      modal.classList.remove('show');
      modal.setAttribute('aria-hidden', 'true');
    }
    if (backdrop && backdrop.parentNode) {
      backdrop.parentNode.removeChild(backdrop);
    }
  }

  function readPackSuccessPrintUrls() {
    const payload = document.getElementById('pack-success-print-urls');
    if (!payload) {
      return [];
    }
    try {
      const data = JSON.parse(payload.textContent || '[]');
      return Array.isArray(data) ? data.filter(Boolean) : [];
    } catch (err) {
      return [];
    }
  }

  function setupPackSuccessModal() {
    document.querySelectorAll('[data-pack-success-close="1"]').forEach(button => {
      button.addEventListener('click', () => {
        closePackSuccessModal();
      });
    });

    document.querySelectorAll('[data-pack-success-print="1"]').forEach(button => {
      button.addEventListener('click', () => {
        readPackSuccessPrintUrls().forEach(url => {
          window.open(url, '_blank', 'noopener');
        });
        closePackSuccessModal();
      });
    });
  }

  setupProductDatalist();
  setupPackLines();
  setupPackSuccessModal();
  setupShipmentBuilder();
  setupShipmentContactFilters();
  setupAdminContactsCrud();
  setupReceiptLines();
  setupTableTools();
  setupFaqEnhancements();
  setupCameraFacingControls();

  const receivedOnInput = document.getElementById('id_received_on');
  if (receivedOnInput && !receivedOnInput.value) {
    receivedOnInput.value = new Date().toISOString().slice(0, 10);
  }

  if (captureBtn) {
    captureBtn.addEventListener('click', async () => {
      if (!ocrActiveInput) {
        return;
      }
      captureBtn.disabled = true;
      setStatus(OCR_DISABLED_MESSAGE);
      await stopScan();
      try {
        await runOcrCapture();
      } finally {
        captureBtn.disabled = false;
      }
    });
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
