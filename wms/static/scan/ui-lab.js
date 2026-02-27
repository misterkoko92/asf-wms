(() => {
  const preview = document.getElementById("ui-lab-preview");
  const paletteSelect = document.getElementById("ui-lab-palette");
  const typographySelect = document.getElementById("ui-lab-typography");
  const densitySelect = document.getElementById("ui-lab-density");

  if (!preview || !paletteSelect || !typographySelect || !densitySelect) {
    return;
  }

  const storageKey = "wms-ui-lab-settings";
  const allowed = {
    palette: new Set(["sage", "mist", "tea"]),
    typography: new Set(["manrope-source", "dm-nunito", "aptos-like"]),
    density: new Set(["compact", "standard", "airy"]),
  };

  const normalize = (value, kind, fallback) => {
    if (allowed[kind].has(value)) {
      return value;
    }
    return fallback;
  };

  const applySettings = (settings) => {
    preview.dataset.uiLabPalette = settings.palette;
    preview.dataset.uiLabTypography = settings.typography;
    preview.dataset.uiLabDensity = settings.density;
    paletteSelect.value = settings.palette;
    typographySelect.value = settings.typography;
    densitySelect.value = settings.density;
  };

  const readCurrent = () => ({
    palette: normalize(paletteSelect.value, "palette", "sage"),
    typography: normalize(typographySelect.value, "typography", "manrope-source"),
    density: normalize(densitySelect.value, "density", "standard"),
  });

  const save = (settings) => {
    try {
      localStorage.setItem(storageKey, JSON.stringify(settings));
    } catch (err) {
      // Ignore storage errors in sandbox.
    }
  };

  const load = () => {
    try {
      const raw = localStorage.getItem(storageKey);
      if (!raw) {
        return null;
      }
      const parsed = JSON.parse(raw);
      return {
        palette: normalize(parsed.palette, "palette", "sage"),
        typography: normalize(parsed.typography, "typography", "manrope-source"),
        density: normalize(parsed.density, "density", "standard"),
      };
    } catch (err) {
      return null;
    }
  };

  const persisted = load();
  if (persisted) {
    applySettings(persisted);
  } else {
    applySettings(readCurrent());
  }

  [paletteSelect, typographySelect, densitySelect].forEach((control) => {
    control.addEventListener("change", () => {
      const nextSettings = readCurrent();
      applySettings(nextSettings);
      save(nextSettings);
    });
  });
})();
