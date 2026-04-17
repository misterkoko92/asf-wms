(function () {
  const dataNode = document.getElementById("scan-import-selector-data");
  if (!dataNode) {
    return;
  }

  let datasets = {};
  try {
    datasets = JSON.parse(dataNode.textContent || "{}");
  } catch (error) {
    return;
  }

  const MAX_RESULTS = 8;
  const MAX_EMPTY_RESULTS = 24;
  const field = id => document.getElementById(id);

  const normalize = value =>
    String(value || "")
      .normalize("NFKD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .trim();

  const joinParts = parts => parts.filter(Boolean).join(" | ");
  const compareValues = (left, right) =>
    String(left || "").localeCompare(String(right || ""), "fr", {
      sensitivity: "base",
      numeric: true,
    });

  const uniqueValues = values => {
    const seen = new Set();
    const deduped = [];
    values.forEach(value => {
      if (!value) {
        return;
      }
      const key = normalize(value);
      if (!key || seen.has(key)) {
        return;
      }
      seen.add(key);
      deduped.push(String(value));
    });
    return deduped.sort(compareValues);
  };

  const setFieldValue = (id, value) => {
    const element = field(id);
    if (!element) {
      return;
    }
    const nextValue = value == null ? "" : String(value);
    if (element.tagName === "SELECT") {
      element.value = nextValue;
      if (element.value !== nextValue && nextValue === "") {
        element.selectedIndex = 0;
      }
      return;
    }
    element.value = nextValue;
  };

  const renderNoMatch = (list, query) => {
    list.innerHTML = "";
    if (!query) {
      list.classList.remove("is-open");
      return [];
    }
    const empty = document.createElement("div");
    empty.className = "scan-import-selector-empty";
    empty.textContent = 'Aucune correspondance. La valeur sera gardee telle quelle.';
    list.appendChild(empty);
    list.classList.add("is-open");
    return [];
  };

  const createHost = input => {
    const host = input.closest(".scan-field") || input.parentElement;
    if (!host) {
      return null;
    }
    host.classList.add("scan-import-selector-host");
    input.classList.add("scan-import-selector-input");
    let list = host.querySelector(".scan-import-selector-list");
    if (!list) {
      list = document.createElement("div");
      list.className = "scan-import-selector-list";
      list.setAttribute("role", "listbox");
      host.appendChild(list);
    }
    return { host, list };
  };

  const filterRecords = (records, searchKeys, query) => {
    const normalizedQuery = normalize(query);
    if (!normalizedQuery) {
      return records.slice(0, MAX_EMPTY_RESULTS);
    }
    return records
      .filter(record =>
        searchKeys.some(key => normalize(record[key]).includes(normalizedQuery))
      )
      .slice(0, MAX_RESULTS);
  };

  const filterValues = (values, query) => {
    const normalizedQuery = normalize(query);
    if (!normalizedQuery) {
      return values.slice(0, MAX_EMPTY_RESULTS);
    }
    return values
      .filter(value => normalize(value).includes(normalizedQuery))
      .slice(0, MAX_RESULTS);
  };

  const buildItem = suggestion => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "scan-import-selector-item";
    button.setAttribute("role", "option");

    const primary = document.createElement("span");
    primary.className = "scan-import-selector-primary";
    primary.textContent = suggestion.primary;
    button.appendChild(primary);

    if (suggestion.secondary) {
      const meta = document.createElement("span");
      meta.className = "scan-import-selector-meta";
      meta.textContent = suggestion.secondary;
      button.appendChild(meta);
    }
    return button;
  };

  const attachRecordAutocomplete = config => {
    const input = field(config.inputId);
    const staticRecords = Array.isArray(datasets[config.datasetName]) ? datasets[config.datasetName] : [];
    const resolveRecords = () => {
      if (typeof config.getRecords === "function") {
        const dynamicRecords = config.getRecords(staticRecords, datasets);
        return Array.isArray(dynamicRecords) ? dynamicRecords : [];
      }
      return staticRecords;
    };
    if (!input || (!staticRecords.length && typeof config.getRecords !== "function")) {
      return;
    }

    input.autocomplete = "off";
    const hostData = createHost(input);
    if (!hostData) {
      return;
    }
    const { host, list } = hostData;
    let matches = [];
    let activeIndex = -1;
    let closeTimer = null;

    const closeList = () => {
      matches = [];
      activeIndex = -1;
      list.innerHTML = "";
      list.classList.remove("is-open");
    };

    const applySelection = record => {
      setFieldValue(config.inputId, record[config.valueKey] || "");
      config.fill(record);
      if (typeof config.onApply === "function") {
        config.onApply(record);
      }
      closeList();
    };

    const updateActive = nextIndex => {
      const items = list.querySelectorAll(".scan-import-selector-item");
      items.forEach((item, index) => {
        item.classList.toggle("is-active", index === nextIndex);
      });
      activeIndex = nextIndex;
    };

    const renderMatches = query => {
      const records = resolveRecords();
      if (!records.length) {
        renderNoMatch(list, query);
        return;
      }
      matches = filterRecords(records, config.searchKeys, query);
      if (!matches.length) {
        renderNoMatch(list, query);
        return;
      }

      list.innerHTML = "";
      matches.forEach((record, index) => {
        const item = buildItem(config.render(record));
        item.addEventListener("mouseenter", () => updateActive(index));
        item.addEventListener("mousedown", event => {
          event.preventDefault();
          applySelection(record);
        });
        list.appendChild(item);
      });
      updateActive(0);
      list.classList.add("is-open");
    };

    input.addEventListener("input", () => {
      renderMatches(input.value);
    });

    input.addEventListener("focus", () => {
      if (closeTimer) {
        window.clearTimeout(closeTimer);
      }
      renderMatches(input.value);
    });

    input.addEventListener("keydown", event => {
      if (!list.classList.contains("is-open")) {
        return;
      }
      if (event.key === "ArrowDown") {
        event.preventDefault();
        updateActive(Math.min(activeIndex + 1, matches.length - 1));
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        updateActive(Math.max(activeIndex - 1, 0));
      } else if (event.key === "Enter") {
        if (activeIndex < 0 || !matches[activeIndex]) {
          return;
        }
        event.preventDefault();
        applySelection(matches[activeIndex]);
      } else if (event.key === "Escape") {
        closeList();
      }
    });

    input.addEventListener("blur", () => {
      closeTimer = window.setTimeout(closeList, 120);
    });

    document.addEventListener("click", event => {
      if (!host.contains(event.target)) {
        closeList();
      }
    });
  };

  const attachValueAutocomplete = config => {
    const input = field(config.inputId);
    const staticValues = Array.isArray(datasets[config.datasetName]) ? datasets[config.datasetName] : [];
    const resolveValues = () => {
      if (typeof config.getValues === "function") {
        const dynamicValues = config.getValues(staticValues, datasets);
        return Array.isArray(dynamicValues) ? uniqueValues(dynamicValues) : [];
      }
      return uniqueValues(staticValues);
    };
    if (!input || (!staticValues.length && typeof config.getValues !== "function")) {
      return;
    }

    input.autocomplete = "off";
    const hostData = createHost(input);
    if (!hostData) {
      return;
    }
    const { host, list } = hostData;
    let matches = [];
    let activeIndex = -1;
    let closeTimer = null;

    const closeList = () => {
      matches = [];
      activeIndex = -1;
      list.innerHTML = "";
      list.classList.remove("is-open");
    };

    const updateActive = nextIndex => {
      const items = list.querySelectorAll(".scan-import-selector-item");
      items.forEach((item, index) => {
        item.classList.toggle("is-active", index === nextIndex);
      });
      activeIndex = nextIndex;
    };

    const applySelection = value => {
      input.value = value;
      if (typeof config.onApply === "function") {
        config.onApply(value);
      }
      closeList();
    };

    const renderMatches = query => {
      if (input.readOnly) {
        closeList();
        return;
      }
      const values = resolveValues();
      if (!values.length) {
        renderNoMatch(list, query);
        return;
      }
      matches = filterValues(values, query);
      if (!matches.length) {
        renderNoMatch(list, query);
        return;
      }
      list.innerHTML = "";
      matches.forEach((value, index) => {
        const item = buildItem({ primary: value, secondary: config.secondaryText || "" });
        item.addEventListener("mouseenter", () => updateActive(index));
        item.addEventListener("mousedown", event => {
          event.preventDefault();
          applySelection(value);
        });
        list.appendChild(item);
      });
      updateActive(0);
      list.classList.add("is-open");
    };

    input.addEventListener("input", () => renderMatches(input.value));

    input.addEventListener("focus", () => {
      if (closeTimer) {
        window.clearTimeout(closeTimer);
      }
      renderMatches(input.value);
    });

    input.addEventListener("keydown", event => {
      if (!list.classList.contains("is-open")) {
        return;
      }
      if (event.key === "ArrowDown") {
        event.preventDefault();
        updateActive(Math.min(activeIndex + 1, matches.length - 1));
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        updateActive(Math.max(activeIndex - 1, 0));
      } else if (event.key === "Enter") {
        if (activeIndex < 0 || !matches[activeIndex]) {
          return;
        }
        event.preventDefault();
        applySelection(matches[activeIndex]);
      } else if (event.key === "Escape") {
        closeList();
      }
    });

    input.addEventListener("blur", () => {
      closeTimer = window.setTimeout(closeList, 120);
    });

    document.addEventListener("click", event => {
      if (!host.contains(event.target)) {
        closeList();
      }
    });
  };

  const categoryRecords = Array.isArray(datasets.categories) ? datasets.categories : [];
  const locationRecords = Array.isArray(datasets.locations) ? datasets.locations : [];
  const rackColorRecords = Array.isArray(datasets.rack_colors) ? datasets.rack_colors : [];
  const rackColorByWarehouseAndZone = new Map();
  rackColorRecords.forEach(record => {
    const key = `${normalize(record.warehouse)}|${normalize(record.zone)}`;
    if (key && record.color && !rackColorByWarehouseAndZone.has(key)) {
      rackColorByWarehouseAndZone.set(key, record.color);
    }
  });
  const rackColorsByWarehouse = new Map();
  rackColorRecords.forEach(record => {
    const warehouseKey = normalize(record.warehouse);
    if (!warehouseKey || !record.color) {
      return;
    }
    if (!rackColorsByWarehouse.has(warehouseKey)) {
      rackColorsByWarehouse.set(warehouseKey, new Set());
    }
    rackColorsByWarehouse.get(warehouseKey).add(normalize(record.color));
  });
  const allRackColors = uniqueValues(rackColorRecords.map(record => record.color));

  const getRackColorFor = (warehouse, zone) =>
    rackColorByWarehouseAndZone.get(`${normalize(warehouse)}|${normalize(zone)}`) || "";

  const syncRackColorField = ({ warehouseId, zoneId, colorId }) => {
    const warehouseInput = field(warehouseId);
    const zoneInput = field(zoneId);
    const colorInput = field(colorId);
    if (!warehouseInput || !zoneInput || !colorInput) {
      return;
    }
    const knownRackColor = getRackColorFor(warehouseInput.value, zoneInput.value);
    if (knownRackColor) {
      colorInput.value = knownRackColor;
      colorInput.readOnly = true;
      colorInput.dataset.lockedByKnownRack = "1";
      return;
    }
    if (colorInput.dataset.lockedByKnownRack === "1") {
      colorInput.value = "";
    }
    colorInput.readOnly = false;
    colorInput.dataset.lockedByKnownRack = "0";
  };

  const bindRackColorSync = config => {
    const warehouseInput = field(config.warehouseId);
    const zoneInput = field(config.zoneId);
    [warehouseInput, zoneInput].forEach(input => {
      if (!input) {
        return;
      }
      ["input", "change", "blur"].forEach(eventName => {
        input.addEventListener(eventName, () => syncRackColorField(config));
      });
    });
    syncRackColorField(config);
  };

  const buildCategoryLevelValueResolver = level => () => {
    const levelValues = [
      field("category_l1")?.value || "",
      field("category_l2")?.value || "",
      field("category_l3")?.value || "",
      field("category_l4")?.value || "",
    ];
    const targetKey = `level_${level + 1}`;
    const values = categoryRecords
      .filter(record => {
        for (let index = 0; index < level; index += 1) {
          const currentValue = levelValues[index];
          if (!currentValue) {
            continue;
          }
          if (normalize(record[`level_${index + 1}`]) !== normalize(currentValue)) {
            return false;
          }
        }
        return Boolean(record[targetKey]);
      })
      .map(record => record[targetKey]);
    return uniqueValues(values);
  };

  const filterLocationRecords = ({ warehouseId, zoneId, aisleId, level }) => {
    const warehouseValue = field(warehouseId)?.value || "";
    const zoneValue = field(zoneId)?.value || "";
    const aisleValue = field(aisleId)?.value || "";
    return locationRecords.filter(record => {
      if (warehouseValue && normalize(record.warehouse) !== normalize(warehouseValue)) {
        return false;
      }
      if (level !== "zone" && zoneValue && normalize(record.zone) !== normalize(zoneValue)) {
        return false;
      }
      if (level === "shelf" && aisleValue && normalize(record.aisle) !== normalize(aisleValue)) {
        return false;
      }
      return true;
    });
  };

  const buildLocationValueResolver = config => key => () =>
    uniqueValues(filterLocationRecords(config).map(record => record[key]));

  const buildRackColorValueResolver = ({ warehouseId, zoneId }) => () => {
    const warehouseValue = field(warehouseId)?.value || "";
    const zoneValue = field(zoneId)?.value || "";
    const knownRackColor = getRackColorFor(warehouseValue, zoneValue);
    if (knownRackColor) {
      return [knownRackColor];
    }
    const warehouseKey = normalize(warehouseValue);
    if (!warehouseKey || !rackColorsByWarehouse.has(warehouseKey)) {
      return allRackColors;
    }
    const warehouseColors = rackColorsByWarehouse.get(warehouseKey);
    return allRackColors.filter(color => !warehouseColors.has(normalize(color)));
  };

  const attachTokenAutocomplete = config => {
    const input = field(config.inputId);
    const values = uniqueValues(
      Array.isArray(datasets[config.datasetName]) ? datasets[config.datasetName] : []
    );
    if (!input || !values.length) {
      return;
    }

    input.autocomplete = "off";
    const hostData = createHost(input);
    if (!hostData) {
      return;
    }
    const { host, list } = hostData;
    let matches = [];
    let activeIndex = -1;
    let closeTimer = null;

    const currentToken = () => {
      const parts = input.value.split("|");
      return (parts[parts.length - 1] || "").trim();
    };

    const closeList = () => {
      matches = [];
      activeIndex = -1;
      list.innerHTML = "";
      list.classList.remove("is-open");
    };

    const updateActive = nextIndex => {
      const items = list.querySelectorAll(".scan-import-selector-item");
      items.forEach((item, index) => {
        item.classList.toggle("is-active", index === nextIndex);
      });
      activeIndex = nextIndex;
    };

    const applySelection = value => {
      const parts = input.value.split("|");
      const committed = parts
        .slice(0, -1)
        .map(part => part.trim())
        .filter(Boolean);
      const deduped = committed.filter(token => normalize(token) !== normalize(value));
      deduped.push(value);
      input.value = deduped.join("|");
      closeList();
    };

    const renderMatches = () => {
      const query = currentToken();
      const committedTokens = input.value
        .split("|")
        .slice(0, -1)
        .map(part => part.trim())
        .filter(Boolean)
        .map(normalize);
      const availableValues = values.filter(
        value => !committedTokens.includes(normalize(value))
      );
      matches = filterValues(availableValues, query);
      if (!matches.length) {
        renderNoMatch(list, query);
        return;
      }
      list.innerHTML = "";
      matches.forEach((value, index) => {
        const item = buildItem({ primary: value, secondary: config.secondaryText || "" });
        item.addEventListener("mouseenter", () => updateActive(index));
        item.addEventListener("mousedown", event => {
          event.preventDefault();
          applySelection(value);
        });
        list.appendChild(item);
      });
      updateActive(0);
      list.classList.add("is-open");
    };

    input.addEventListener("input", renderMatches);

    input.addEventListener("focus", () => {
      if (closeTimer) {
        window.clearTimeout(closeTimer);
      }
      renderMatches();
    });

    input.addEventListener("keydown", event => {
      if (!list.classList.contains("is-open")) {
        return;
      }
      if (event.key === "ArrowDown") {
        event.preventDefault();
        updateActive(Math.min(activeIndex + 1, matches.length - 1));
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        updateActive(Math.max(activeIndex - 1, 0));
      } else if (event.key === "Enter") {
        if (activeIndex < 0 || !matches[activeIndex]) {
          return;
        }
        event.preventDefault();
        applySelection(matches[activeIndex]);
      } else if (event.key === "Escape") {
        closeList();
      }
    });

    input.addEventListener("blur", () => {
      closeTimer = window.setTimeout(closeList, 120);
    });

    document.addEventListener("click", event => {
      if (!host.contains(event.target)) {
        closeList();
      }
    });
  };

  const fillProduct = record => {
    setFieldValue("product_name", record.name);
    setFieldValue("product_sku", record.sku);
    setFieldValue("product_barcode", record.barcode);
    setFieldValue("product_ean", record.ean);
    setFieldValue("product_pu_ht", record.pu_ht);
    setFieldValue("product_tva", record.tva);
    setFieldValue("product_brand", record.brand);
    setFieldValue("product_color", record.color);
    setFieldValue("product_tags", record.tags);
    setFieldValue("category_l1", record.category_l1);
    setFieldValue("category_l2", record.category_l2);
    setFieldValue("category_l3", record.category_l3);
    setFieldValue("category_l4", record.category_l4);
    setFieldValue("product_warehouse", record.warehouse);
    setFieldValue("product_zone", record.zone);
    setFieldValue("product_aisle", record.aisle);
    setFieldValue("product_shelf", record.shelf);
    setFieldValue("product_rack_color", record.rack_color);
    setFieldValue("product_weight_g", record.weight_g);
    setFieldValue("product_length_cm", record.length_cm);
    setFieldValue("product_width_cm", record.width_cm);
    setFieldValue("product_height_cm", record.height_cm);
    setFieldValue("product_volume_cm3", record.volume_cm3);
    setFieldValue("product_storage_conditions", record.storage_conditions);
    setFieldValue("product_perishable", String(record.perishable));
    setFieldValue("product_quarantine_default", String(record.quarantine_default));
    setFieldValue("product_notes", record.notes);
    syncRackColorField({
      warehouseId: "product_warehouse",
      zoneId: "product_zone",
      colorId: "product_rack_color",
    });
  };

  const fillCategory = record => {
    setFieldValue("cat_name", record.name);
    setFieldValue("cat_parent", record.parent);
  };

  const fillContact = record => {
    setFieldValue("contact_type", record.contact_type);
    setFieldValue("contact_name", record.name);
    setFieldValue("contact_email", record.email);
    setFieldValue("contact_phone", record.phone);
    setFieldValue("contact_address", record.address_line1);
    setFieldValue("contact_city", record.city);
  };

  const fillUser = record => {
    setFieldValue("user_username", record.username);
    setFieldValue("user_email", record.email);
    setFieldValue("user_first_name", record.first_name);
    setFieldValue("user_last_name", record.last_name);
    setFieldValue("user_flags", String(record.is_staff));
    setFieldValue("user_superuser", String(record.is_superuser));
    setFieldValue("user_active", String(record.is_active));
  };

  const productSecondary = record =>
    joinParts([
      record.sku && record.sku !== record.name ? record.sku : "",
      record.brand,
      joinParts([record.category_l1, record.category_l2, record.category_l3, record.category_l4]),
    ]);

  const categorySecondary = record => joinParts([record.parent, record.path]);
  const contactSecondary = record => joinParts([record.email, record.phone, record.scope, record.city]);
  const userSecondary = record => joinParts([record.email, record.first_name, record.last_name]);

  [
    { inputId: "product_name", valueKey: "name" },
    { inputId: "product_sku", valueKey: "sku" },
    { inputId: "product_barcode", valueKey: "barcode" },
    { inputId: "product_ean", valueKey: "ean" },
  ].forEach(config => {
    attachRecordAutocomplete({
      inputId: config.inputId,
      datasetName: "products",
      valueKey: config.valueKey,
      searchKeys: [
        "name",
        "sku",
        "barcode",
        "ean",
        "brand",
        "color",
        "tags",
        "category_l1",
        "category_l2",
        "category_l3",
        "category_l4",
      ],
      fill: fillProduct,
      render: record => ({
        primary: record[config.valueKey] || record.label,
        secondary: productSecondary(record),
      }),
    });
  });

  attachValueAutocomplete({
    inputId: "product_brand",
    datasetName: "brands",
    secondaryText: "Marque existante",
  });

  attachValueAutocomplete({
    inputId: "product_color",
    datasetName: "product_colors",
    secondaryText: "Couleur existante",
  });

  attachValueAutocomplete({
    inputId: "product_storage_conditions",
    datasetName: "storage_conditions",
    secondaryText: "Condition existante",
  });

  [
    { inputId: "category_l1", level: 0, secondaryText: "Catégorie L1" },
    { inputId: "category_l2", level: 1, secondaryText: "Catégorie L2" },
    { inputId: "category_l3", level: 2, secondaryText: "Catégorie L3" },
    { inputId: "category_l4", level: 3, secondaryText: "Catégorie L4" },
  ].forEach(config => {
    attachValueAutocomplete({
      inputId: config.inputId,
      datasetName: "categories",
      getValues: buildCategoryLevelValueResolver(config.level),
      secondaryText: config.secondaryText,
    });
  });

  attachRecordAutocomplete({
    inputId: "product_warehouse",
    datasetName: "warehouses",
    valueKey: "name",
    searchKeys: ["name", "code"],
    fill: record => {
      setFieldValue("product_warehouse", record.name);
      syncRackColorField({
        warehouseId: "product_warehouse",
        zoneId: "product_zone",
        colorId: "product_rack_color",
      });
    },
    render: record => ({
      primary: record.name,
      secondary: record.code || "",
    }),
  });

  const productLocationConfig = {
    warehouseId: "product_warehouse",
    zoneId: "product_zone",
    aisleId: "product_aisle",
  };

  [
    { inputId: "product_zone", key: "zone" },
    { inputId: "product_aisle", key: "aisle" },
    { inputId: "product_shelf", key: "shelf" },
  ].forEach(config => {
    attachValueAutocomplete({
      inputId: config.inputId,
      datasetName: "locations",
      getValues: buildLocationValueResolver(productLocationConfig)(config.key),
      secondaryText: "Emplacement existant",
      onApply:
        config.key === "zone"
          ? () =>
              syncRackColorField({
                warehouseId: "product_warehouse",
                zoneId: "product_zone",
                colorId: "product_rack_color",
              })
          : null,
    });
  });

  attachValueAutocomplete({
    inputId: "product_rack_color",
    datasetName: "rack_colors",
    getValues: buildRackColorValueResolver({
      warehouseId: "product_warehouse",
      zoneId: "product_zone",
    }),
    secondaryText: "Couleur rack existante",
  });

  attachTokenAutocomplete({
    inputId: "product_tags",
    datasetName: "product_tags",
  });

  attachRecordAutocomplete({
    inputId: "loc_warehouse",
    datasetName: "warehouses",
    valueKey: "name",
    searchKeys: ["name", "code"],
    fill: record => {
      setFieldValue("loc_warehouse", record.name);
      syncRackColorField({
        warehouseId: "loc_warehouse",
        zoneId: "loc_zone",
        colorId: "loc_color",
      });
    },
    render: record => ({
      primary: record.name,
      secondary: record.code || "",
    }),
  });

  const locationFormConfig = {
    warehouseId: "loc_warehouse",
    zoneId: "loc_zone",
    aisleId: "loc_aisle",
  };

  [
    { inputId: "loc_zone", key: "zone" },
    { inputId: "loc_aisle", key: "aisle" },
    { inputId: "loc_shelf", key: "shelf" },
    { inputId: "loc_notes", key: "notes" },
  ].forEach(config => {
    attachValueAutocomplete({
      inputId: config.inputId,
      datasetName: "locations",
      getValues: buildLocationValueResolver(locationFormConfig)(config.key),
      secondaryText: config.key === "notes" ? "Note existante" : "Emplacement existant",
      onApply:
        config.key === "zone"
          ? () =>
              syncRackColorField({
                warehouseId: "loc_warehouse",
                zoneId: "loc_zone",
                colorId: "loc_color",
              })
          : null,
    });
  });

  attachValueAutocomplete({
    inputId: "loc_color",
    datasetName: "rack_colors",
    getValues: buildRackColorValueResolver({
      warehouseId: "loc_warehouse",
      zoneId: "loc_zone",
    }),
    secondaryText: "Couleur rack existante",
  });

  attachRecordAutocomplete({
    inputId: "cat_name",
    datasetName: "categories",
    valueKey: "name",
    searchKeys: ["name", "parent", "path", "level_1", "level_2", "level_3", "level_4"],
    fill: fillCategory,
    render: record => ({
      primary: record.name,
      secondary: categorySecondary(record),
    }),
  });

  attachRecordAutocomplete({
    inputId: "cat_parent",
    datasetName: "categories",
    valueKey: "name",
    searchKeys: ["name", "path", "level_1", "level_2", "level_3", "level_4"],
    fill: record => setFieldValue("cat_parent", record.name),
    render: record => ({
      primary: record.name,
      secondary: record.path,
    }),
  });

  [
    { inputId: "wh_name", valueKey: "name" },
    { inputId: "wh_code", valueKey: "code" },
  ].forEach(config => {
    attachRecordAutocomplete({
      inputId: config.inputId,
      datasetName: "warehouses",
      valueKey: config.valueKey,
      searchKeys: ["name", "code"],
      fill: record => {
        setFieldValue("wh_name", record.name);
        setFieldValue("wh_code", record.code);
      },
      render: record => ({
        primary: record[config.valueKey] || record.name,
        secondary: joinParts([record.name, record.code]),
      }),
    });
  });

  [
    { inputId: "contact_name", valueKey: "name" },
    { inputId: "contact_email", valueKey: "email" },
    { inputId: "contact_phone", valueKey: "phone" },
    { inputId: "contact_address", valueKey: "address_line1" },
    { inputId: "contact_city", valueKey: "city" },
  ].forEach(config => {
    attachRecordAutocomplete({
      inputId: config.inputId,
      datasetName: "contacts",
      valueKey: config.valueKey,
      searchKeys: ["name", "email", "phone", "scope", "address_line1", "city"],
      fill: fillContact,
      render: record => ({
        primary: record[config.valueKey] || record.label,
        secondary: contactSecondary(record),
      }),
    });
  });

  [
    { inputId: "user_username", valueKey: "username" },
    { inputId: "user_email", valueKey: "email" },
    { inputId: "user_first_name", valueKey: "first_name" },
    { inputId: "user_last_name", valueKey: "last_name" },
  ].forEach(config => {
    attachRecordAutocomplete({
      inputId: config.inputId,
      datasetName: "users",
      valueKey: config.valueKey,
      searchKeys: ["username", "email", "first_name", "last_name"],
      fill: fillUser,
      render: record => ({
        primary: record[config.valueKey] || record.label,
        secondary: userSecondary(record),
      }),
    });
  });

  bindRackColorSync({
    warehouseId: "product_warehouse",
    zoneId: "product_zone",
    colorId: "product_rack_color",
  });

  bindRackColorSync({
    warehouseId: "loc_warehouse",
    zoneId: "loc_zone",
    colorId: "loc_color",
  });
})();
