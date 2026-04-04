(() => {
  const shipmentForm = document.getElementById('shipment-form');
  if (!shipmentForm) {
    return;
  }

  const destinationSelect = document.getElementById('id_destination');
  const contactManagementLinks = Array.from(
    document.querySelectorAll('[data-contact-management-link="1"]')
  );

  const syncContactManagementLinks = () => {
    const destinationId = destinationSelect ? String(destinationSelect.value || '').trim() : '';
    contactManagementLinks.forEach((link) => {
      const baseHref = link.dataset.baseHref || link.getAttribute('href') || '';
      if (!baseHref) {
        return;
      }
      const nextHref = destinationId
        ? `${baseHref}?destination_id=${encodeURIComponent(destinationId)}`
        : baseHref;
      link.setAttribute('href', nextHref);
    });
  };

  if (destinationSelect && contactManagementLinks.length) {
    destinationSelect.addEventListener('change', syncContactManagementLinks);
    syncContactManagementLinks();
  }

  shipmentForm.dataset.shipmentsModuleReady = '1';
  document.body.dataset.scanShipmentEditor = '1';
})();
