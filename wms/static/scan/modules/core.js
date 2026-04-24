(() => {
  let numberInputCounter = 0;
  let dateInputCounter = 0;
  let activeDatePicker = null;

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

  function parseCssPixels(rawValue) {
    const parsed = parseFloat(rawValue);
    return Number.isFinite(parsed) ? parsed : 0;
  }

  function syncNumberInputLayout(input, wrapper, controls) {
    if (
      !(input instanceof HTMLInputElement) ||
      !(wrapper instanceof HTMLElement) ||
      !(controls instanceof HTMLElement)
    ) {
      return;
    }

    const inputStyles = window.getComputedStyle(input);
    const wrapperStyles = window.getComputedStyle(wrapper);
    const basePadding =
      parseCssPixels(inputStyles.getPropertyValue("--wms-input-padding-x")) ||
      parseCssPixels(wrapperStyles.getPropertyValue("--wms-input-padding-x")) ||
      parseCssPixels(inputStyles.paddingLeft);
    const controlsWidth = controls.getBoundingClientRect().width;
    const valueGap = parseCssPixels(wrapperStyles.getPropertyValue("--ui-number-input-value-gap"));
    const reservedPadding = Math.max(basePadding, basePadding + controlsWidth + valueGap);
    const reservedPaddingPx = `${reservedPadding}px`;

    wrapper.style.setProperty("--ui-number-input-reserved-padding", reservedPaddingPx);
    input.style.paddingLeft = reservedPaddingPx;
    input.style.paddingInlineStart = reservedPaddingPx;
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
    if (input.classList.contains("ui-number-input-compact")) {
      wrapper.classList.add("is-compact");
    }

    const controls = document.createElement("div");
    controls.className = "ui-number-input-controls";
    controls.appendChild(createNumberInputButton(inputId, "decrement", "-"));
    controls.appendChild(createNumberInputButton(inputId, "increment", "+"));

    input.parentNode.insertBefore(wrapper, input);
    wrapper.appendChild(controls);
    wrapper.appendChild(input);

    input.classList.add("ui-number-input-input", "is-ui-number-input-enhanced");
    syncNumberInputLayout(input, wrapper, controls);
    if (typeof window.requestAnimationFrame === "function") {
      window.requestAnimationFrame(() => syncNumberInputLayout(input, wrapper, controls));
    }
    if ("ResizeObserver" in window) {
      const resizeObserver = new ResizeObserver(() => syncNumberInputLayout(input, wrapper, controls));
      resizeObserver.observe(wrapper);
      resizeObserver.observe(controls);
    }
    window.addEventListener("resize", () => syncNumberInputLayout(input, wrapper, controls));
    window.addEventListener("load", () => syncNumberInputLayout(input, wrapper, controls));

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

  function isRequiredField(field) {
    if (!(field instanceof HTMLElement)) {
      return false;
    }
    if (
      field.matches('input[type="hidden"], button, [disabled]') ||
      field.getAttribute("aria-hidden") === "true"
    ) {
      return false;
    }
    return field.required || field.getAttribute("aria-required") === "true";
  }

  function findRequiredMarkerLabel(field) {
    if (!(field instanceof HTMLElement)) {
      return null;
    }
    if (field.id) {
      const explicitLabel = document.querySelector(`label[for="${CSS.escape(field.id)}"]`);
      if (explicitLabel) {
        return explicitLabel;
      }
    }
    const wrappedLabel = field.closest("label");
    if (wrappedLabel) {
      return wrappedLabel.querySelector(".form-check-label") || wrappedLabel;
    }
    return null;
  }

  function getAutoRequiredMarker(label) {
    return label.querySelector('.ui-field-required-marker[data-auto-required-marker="1"]');
  }

  function syncRequiredMarkerForField(field) {
    const label = findRequiredMarkerLabel(field);
    if (!label) {
      return;
    }
    const hasManualMarker = !!label.querySelector(
      '.ui-field-required-marker:not([data-auto-required-marker="1"]), [data-required-marker], [data-account-validation-required-marker]'
    );
    const autoMarker = getAutoRequiredMarker(label);
    if (!isRequiredField(field) || hasManualMarker) {
      if (autoMarker) {
        autoMarker.remove();
      }
      return;
    }
    if (autoMarker) {
      return;
    }
    const marker = document.createElement("span");
    marker.className = "ui-field-required-marker";
    marker.dataset.autoRequiredMarker = "1";
    marker.setAttribute("aria-hidden", "true");
    marker.textContent = "*";
    label.appendChild(marker);
  }

  function syncRequiredMarkers(root = document) {
    root.querySelectorAll("input, select, textarea").forEach(syncRequiredMarkerForField);
  }

  document.addEventListener("wms:sync-required-markers", event => {
    const root =
      event &&
      event.detail &&
      event.detail.root instanceof Element
        ? event.detail.root
        : document;
    syncRequiredMarkers(root);
  });

  function getOrAssignDateInputId(input) {
    if (!input.id) {
      dateInputCounter += 1;
      input.id = `ui-date-input-${dateInputCounter}`;
    }
    return input.id;
  }

  function parseDateValue(value) {
    const match = String(value || "").match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (!match) {
      return null;
    }
    const year = Number(match[1]);
    const month = Number(match[2]) - 1;
    const day = Number(match[3]);
    const date = new Date(year, month, day);
    if (
      date.getFullYear() !== year ||
      date.getMonth() !== month ||
      date.getDate() !== day
    ) {
      return null;
    }
    return date;
  }

  function formatDateValue(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  }

  function getMonthStart(date) {
    return new Date(date.getFullYear(), date.getMonth(), 1);
  }

  function addMonths(date, delta) {
    return new Date(date.getFullYear(), date.getMonth() + delta, 1);
  }

  function dispatchDateValue(input) {
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function closeDatePicker() {
    if (!activeDatePicker) {
      return;
    }
    document.removeEventListener("click", activeDatePicker.handleDocumentClick, true);
    document.removeEventListener("keydown", activeDatePicker.handleKeydown);
    window.removeEventListener("resize", activeDatePicker.reposition);
    window.removeEventListener("scroll", activeDatePicker.reposition, true);
    activeDatePicker.picker.remove();
    activeDatePicker = null;
  }

  function positionDatePicker(picker, wrapper) {
    const rect = wrapper.getBoundingClientRect();
    const viewportGap = 8;
    const pickerWidth = Math.min(320, window.innerWidth - viewportGap * 2);
    const left = Math.min(
      Math.max(viewportGap, rect.left),
      Math.max(viewportGap, window.innerWidth - pickerWidth - viewportGap)
    );
    picker.style.width = `${pickerWidth}px`;
    picker.style.left = `${left + window.scrollX}px`;
    picker.style.top = `${rect.bottom + viewportGap + window.scrollY}px`;
  }

  function buildDatePickerDayButton(dayDate, selectedValue, currentMonth) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "ui-date-picker-day";
    const value = formatDateValue(dayDate);
    button.textContent = String(dayDate.getDate());
    button.dataset.uiDateInputAction = "select-day";
    button.dataset.uiDateInputValue = value;
    button.classList.toggle("is-outside-month", dayDate.getMonth() !== currentMonth);
    button.classList.toggle("is-selected", value === selectedValue);
    return button;
  }

  function openDatePicker(input, wrapper) {
    closeDatePicker();
    const selectedDate = parseDateValue(input.value);
    let currentMonthDate = getMonthStart(selectedDate || new Date());
    const picker = document.createElement("div");
    picker.className = "ui-date-picker";
    picker.setAttribute("role", "dialog");
    picker.setAttribute("aria-label", "Choisir une date");

    const monthFormatter = new Intl.DateTimeFormat("fr-FR", {
      month: "long",
      year: "numeric",
    });

    const render = () => {
      const selectedValue = input.value || "";
      picker.innerHTML = "";

      const header = document.createElement("div");
      header.className = "ui-date-picker-header";

      const previous = document.createElement("button");
      previous.type = "button";
      previous.className = "ui-date-picker-nav";
      previous.textContent = "<";
      previous.dataset.uiDateInputAction = "previous-month";
      previous.setAttribute("aria-label", "Mois precedent");

      const title = document.createElement("div");
      title.className = "ui-date-picker-title";
      title.textContent = monthFormatter.format(currentMonthDate);

      const next = document.createElement("button");
      next.type = "button";
      next.className = "ui-date-picker-nav";
      next.textContent = ">";
      next.dataset.uiDateInputAction = "next-month";
      next.setAttribute("aria-label", "Mois suivant");

      header.appendChild(previous);
      header.appendChild(title);
      header.appendChild(next);
      picker.appendChild(header);

      const weekdays = document.createElement("div");
      weekdays.className = "ui-date-picker-weekdays";
      ["L", "M", "M", "J", "V", "S", "D"].forEach(label => {
        const day = document.createElement("span");
        day.textContent = label;
        weekdays.appendChild(day);
      });
      picker.appendChild(weekdays);

      const grid = document.createElement("div");
      grid.className = "ui-date-picker-grid";
      const firstDay = new Date(currentMonthDate.getFullYear(), currentMonthDate.getMonth(), 1);
      const mondayOffset = (firstDay.getDay() + 6) % 7;
      const gridStart = new Date(firstDay);
      gridStart.setDate(firstDay.getDate() - mondayOffset);
      for (let index = 0; index < 42; index += 1) {
        const dayDate = new Date(gridStart);
        dayDate.setDate(gridStart.getDate() + index);
        grid.appendChild(
          buildDatePickerDayButton(dayDate, selectedValue, currentMonthDate.getMonth())
        );
      }
      picker.appendChild(grid);
    };

    picker.addEventListener("click", event => {
      const target = event.target.closest("[data-ui-date-input-action]");
      if (!target) {
        return;
      }
      const action = target.dataset.uiDateInputAction;
      if (action === "previous-month") {
        currentMonthDate = addMonths(currentMonthDate, -1);
        render();
        return;
      }
      if (action === "next-month") {
        currentMonthDate = addMonths(currentMonthDate, 1);
        render();
        return;
      }
      if (action === "select-day") {
        input.value = target.dataset.uiDateInputValue || "";
        dispatchDateValue(input);
        closeDatePicker();
        input.focus();
      }
    });

    document.body.appendChild(picker);
    render();

    const reposition = () => positionDatePicker(picker, wrapper);
    reposition();
    const handleDocumentClick = event => {
      if (picker.contains(event.target) || wrapper.contains(event.target)) {
        return;
      }
      closeDatePicker();
    };
    const handleKeydown = event => {
      if (event.key === "Escape") {
        closeDatePicker();
      }
    };
    activeDatePicker = {
      picker,
      input,
      wrapper,
      reposition,
      handleDocumentClick,
      handleKeydown,
    };
    document.addEventListener("click", handleDocumentClick, true);
    document.addEventListener("keydown", handleKeydown);
    window.addEventListener("resize", reposition);
    window.addEventListener("scroll", reposition, true);
  }

  function enhanceDateInput(input) {
    if (!(input instanceof HTMLInputElement)) {
      return;
    }
    if (input.type !== "date") {
      return;
    }
    if (input.dataset.uiDateInputOptout === "1" || input.classList.contains("ui-date-input-optout")) {
      return;
    }
    if (input.classList.contains("is-ui-date-input-enhanced")) {
      return;
    }
    if (input.closest(".ui-date-input")) {
      return;
    }
    if (!input.parentNode) {
      return;
    }

    const inputId = getOrAssignDateInputId(input);
    const wrapper = document.createElement("div");
    wrapper.className = "ui-date-input";
    if (input.classList.contains("form-control") || input.classList.contains("w-100")) {
      wrapper.classList.add("is-fluid");
    }

    const button = document.createElement("button");
    button.type = "button";
    button.className = "ui-date-input-btn";
    button.setAttribute("aria-label", "Ouvrir le calendrier");
    button.setAttribute("data-ui-date-input-action", "open");
    button.setAttribute("data-ui-date-input-target", inputId);
    const icon = document.createElement("span");
    icon.className = "ui-date-input-btn-icon";
    icon.setAttribute("aria-hidden", "true");
    icon.innerHTML =
      '<svg viewBox="0 0 16 16" focusable="false"><path d="M4.25 1.5a.75.75 0 0 1 .75.75V3h6V2.25a.75.75 0 0 1 1.5 0V3h.25A2.25 2.25 0 0 1 15 5.25v7.5A2.25 2.25 0 0 1 12.75 15h-9.5A2.25 2.25 0 0 1 1 12.75v-7.5A2.25 2.25 0 0 1 3.25 3h.25v-.75a.75.75 0 0 1 .75-.75Zm8.5 5h-9.5v6.25a.75.75 0 0 0 .75.75h8a.75.75 0 0 0 .75-.75V6.5Zm-.75-2h-8a.75.75 0 0 0-.75.75v.25h9.5v-.25a.75.75 0 0 0-.75-.75Z" /></svg>';
    button.appendChild(icon);

    input.parentNode.insertBefore(wrapper, input);
    wrapper.appendChild(input);
    wrapper.appendChild(button);
    input.classList.add("ui-date-input-input", "is-ui-date-input-enhanced");

    button.addEventListener("click", () => {
      if (input.disabled || input.readOnly) {
        return;
      }
      if (typeof input.showPicker === "function") {
        try {
          input.showPicker();
          return;
        } catch (err) {
          // Fall through to the shared calendar when native picker access fails.
        }
      }
      openDatePicker(input, wrapper);
    });
  }

  function setupDateInputs(root = document) {
    root.querySelectorAll('input[type="date"]').forEach(enhanceDateInput);
  }

  document.addEventListener("wms:enhance-date-inputs", event => {
    const root =
      event &&
      event.detail &&
      event.detail.root instanceof Element
        ? event.detail.root
        : document;
    setupDateInputs(root);
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
  setupDateInputs();
  syncRequiredMarkers();
  document.addEventListener("input", () => syncRequiredMarkers());
  document.addEventListener("change", () => syncRequiredMarkers());
  setupLiveSync();
})();
