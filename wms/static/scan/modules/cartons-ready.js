(() => {
  const root = document.querySelector('[data-carton-bulk-root="1"]');
  if (!root) {
    return;
  }

  const bulkActionSelect = root.querySelector('[name="bulk_action"]');
  const toolbarShipmentSelect = root.querySelector('[data-carton-toolbar-shipment-select="1"]');
  const confirmInput = root.querySelector('[data-carton-confirm-skipped-input="1"]');
  const preassignmentConfirmInput = root.querySelector(
    '[data-carton-preassignment-confirm-input="1"]'
  );
  const selectAllCheckbox = root.querySelector('[data-carton-select-all="1"]');
  const overlay = root.querySelector('#carton-status-skip-confirmation-overlay');
  const message = root.querySelector('#carton-status-skip-confirmation-message');
  const acceptButton = root.querySelector('[data-carton-confirm-accept="1"]');
  const cancelButton = root.querySelector('[data-carton-confirm-cancel="1"]');
  const shipmentField = root.querySelector('[data-carton-confirm-shipment-field="1"]');
  const shipmentSelect = root.querySelector('[data-carton-confirm-shipment-select="1"]');
  const shipmentError = root.querySelector('[data-carton-confirm-shipment-error="1"]');
  const preassignmentOverlay = root.querySelector('#carton-preassignment-mismatch-overlay');
  const preassignmentMessage = root.querySelector('#carton-preassignment-mismatch-message');
  const preassignmentAcceptButton = root.querySelector(
    '[data-carton-preassignment-accept="1"]'
  );
  const preassignmentRemoveButton = root.querySelector('[data-carton-preassignment-remove="1"]');
  const preassignmentCancelButton = root.querySelector('[data-carton-preassignment-cancel="1"]');

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

  function updateSelectAllCheckboxState() {
    if (!selectAllCheckbox) {
      return;
    }
    const checkboxes = getAllCheckboxes();
    const checkedCount = checkboxes.filter(checkbox => checkbox.checked).length;
    selectAllCheckbox.disabled = checkboxes.length === 0;
    selectAllCheckbox.checked = checkboxes.length > 0 && checkedCount === checkboxes.length;
    selectAllCheckbox.indeterminate = checkedCount > 0 && checkedCount < checkboxes.length;
  }

  function clearConfirmationInputs() {
    if (confirmInput) {
      confirmInput.value = '';
    }
    if (preassignmentConfirmInput) {
      preassignmentConfirmInput.value = '';
    }
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

  function setPreassignmentOverlayVisible(visible) {
    if (!preassignmentOverlay) {
      return;
    }
    preassignmentOverlay.hidden = !visible;
    preassignmentOverlay.setAttribute('aria-hidden', visible ? 'false' : 'true');
    preassignmentOverlay.classList.toggle('active', visible);
  }

  function resetConfirmationState() {
    if (shipmentError) {
      shipmentError.classList.add('scan-hidden');
    }
  }

  function openConfirmationModal({
    action,
    targetStep,
    skippedLabels,
    selectedCheckboxes,
    onAccept,
    onCancel
  }) {
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
      if (typeof onAccept === 'function') {
        onAccept();
      }
    };

    const handleCancel = () => {
      cleanup();
      if (typeof onCancel === 'function') {
        onCancel();
      }
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

  function getSelectedShipmentOption() {
    if (!toolbarShipmentSelect) {
      return null;
    }
    const shipmentId = (toolbarShipmentSelect.value || '').trim();
    if (!shipmentId) {
      return null;
    }
    return toolbarShipmentSelect.querySelector(`option[value="${shipmentId}"]`);
  }

  function getPreassignmentMismatches(selectedCheckboxes) {
    const targetOption = getSelectedShipmentOption();
    const shipmentDestinationId = targetOption
      ? (targetOption.dataset.shipmentDestinationId || '').trim()
      : '';
    if (!shipmentDestinationId) {
      return [];
    }
    return selectedCheckboxes.filter(checkbox => {
      const cartonDestinationId = (checkbox.dataset.cartonPreassignedDestinationId || '').trim();
      return Boolean(cartonDestinationId) && cartonDestinationId !== shipmentDestinationId;
    });
  }

  function openPreassignmentMismatchModal({
    mismatches,
    onAccept,
    onRemove,
    onCancel
  }) {
    if (
      !preassignmentOverlay ||
      !preassignmentMessage ||
      !preassignmentAcceptButton ||
      !preassignmentRemoveButton ||
      !preassignmentCancelButton
    ) {
      return false;
    }

    const targetOption = getSelectedShipmentOption();
    const shipmentLabel = targetOption ? targetOption.textContent.trim() : '';
    const cartonCodes = mismatches
      .map(checkbox => (checkbox.dataset.cartonCode || '').trim())
      .filter(Boolean);
    const conflictCodes = cartonCodes.join(', ');
    const plural = cartonCodes.length > 1;
    preassignmentMessage.textContent =
      `${plural ? 'Les colis' : 'Le colis'} ${conflictCodes} ` +
      `${plural ? 'sont pré-affectés' : 'est pré-affecté'} à une autre destination ` +
      `et ${plural ? 'vont être affectés' : 'va être affecté'} à ${shipmentLabel}.`;

    setPreassignmentOverlayVisible(true);

    const cleanup = () => {
      preassignmentAcceptButton.removeEventListener('click', handleAccept);
      preassignmentRemoveButton.removeEventListener('click', handleRemove);
      preassignmentCancelButton.removeEventListener('click', handleCancel);
      preassignmentOverlay.removeEventListener('click', handleOverlayClick);
      setPreassignmentOverlayVisible(false);
    };

    const handleAccept = () => {
      cleanup();
      if (preassignmentConfirmInput) {
        preassignmentConfirmInput.value = '1';
      }
      if (typeof onAccept === 'function') {
        onAccept();
      }
    };

    const handleRemove = () => {
      cleanup();
      mismatches.forEach(checkbox => {
        checkbox.checked = false;
      });
      updateSelectAllCheckboxState();
      if (typeof onRemove === 'function') {
        onRemove();
      }
    };

    const handleCancel = () => {
      cleanup();
      clearConfirmationInputs();
      if (typeof onCancel === 'function') {
        onCancel();
      }
    };

    const handleOverlayClick = event => {
      if (event.target === preassignmentOverlay) {
        handleCancel();
      }
    };

    preassignmentAcceptButton.addEventListener('click', handleAccept);
    preassignmentRemoveButton.addEventListener('click', handleRemove);
    preassignmentCancelButton.addEventListener('click', handleCancel);
    preassignmentOverlay.addEventListener('click', handleOverlayClick);
    return true;
  }

  function continueAfterMismatchCheck({ action, targetStep, selectedCheckboxes, skippedLabels }) {
    if (skippedLabels.length && (!confirmInput || confirmInput.value !== '1')) {
      openConfirmationModal({
        action,
        targetStep,
        skippedLabels,
        selectedCheckboxes,
        onAccept: () => root.submit(),
        onCancel: () => clearConfirmationInputs()
      });
      return;
    }
    root.submit();
  }

  if (selectAllCheckbox) {
    selectAllCheckbox.addEventListener('change', () => {
      const checkboxes = getAllCheckboxes();
      if (!checkboxes.length) {
        return;
      }
      checkboxes.forEach(checkbox => {
        checkbox.checked = selectAllCheckbox.checked;
      });
      updateSelectAllCheckboxState();
    });
  }

  getAllCheckboxes().forEach(checkbox => {
    checkbox.addEventListener('change', () => {
      clearConfirmationInputs();
      updateSelectAllCheckboxState();
    });
  });
  updateSelectAllCheckboxState();

  [bulkActionSelect, toolbarShipmentSelect].forEach(field => {
    if (!field) {
      return;
    }
    field.addEventListener('change', () => {
      clearConfirmationInputs();
      resetConfirmationState();
    });
  });

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

    const mismatches =
      action === 'bulk_assign_cartons_shipment' &&
      (!preassignmentConfirmInput || preassignmentConfirmInput.value !== '1')
        ? getPreassignmentMismatches(selectedCheckboxes)
        : [];

    const skippedLabels = Array.from(
      new Set(
        selectedCheckboxes.flatMap(checkbox => getSkippedLabels(checkbox, targetStep))
      )
    );

    if (!mismatches.length && !skippedLabels.length) {
      return;
    }

    event.preventDefault();
    if (mismatches.length) {
      openPreassignmentMismatchModal({
        mismatches,
        onAccept: () =>
          continueAfterMismatchCheck({
            action,
            targetStep,
            selectedCheckboxes,
            skippedLabels
          }),
        onRemove: () => {
          const remainingSelection = getSelectedCheckboxes();
          const remainingSkippedLabels = Array.from(
            new Set(
              remainingSelection.flatMap(checkbox => getSkippedLabels(checkbox, targetStep))
            )
          );
          continueAfterMismatchCheck({
            action,
            targetStep,
            selectedCheckboxes: remainingSelection,
            skippedLabels: remainingSkippedLabels
          });
        },
        onCancel: () => {}
      });
      return;
    }

    openConfirmationModal({
      action,
      targetStep,
      skippedLabels,
      selectedCheckboxes,
      onAccept: () => root.submit(),
      onCancel: () => clearConfirmationInputs()
    });
  });
})();
