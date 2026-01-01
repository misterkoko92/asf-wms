(function () {
  const SEARCH_URL = "https://nominatim.openstreetmap.org/search";
  const REVERSE_URL = "https://nominatim.openstreetmap.org/reverse";
  const MIN_CHARS = 3;
  const MAX_RESULTS = 6;
  const DEBOUNCE_MS = 350;

  const hasFetch = typeof window.fetch === "function";
  if (!hasFetch) {
    return;
  }

  const normalize = value => (value || "").trim();

  const buildLine1 = address => {
    if (!address) {
      return "";
    }
    const parts = [];
    if (address.house_number) {
      parts.push(address.house_number);
    }
    if (address.road) {
      parts.push(address.road);
    } else if (address.pedestrian) {
      parts.push(address.pedestrian);
    } else if (address.neighbourhood) {
      parts.push(address.neighbourhood);
    } else if (address.suburb) {
      parts.push(address.suburb);
    }
    return parts.join(" ").trim();
  };

  const extractCity = address =>
    address.city ||
    address.town ||
    address.village ||
    address.hamlet ||
    address.county ||
    "";

  const extractAddress = item => {
    const address = item.address || {};
    const line1 = buildLine1(address) || normalize(item.display_name || "").split(",")[0];
    return {
      label: item.display_name || line1,
      line1,
      postal_code: address.postcode || "",
      city: extractCity(address),
      country: address.country || "",
    };
  };

  const showStatus = (host, message, type) => {
    if (!host) {
      return;
    }
    let status = host.querySelector(".address-autocomplete-status");
    if (!status) {
      status = document.createElement("div");
      status.className = "address-autocomplete-status";
      host.appendChild(status);
    }
    status.textContent = message;
    status.classList.remove("info", "error");
    if (type) {
      status.classList.add(type);
    }
    window.clearTimeout(status._clearTimer);
    status._clearTimer = window.setTimeout(() => {
      status.textContent = "";
      status.classList.remove("info", "error");
    }, 4000);
  };

  const createList = host => {
    let list = host.querySelector(".address-autocomplete-list");
    if (!list) {
      list = document.createElement("div");
      list.className = "address-autocomplete-list";
      host.appendChild(list);
    }
    return list;
  };

  const closeList = list => {
    if (!list) {
      return;
    }
    list.classList.remove("is-open");
    list.innerHTML = "";
  };

  const renderResults = (list, results, onSelect) => {
    list.innerHTML = "";
    if (!results.length) {
      closeList(list);
      return;
    }
    results.forEach(result => {
      const item = document.createElement("button");
      item.type = "button";
      item.className = "address-autocomplete-item";
      item.textContent = result.label;
      item.addEventListener("click", () => {
        onSelect(result);
        closeList(list);
      });
      list.appendChild(item);
    });
    list.classList.add("is-open");
  };

  const buildSearchUrl = query => {
    const params = new URLSearchParams({
      format: "jsonv2",
      addressdetails: "1",
      limit: String(MAX_RESULTS),
      q: query,
    });
    return `${SEARCH_URL}?${params.toString()}`;
  };

  const buildReverseUrl = (lat, lon) => {
    const params = new URLSearchParams({
      format: "jsonv2",
      addressdetails: "1",
      zoom: "18",
      lat: String(lat),
      lon: String(lon),
    });
    return `${REVERSE_URL}?${params.toString()}`;
  };

  const fillFields = (fields, data) => {
    if (!data) {
      return;
    }
    if (fields.line1 && data.line1) {
      fields.line1.value = data.line1;
    }
    if (fields.postal_code && data.postal_code) {
      fields.postal_code.value = data.postal_code;
    }
    if (fields.city && data.city) {
      fields.city.value = data.city;
    }
    if (fields.country && data.country) {
      fields.country.value = data.country;
    }
  };

  const attachAutocomplete = fields => {
    const line1 = fields.line1;
    if (!line1 || line1.dataset.autocompleteInit === "1") {
      return;
    }
    line1.dataset.autocompleteInit = "1";

    const host = line1.parentElement;
    if (host) {
      host.classList.add("address-autocomplete-host");
    }
    const list = createList(host);
    let controller = null;
    let timer = null;
    let lastQuery = "";

    const runSearch = query => {
      if (controller) {
        controller.abort();
      }
      controller = new AbortController();
      fetch(buildSearchUrl(query), {
        headers: { "Accept-Language": "fr" },
        signal: controller.signal,
      })
        .then(response => (response.ok ? response.json() : []))
        .then(results => {
          const mapped = (results || []).map(extractAddress).filter(item => item.label);
          renderResults(list, mapped, data => fillFields(fields, data));
        })
        .catch(() => {
          closeList(list);
        });
    };

    line1.addEventListener("input", () => {
      const query = normalize(line1.value);
      if (query.length < MIN_CHARS) {
        closeList(list);
        lastQuery = query;
        return;
      }
      if (query === lastQuery) {
        return;
      }
      lastQuery = query;
      if (timer) {
        window.clearTimeout(timer);
      }
      timer = window.setTimeout(() => runSearch(query), DEBOUNCE_MS);
    });

    line1.addEventListener("keydown", event => {
      if (event.key === "Escape") {
        closeList(list);
      }
    });

    document.addEventListener("click", event => {
      if (!host || host.contains(event.target)) {
        return;
      }
      closeList(list);
    });

    const allowGeo = line1.dataset.autocompleteGeo !== "0";
    if (allowGeo) {
      const geoButton = document.createElement("button");
      geoButton.type = "button";
      geoButton.className = "address-autocomplete-geo-btn";
      geoButton.textContent = "Utiliser ma position";
      geoButton.addEventListener("click", () => {
        if (!navigator.geolocation) {
          showStatus(host, "Geolocalisation indisponible.", "error");
          return;
        }
        showStatus(host, "Recherche de votre position...", "info");
        navigator.geolocation.getCurrentPosition(
          position => {
            const { latitude, longitude } = position.coords || {};
            fetch(buildReverseUrl(latitude, longitude), {
              headers: { "Accept-Language": "fr" },
            })
              .then(response => (response.ok ? response.json() : null))
              .then(result => {
                if (!result) {
                  showStatus(host, "Adresse introuvable.", "error");
                  return;
                }
                fillFields(fields, extractAddress(result));
                showStatus(host, "Adresse renseignee.", "info");
              })
              .catch(() => {
                showStatus(host, "Adresse introuvable.", "error");
              });
          },
          () => {
            showStatus(host, "Geolocalisation refusee.", "error");
          }
        );
      });
      host.appendChild(geoButton);
    }
  };

  const attachFromDataAttributes = () => {
    const line1Inputs = document.querySelectorAll('[data-address-field="line1"]');
    line1Inputs.forEach(line1 => {
      const group = line1.dataset.addressGroup || "";
      const scope = line1.form || document;
      const findField = name => {
        const selector = `[data-address-field="${name}"]${group ? `[data-address-group="${group}"]` : ""}`;
        return scope.querySelector(selector);
      };
      attachAutocomplete({
        line1,
        line2: findField("line2"),
        postal_code: findField("postal_code"),
        city: findField("city"),
        country: findField("country"),
      });
    });
  };

  const attachFromAdmin = () => {
    const line1Inputs = document.querySelectorAll('input[name$="address_line1"]');
    line1Inputs.forEach(line1 => {
      if (line1.closest("[data-address-field]")) {
        return;
      }
      const row = line1.closest("tr") || line1.parentElement;
      if (!row) {
        return;
      }
      const selectField = suffix =>
        row.querySelector(`input[name$="${suffix}"]`) ||
        row.querySelector(`select[name$="${suffix}"]`);
      attachAutocomplete({
        line1,
        line2: selectField("address_line2"),
        postal_code: selectField("postal_code"),
        city: selectField("city"),
        country: selectField("country"),
      });
    });
  };

  attachFromDataAttributes();
  if (document.body && document.body.classList.contains("model-contact")) {
    attachFromAdmin();
  }
})();
