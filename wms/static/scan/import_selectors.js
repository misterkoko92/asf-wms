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
  const field = id => document.getElementById(id);

  const normalize = value =>
    String(value || "")
      .normalize("NFKD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .trim();

  const joinParts = parts => parts.filter(Boolean).join(" | ");

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
      return [];
    }
    return records
      .filter(record =>
        searchKeys.some(key => normalize(record[key]).includes(normalizedQuery))
      )
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
    const records = Array.isArray(datasets[config.datasetName]) ? datasets[config.datasetName] : [];
    if (!input || !records.length) {
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
      if (input.value.trim()) {
        renderMatches(input.value);
      }
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

  const attachTokenAutocomplete = config => {
    const input = field(config.inputId);
    const values = Array.isArray(datasets[config.datasetName]) ? datasets[config.datasetName] : [];
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
      const normalizedQuery = normalize(query);
      if (!normalizedQuery) {
        closeList();
        return;
      }
      matches = values
        .filter(value => normalize(value).includes(normalizedQuery))
        .slice(0, MAX_RESULTS);
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
    setFieldValue("product_notes", record.notes);
  };

  const fillProductCategories = record => {
    setFieldValue("category_l1", record.level_1);
    setFieldValue("category_l2", record.level_2);
    setFieldValue("category_l3", record.level_3);
    setFieldValue("category_l4", record.level_4);
  };

  const fillProductLocation = record => {
    setFieldValue("product_warehouse", record.warehouse);
    setFieldValue("product_zone", record.zone);
    setFieldValue("product_aisle", record.aisle);
    setFieldValue("product_shelf", record.shelf);
    setFieldValue("product_rack_color", record.rack_color);
  };

  const fillLocation = record => {
    setFieldValue("loc_warehouse", record.warehouse);
    setFieldValue("loc_zone", record.zone);
    setFieldValue("loc_aisle", record.aisle);
    setFieldValue("loc_shelf", record.shelf);
    setFieldValue("loc_color", record.rack_color);
    setFieldValue("loc_notes", record.notes);
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
    setFieldValue("contact_tags", record.tags);
    setFieldValue("contact_destination", record.destination);
    setFieldValue("contact_address", record.address_line1);
    setFieldValue("contact_city", record.city);
  };

  const fillDestination = record => {
    setFieldValue("contact_destination", record.label);
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

  const locationSecondary = record =>
    joinParts([record.warehouse, [record.zone, record.aisle, record.shelf].filter(Boolean).join("-"), record.rack_color]);

  const categorySecondary = record => joinParts([record.parent, record.path]);
  const contactSecondary = record => joinParts([record.email, record.phone, record.destination, record.city]);
  const destinationSecondary = record => joinParts([record.iata_code, record.country]);
  const userSecondary = record => joinParts([record.email, record.first_name, record.last_name]);

  [
    { inputId: "product_name", valueKey: "name" },
    { inputId: "product_sku", valueKey: "sku" },
    { inputId: "product_barcode", valueKey: "barcode" },
    { inputId: "product_ean", valueKey: "ean" },
    { inputId: "product_brand", valueKey: "brand" },
    { inputId: "product_color", valueKey: "color" },
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

  [
    { inputId: "category_l1", valueKey: "level_1" },
    { inputId: "category_l2", valueKey: "level_2" },
    { inputId: "category_l3", valueKey: "level_3" },
    { inputId: "category_l4", valueKey: "level_4" },
  ].forEach(config => {
    attachRecordAutocomplete({
      inputId: config.inputId,
      datasetName: "categories",
      valueKey: config.valueKey,
      searchKeys: ["name", "parent", "path", "level_1", "level_2", "level_3", "level_4"],
      fill: fillProductCategories,
      render: record => ({
        primary: record[config.valueKey] || record.name,
        secondary: categorySecondary(record),
      }),
    });
  });

  attachRecordAutocomplete({
    inputId: "product_warehouse",
    datasetName: "warehouses",
    valueKey: "name",
    searchKeys: ["name", "code"],
    fill: record => setFieldValue("product_warehouse", record.name),
    render: record => ({
      primary: record.name,
      secondary: record.code || "",
    }),
  });

  [
    { inputId: "product_zone", valueKey: "zone" },
    { inputId: "product_aisle", valueKey: "aisle" },
    { inputId: "product_shelf", valueKey: "shelf" },
    { inputId: "product_rack_color", valueKey: "rack_color" },
  ].forEach(config => {
    attachRecordAutocomplete({
      inputId: config.inputId,
      datasetName: "locations",
      valueKey: config.valueKey,
      searchKeys: ["warehouse", "zone", "aisle", "shelf", "rack_color", "notes", "label"],
      fill: fillProductLocation,
      render: record => ({
        primary: record[config.valueKey] || record.label,
        secondary: locationSecondary(record),
      }),
    });
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
    fill: record => setFieldValue("loc_warehouse", record.name),
    render: record => ({
      primary: record.name,
      secondary: record.code || "",
    }),
  });

  [
    { inputId: "loc_zone", valueKey: "zone" },
    { inputId: "loc_aisle", valueKey: "aisle" },
    { inputId: "loc_shelf", valueKey: "shelf" },
    { inputId: "loc_color", valueKey: "rack_color" },
    { inputId: "loc_notes", valueKey: "notes" },
  ].forEach(config => {
    attachRecordAutocomplete({
      inputId: config.inputId,
      datasetName: "locations",
      valueKey: config.valueKey,
      searchKeys: ["warehouse", "zone", "aisle", "shelf", "rack_color", "notes", "label"],
      fill: fillLocation,
      render: record => ({
        primary: record[config.valueKey] || record.label,
        secondary: locationSecondary(record),
      }),
    });
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
      searchKeys: ["name", "email", "phone", "tags", "destination", "address_line1", "city"],
      fill: fillContact,
      render: record => ({
        primary: record[config.valueKey] || record.label,
        secondary: contactSecondary(record),
      }),
    });
  });

  attachRecordAutocomplete({
    inputId: "contact_destination",
    datasetName: "destinations",
    valueKey: "label",
    searchKeys: ["label", "city", "iata_code", "country"],
    fill: fillDestination,
    render: record => ({
      primary: record.label,
      secondary: destinationSecondary(record),
    }),
  });

  attachTokenAutocomplete({
    inputId: "contact_tags",
    datasetName: "contact_tags",
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
})();
