(() => {
  let numberInputCounter = 0;

  function countDecimals(rawValue) {
    if (rawValue === null || rawValue === undefined) {
      return 0;
    }
    const text = String(rawValue).trim().toLowerCase();
    if (!text || text === "any") {
      return 0;
    }
    const exponentIndex = text.indexOf("e-");
    if (exponentIndex >= 0) {
      const exponent = parseInt(text.slice(exponentIndex + 2), 10);
      return Number.isFinite(exponent) ? exponent : 0;
    }
    const dotIndex = text.indexOf(".");
    return dotIndex >= 0 ? text.length - dotIndex - 1 : 0;
  }

  function parseNumericValue(rawValue) {
    if (rawValue === null || rawValue === undefined || rawValue === "") {
      return null;
    }
    const parsed = Number(rawValue);
    return Number.isFinite(parsed) ? parsed : null;
  }

  function roundToPrecision(value, precision) {
    if (!Number.isFinite(value) || precision <= 0) {
      return value;
    }
    const factor = 10 ** precision;
    return Math.round((value + Number.EPSILON) * factor) / factor;
  }

  function formatNumericValue(value, precision) {
    const rounded = roundToPrecision(value, precision);
    if (!Number.isFinite(rounded)) {
      return "";
    }
    if (precision <= 0) {
      return String(Math.round(rounded));
    }
    return rounded.toFixed(precision).replace(/\.?0+$/, "");
  }

  function getNumberInputStep(input) {
    const stepAttr = input.getAttribute("step");
    if (!stepAttr || stepAttr === "any") {
      return 1;
    }
    const parsed = parseNumericValue(stepAttr);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : 1;
  }

  function getNumberInputPrecision(input) {
    return Math.max(
      countDecimals(input.getAttribute("step")),
      countDecimals(input.value),
      countDecimals(input.getAttribute("min")),
      countDecimals(input.getAttribute("max"))
    );
  }

  function getOrAssignNumberInputId(input) {
    if (!input.id) {
      numberInputCounter += 1;
      input.id = `ui-number-input-${numberInputCounter}`;
    }
    return input.id;
  }

  function syncNumberInputButtons(input, controls) {
    if (!controls) {
      return;
    }
    const decrement = controls.querySelector('[data-ui-number-input-action="decrement"]');
    const increment = controls.querySelector('[data-ui-number-input-action="increment"]');
    const isDisabled = input.disabled || input.readOnly;
    const current = parseNumericValue(input.value);
    const min = parseNumericValue(input.getAttribute("min"));
    const max = parseNumericValue(input.getAttribute("max"));

    if (decrement) {
      decrement.disabled = isDisabled || (current !== null && min !== null && current <= min);
    }
    if (increment) {
      increment.disabled = isDisabled || (current !== null && max !== null && current >= max);
    }
  }

  function updateNumberInputValue(input, direction) {
    const step = getNumberInputStep(input);
    const precision = getNumberInputPrecision(input);
    const min = parseNumericValue(input.getAttribute("min"));
    const max = parseNumericValue(input.getAttribute("max"));
    const current = parseNumericValue(input.value);

    let nextValue = current;
    if (nextValue === null) {
      if (direction > 0 && min !== null) {
        nextValue = min;
      } else if (direction < 0 && max !== null) {
        nextValue = max;
      } else {
        nextValue = 0;
      }
    } else {
      nextValue += direction * step;
    }

    if (min !== null && nextValue < min) {
      nextValue = min;
    }
    if (max !== null && nextValue > max) {
      nextValue = max;
    }

    const formatted = formatNumericValue(nextValue, precision);
    if (formatted === input.value) {
      return;
    }

    input.value = formatted;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function createNumberInputButton(inputId, action, label) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "ui-number-input-btn";
    button.textContent = label;
    button.setAttribute("aria-label", action === "increment" ? "Augmenter la valeur" : "Diminuer la valeur");
    button.setAttribute("data-ui-number-input-action", action);
    button.setAttribute("data-ui-number-input-target", inputId);
    return button;
  }

  function enhanceNumberInput(input) {
    if (!(input instanceof HTMLInputElement)) {
      return;
    }
    if (input.type !== "number") {
      return;
    }
    if (input.dataset.uiNumberInputOptout === "1" || input.classList.contains("ui-number-input-optout")) {
      return;
    }
    if (input.classList.contains("is-ui-number-input-enhanced")) {
      return;
    }
    if (input.closest(".ui-number-input")) {
      return;
    }
    if (!input.parentNode) {
      return;
    }

    const inputId = getOrAssignNumberInputId(input);
    const wrapper = document.createElement("div");
    wrapper.className = "ui-number-input";
    if (input.classList.contains("form-control") || input.classList.contains("w-100")) {
      wrapper.classList.add("is-fluid");
    }
    if (input.classList.contains("form-control-sm")) {
      wrapper.classList.add("is-sm");
    }

    const controls = document.createElement("div");
    controls.className = "ui-number-input-controls";
    controls.appendChild(createNumberInputButton(inputId, "decrement", "-"));
    controls.appendChild(createNumberInputButton(inputId, "increment", "+"));

    input.parentNode.insertBefore(wrapper, input);
    wrapper.appendChild(controls);
    wrapper.appendChild(input);

    input.classList.add("ui-number-input-input", "is-ui-number-input-enhanced");

    controls.addEventListener("click", event => {
      const button = event.target.closest(".ui-number-input-btn");
      if (!button || button.disabled || input.disabled || input.readOnly) {
        return;
      }
      const direction = button.dataset.uiNumberInputAction === "decrement" ? -1 : 1;
      updateNumberInputValue(input, direction);
      syncNumberInputButtons(input, controls);
    });

    input.addEventListener("input", () => syncNumberInputButtons(input, controls));
    input.addEventListener("change", () => syncNumberInputButtons(input, controls));
    syncNumberInputButtons(input, controls);
  }

  function setupNumberInputs(root = document) {
    root.querySelectorAll('input[type="number"]').forEach(enhanceNumberInput);
  }

  document.addEventListener('wms:enhance-number-inputs', event => {
    const root =
      event &&
      event.detail &&
      event.detail.root instanceof Element
        ? event.detail.root
        : document;
    setupNumberInputs(root);
  });

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
    const overlay = document.getElementById('scan-overlay');

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

  setupNumberInputs();
  setupLiveSync();
})();
