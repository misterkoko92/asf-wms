(() => {
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

  setupLiveSync();
})();
