(function () {
  function arrayBufferToBase64(buffer) {
    const bytes = new Uint8Array(buffer);
    let binary = "";
    bytes.forEach((byte) => {
      binary += String.fromCharCode(byte);
    });
    return window.btoa(binary);
  }

  function helperUnavailableMessage() {
    return "Le helper local est indisponible. Vérifiez qu'il est démarré sur ce poste.";
  }

  function isHelperUnavailableError(error) {
    const message = String((error && error.message) || "");
    return /helper local/i.test(message) || /Failed to fetch/i.test(message);
  }

  function appendQueryParam(url, name, value) {
    const nextUrl = new URL(url, window.location.href);
    nextUrl.searchParams.set(name, value);
    return nextUrl.toString();
  }

  function showAlert(root, message, tone) {
    const alertNode = root.querySelector("[data-local-document-helper-error]");
    if (!alertNode) {
      return;
    }
    alertNode.textContent = message;
    alertNode.classList.remove("d-none", "alert-danger", "alert-warning", "alert-success");
    alertNode.classList.add(`alert-${tone}`);
  }

  function clearAlert(root) {
    const alertNode = root.querySelector("[data-local-document-helper-error]");
    if (!alertNode) {
      return;
    }
    alertNode.textContent = "";
    alertNode.classList.remove("alert-danger", "alert-warning", "alert-success");
    alertNode.classList.add("d-none");
  }

  function showError(root, message) {
    showAlert(root, message, "danger");
  }

  function showWarning(root, message) {
    showAlert(root, message, "warning");
  }

  function installPanel(root) {
    return root.querySelector("[data-local-document-helper-install-panel]");
  }

  function installStatusNode(root) {
    return root.querySelector("[data-local-document-helper-install-status]");
  }

  function hideInstallAssistant(root) {
    const panel = installPanel(root);
    if (panel) {
      panel.classList.add("d-none");
    }
    const statusNode = installStatusNode(root);
    if (statusNode) {
      statusNode.textContent = "";
      statusNode.classList.add("d-none");
    }
  }

  function showInstallStatus(root, message) {
    const statusNode = installStatusNode(root);
    if (!statusNode) {
      return;
    }
    statusNode.textContent = message;
    statusNode.classList.remove("d-none");
  }

  function showInstallAssistant(root, retryAction) {
    const panel = installPanel(root);
    if (panel) {
      panel.classList.remove("d-none");
    }
    root._localDocumentHelperRetryAction = retryAction;
    showWarning(root, helperUnavailableMessage());
  }

  async function copyInstallCommand(root) {
    const command = root.dataset.localDocumentHelperInstallCommand || "";
    if (!command) {
      showInstallStatus(root, "Aucune commande d'installation disponible.");
      return;
    }
    try {
      await navigator.clipboard.writeText(command);
      showInstallStatus(root, "Commande d'installation copiee. Lancez-la, puis cliquez sur Reessayer.");
    } catch (error) {
      showInstallStatus(root, "Copie impossible. Lancez manuellement la commande affichee ci-dessous.");
    }
  }

  function retryPendingAction(root) {
    const action = root._localDocumentHelperRetryAction;
    if (!action) {
      showInstallStatus(root, "Lancez l'installation, puis recliquez sur le bouton voulu.");
      return;
    }
    action();
  }

  async function fetchJson(url) {
    const response = await fetch(url, {
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
      },
    });
    let payload = {};
    try {
      payload = await response.json();
    } catch (error) {
      payload = {};
    }
    if (!response.ok) {
      throw new Error(payload.error || `Erreur HTTP ${response.status}`);
    }
    return payload;
  }

  async function fetchDocument(documentEntry) {
    const response = await fetch(documentEntry.download_url, {
      credentials: "same-origin",
      headers: {
        Accept: "*/*",
      },
    });
    if (!response.ok) {
      throw new Error(`Telechargement impossible (${response.status})`);
    }
    return {
      filename: documentEntry.filename,
      content_base64: arrayBufferToBase64(await response.arrayBuffer()),
    };
  }

  async function postToHelper(root, payload) {
    const helperUrl = `http://${root.dataset.localDocumentHelperOrigin}/v1/pdf/render`;
    let response;
    try {
      response = await fetch(helperUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-ASF-Planning-Helper": "1",
        },
        body: JSON.stringify(payload),
      });
    } catch (error) {
      throw new Error(helperUnavailableMessage());
    }
    let responsePayload = {};
    try {
      responsePayload = await response.json();
    } catch (error) {
      responsePayload = {};
    }
    if (!response.ok) {
      throw new Error(responsePayload.error || "Le helper local a refuse la requete.");
    }
    return responsePayload;
  }

  async function renderPdfFromLink(root, link) {
    const jobUrl = appendQueryParam(link.href, "helper", "1");
    const jobPayload = await fetchJson(jobUrl);
    const documents = await Promise.all((jobPayload.documents || []).map(fetchDocument));
    const helperResponse = await postToHelper(root, {
      ...jobPayload,
      documents,
    });
    if ((helperResponse.warning_messages || []).length) {
      showWarning(root, helperResponse.warning_messages.join(" "));
      return;
    }
    clearAlert(root);
    hideInstallAssistant(root);
  }

  function attachInstallControls(root) {
    const installLink = root.querySelector("[data-local-document-helper-install-link]");
    if (installLink) {
      installLink.addEventListener("click", function () {
        showInstallStatus(
          root,
          "Installeur telecharge. Lancez-le sur ce poste, puis cliquez sur Reessayer."
        );
      });
    }
    const copyButton = root.querySelector("[data-local-document-helper-copy-command]");
    if (copyButton) {
      copyButton.addEventListener("click", function () {
        copyInstallCommand(root);
      });
    }
    const retryButton = root.querySelector("[data-local-document-helper-retry]");
    if (retryButton) {
      retryButton.addEventListener("click", function () {
        retryPendingAction(root);
      });
    }
    const dismissButton = root.querySelector("[data-local-document-helper-dismiss]");
    if (dismissButton) {
      dismissButton.addEventListener("click", function () {
        hideInstallAssistant(root);
      });
    }
  }

  function attachDocumentLinks(root) {
    root.querySelectorAll("[data-local-document-helper-link]").forEach((link) => {
      link.addEventListener("click", function (event) {
        if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey) {
          return;
        }
        event.preventDefault();
        hideInstallAssistant(root);
        clearAlert(root);
        const previousAriaDisabled = link.getAttribute("aria-disabled");
        link.setAttribute("aria-disabled", "true");
        link.classList.add("disabled");
        renderPdfFromLink(root, link)
          .catch((error) => {
            if (isHelperUnavailableError(error)) {
              showInstallAssistant(root, function () {
                renderPdfFromLink(root, link).catch((retryError) => {
                  showError(root, retryError.message || "Une erreur est survenue.");
                });
              });
              return;
            }
            showError(root, error.message || "Une erreur est survenue.");
          })
          .finally(() => {
            if (previousAriaDisabled === null) {
              link.removeAttribute("aria-disabled");
            } else {
              link.setAttribute("aria-disabled", previousAriaDisabled);
            }
            link.classList.remove("disabled");
          });
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-local-document-helper-root]").forEach((root) => {
      attachInstallControls(root);
      attachDocumentLinks(root);
    });
  });
})();
