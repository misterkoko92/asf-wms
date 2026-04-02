(() => {
  const shipmentForm = document.getElementById('shipment-form');
  if (!shipmentForm) {
    return;
  }

  shipmentForm.dataset.shipmentsModuleReady = '1';
  document.body.dataset.scanShipmentEditor = '1';
})();
