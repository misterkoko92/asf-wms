(function() {
  function onReady(callback) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', callback);
      return;
    }
    callback();
  }

  function setupPortalOnboarding() {
    const modal = document.getElementById('portal-onboarding-wizard');
    if (!modal) {
      return;
    }

    const steps = Array.from(modal.querySelectorAll('[data-portal-onboarding-step]'));
    const previousButton = modal.querySelector('[data-portal-onboarding-prev]');
    const nextButton = modal.querySelector('[data-portal-onboarding-next]');
    const doneButton = modal.querySelector('[data-portal-onboarding-done]');
    const counter = modal.querySelector('#portal-onboarding-step-counter');
    const showNextInput = modal.querySelector('#portal-onboarding-show-next');
    const csrfInput = modal.querySelector('input[name="csrfmiddlewaretoken"]');
    const preferenceUrl = modal.dataset.portalOnboardingPreferenceUrl;
    const bootstrapModal = window.bootstrap && window.bootstrap.Modal
      ? window.bootstrap.Modal.getOrCreateInstance(modal)
      : null;
    let currentStep = 0;

    function setStep(nextStep) {
      if (!steps.length) {
        return;
      }
      currentStep = Math.max(0, Math.min(nextStep, steps.length - 1));
      steps.forEach((step, index) => {
        const isActive = index === currentStep;
        step.hidden = !isActive;
        step.classList.toggle('is-active', isActive);
      });
      if (counter) {
        counter.textContent = 'Étape ' + (currentStep + 1) + ' / ' + steps.length;
      }
      if (previousButton) {
        previousButton.disabled = currentStep === 0;
      }
      if (nextButton) {
        nextButton.hidden = currentStep === steps.length - 1;
      }
      if (doneButton) {
        doneButton.hidden = currentStep !== steps.length - 1;
      }
    }

    function savePreference() {
      if (!preferenceUrl) {
        return Promise.resolve();
      }
      const payload = new URLSearchParams();
      payload.set('show_on_next_login', showNextInput && showNextInput.checked ? '1' : '0');
      return fetch(preferenceUrl, {
        method: 'POST',
        credentials: 'same-origin',
        keepalive: true,
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
          'X-CSRFToken': csrfInput ? csrfInput.value : '',
          'X-Requested-With': 'XMLHttpRequest'
        },
        body: payload.toString()
      }).catch(() => null);
    }

    function openWizard() {
      setStep(currentStep);
      if (bootstrapModal) {
        bootstrapModal.show();
        return;
      }
      modal.hidden = false;
      modal.classList.add('show');
      modal.style.display = 'block';
    }

    function closeWizard() {
      if (bootstrapModal) {
        bootstrapModal.hide();
        return;
      }
      savePreference();
      modal.classList.remove('show');
      modal.style.display = 'none';
    }

    if (previousButton) {
      previousButton.addEventListener('click', () => {
        setStep(currentStep - 1);
      });
    }
    if (nextButton) {
      nextButton.addEventListener('click', () => {
        setStep(currentStep + 1);
      });
    }
    if (doneButton) {
      doneButton.addEventListener('click', closeWizard);
    }

    modal.querySelectorAll('.portal-onboarding-actions a').forEach(link => {
      link.addEventListener('click', () => {
        savePreference();
      });
    });
    document.querySelectorAll('[data-portal-onboarding-open]').forEach(link => {
      link.addEventListener('click', event => {
        event.preventDefault();
        openWizard();
      });
    });
    modal.addEventListener('hidden.bs.modal', savePreference);

    setStep(0);
    if (modal.dataset.portalOnboardingAutoOpen === '1') {
      openWizard();
    }
  }

  onReady(setupPortalOnboarding);
})();
