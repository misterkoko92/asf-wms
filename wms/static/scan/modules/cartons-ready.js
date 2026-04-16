(() => {
  const root = document.querySelector('[data-carton-bulk-root="1"]');
  if (!root) {
    return;
  }

  const bulkActionSelect = root.querySelector('[name="bulk_action"]');
  const toolbarShipmentSelect = root.querySelector('[data-carton-toolbar-shipment-select="1"]');
  const confirmInput = root.querySelector('[data-carton-confirm-skipped-input="1"]');
  const selectAllButton = root.querySelector('[data-carton-select-all="1"]');
  const overlay = root.querySelector('#carton-status-skip-confirmation-overlay');
  const message = root.querySelector('#carton-status-skip-confirmation-message');
  const acceptButton = root.querySelector('[data-carton-confirm-accept="1"]');
  const cancelButton = root.querySelector('[data-carton-confirm-cancel="1"]');
  const shipmentField = root.querySelector('[data-carton-confirm-shipment-field="1"]');
  const shipmentSelect = root.querySelector('[data-carton-confirm-shipment-select="1"]');
  const shipmentError = root.querySelector('[data-carton-confirm-shipment-error="1"]');

  const visibleFlow = ['draft', 'picking', 'packed', 'assigned', 'labeled'];
  const visibleLabels = {
    draft: 'Créé',
    picking: 'En préparation',
    packed: 'Disponible',
    assigned: 'Affecté',
    labeled: 'Étiqueté'
  };
  const targetByAction = {
    bulk_update_cartons_picking: 'picking',
    bulk_update_cartons_packed: 'packed',
    bulk_assign_cartons_shipment: 'assigned',
    bulk_mark_cartons_assigned: 'assigned',
    bulk_mark_cartons_labeled: 'labeled'
  };

  function getSelectedCheckboxes() {
    return Array.from(root.querySelectorAll('.scan-carton-select-checkbox:checked'));
  }

  function getAllCheckboxes() {
    return Array.from(root.querySelectorAll('.scan-carton-select-checkbox'));
  }

  function updateSelectAllButtonState() {
    if (!selectAllButton) {
      return;
    }
    const checkboxes = getAllCheckboxes();
    const allSelected = checkboxes.length > 0 && checkboxes.every(checkbox => checkbox.checked);
    selectAllButton.setAttribute('aria-pressed', allSelected ? 'true' : 'false');
  }

  function resolveAction() {
    const action = bulkActionSelect ? (bulkActionSelect.value || '').trim() : '';
    if (action) {
      return action;
    }
    const selected = getSelectedCheckboxes();
    const shipmentId = toolbarShipmentSelect ? (toolbarShipmentSelect.value || '').trim() : '';
    if (shipmentId && selected.length) {
      return 'bulk_assign_cartons_shipment';
    }
    return '';
  }

  function getAchievedSteps(checkbox) {
    const achieved = new Set(['draft']);
    const preparationStatus = checkbox.dataset.cartonPreparationStatus || '';
    const rawStatus = checkbox.dataset.cartonStatusValue || '';
    const isAssigned =
      checkbox.dataset.cartonAssigned === '1' ||
      Boolean((checkbox.dataset.cartonShipmentId || '').trim()) ||
      rawStatus === 'assigned' ||
      rawStatus === 'labeled' ||
      rawStatus === 'shipped';

    if (preparationStatus === 'picking' || preparationStatus === 'packed' || preparationStatus === 'labeled') {
      achieved.add('picking');
    }
    if (preparationStatus === 'packed' || preparationStatus === 'labeled') {
      achieved.add('packed');
    }
    if (isAssigned) {
      achieved.add('assigned');
    }
    if (rawStatus === 'labeled' || rawStatus === 'shipped') {
      achieved.add('labeled');
    }

    return achieved;
  }

  function getSkippedLabels(checkbox, targetStep) {
    const targetIndex = visibleFlow.indexOf(targetStep);
    if (targetIndex <= 0) {
      return [];
    }
    const achieved = getAchievedSteps(checkbox);
    return visibleFlow
      .slice(0, targetIndex)
      .filter(step => !achieved.has(step))
      .map(step => visibleLabels[step]);
  }

  function formatLabels(labels) {
    if (!labels.length) {
      return '';
    }
    if (labels.length === 1) {
      return labels[0];
    }
    if (labels.length === 2) {
      return `${labels[0]} et ${labels[1]}`;
    }
    return `${labels.slice(0, -1).join(', ')} et ${labels[labels.length - 1]}`;
  }

  function setOverlayVisible(visible) {
    if (!overlay) {
      return;
    }
    overlay.hidden = !visible;
    overlay.setAttribute('aria-hidden', visible ? 'false' : 'true');
    overlay.classList.toggle('active', visible);
  }

  function resetConfirmationState() {
    if (confirmInput) {
      confirmInput.value = '';
    }
    if (shipmentError) {
      shipmentError.classList.add('scan-hidden');
    }
  }

  function openConfirmationModal({ action, targetStep, skippedLabels, selectedCheckboxes }) {
    if (!overlay || !message || !acceptButton || !cancelButton) {
      return false;
    }

    const targetLabel = visibleLabels[targetStep] || targetStep;
    const plural = selectedCheckboxes.length > 1;
    message.textContent = `${plural ? 'Les étapes' : "L'étape"} ${formatLabels(skippedLabels)} seront considérées faites et ${plural ? 'les colis sélectionnés seront marqués' : 'le colis sera marqué'} « ${targetLabel} » directement.`;

    const requiresShipmentSelection = action === 'bulk_mark_cartons_labeled';
    if (shipmentField) {
      shipmentField.classList.toggle('scan-hidden', !requiresShipmentSelection);
    }

    if (requiresShipmentSelection && shipmentSelect) {
      const toolbarValue = toolbarShipmentSelect ? (toolbarShipmentSelect.value || '').trim() : '';
      const selectedShipmentIds = Array.from(
        new Set(
          selectedCheckboxes
            .map(checkbox => (checkbox.dataset.cartonShipmentId || '').trim())
            .filter(Boolean)
        )
      );
      const preselectedShipmentId =
        toolbarValue || (selectedShipmentIds.length === 1 ? selectedShipmentIds[0] : '');
      shipmentSelect.value = preselectedShipmentId;
    }

    setOverlayVisible(true);

    const cleanup = ({ reset = true } = {}) => {
      acceptButton.removeEventListener('click', handleAccept);
      cancelButton.removeEventListener('click', handleCancel);
      overlay.removeEventListener('click', handleOverlayClick);
      setOverlayVisible(false);
      if (reset) {
        resetConfirmationState();
      }
    };

    const handleAccept = () => {
      if (requiresShipmentSelection && shipmentSelect) {
        const shipmentId = (shipmentSelect.value || '').trim();
        if (!shipmentId) {
          if (shipmentError) {
            shipmentError.classList.remove('scan-hidden');
          }
          shipmentSelect.focus();
          return;
        }
        if (toolbarShipmentSelect) {
          toolbarShipmentSelect.value = shipmentId;
        }
      }
      if (confirmInput) {
        confirmInput.value = '1';
      }
      cleanup({ reset: false });
      root.submit();
    };

    const handleCancel = () => {
      cleanup();
    };

    const handleOverlayClick = event => {
      if (event.target === overlay) {
        cleanup();
      }
    };

    acceptButton.addEventListener('click', handleAccept);
    cancelButton.addEventListener('click', handleCancel);
    overlay.addEventListener('click', handleOverlayClick);
    return true;
  }

  if (selectAllButton) {
    selectAllButton.addEventListener('click', () => {
      const checkboxes = getAllCheckboxes();
      if (!checkboxes.length) {
        return;
      }
      const allSelected = checkboxes.every(checkbox => checkbox.checked);
      checkboxes.forEach(checkbox => {
        checkbox.checked = !allSelected;
      });
      updateSelectAllButtonState();
    });
  }

  getAllCheckboxes().forEach(checkbox => {
    checkbox.addEventListener('change', updateSelectAllButtonState);
  });
  updateSelectAllButtonState();

  root.addEventListener('submit', event => {
    const submitter = event.submitter;
    if (submitter && submitter.name === 'bulk_document') {
      return;
    }

    resetConfirmationState();

    const selectedCheckboxes = getSelectedCheckboxes();
    if (!selectedCheckboxes.length) {
      return;
    }

    const action = resolveAction();
    const targetStep = targetByAction[action];
    if (!targetStep) {
      return;
    }

    const skippedLabels = Array.from(
      new Set(
        selectedCheckboxes.flatMap(checkbox => getSkippedLabels(checkbox, targetStep))
      )
    );

    if (!skippedLabels.length) {
      return;
    }

    event.preventDefault();
    openConfirmationModal({ action, targetStep, skippedLabels, selectedCheckboxes });
  });
})();
