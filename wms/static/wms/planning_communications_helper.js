(function () {
  function arrayBufferToBase64(buffer) {
    const bytes = new Uint8Array(buffer);
    let binary = "";
    bytes.forEach((byte) => {
      binary += String.fromCharCode(byte);
    });
    return window.btoa(binary);
  }

  function normalizePhoneNumber(value) {
    return String(value || "").replace(/\D+/g, "");
  }

  function buildWaUrl(contact, message) {
    const digits = normalizePhoneNumber(contact);
    if (!digits) {
      return "";
    }
    return `https://wa.me/${digits}?text=${encodeURIComponent(message || "")}`;
  }

  function showError(root, message) {
    showAlert(root, message, "danger");
  }

  function showWarning(root, message) {
    showAlert(root, message, "warning");
  }

  function showAlert(root, message, tone) {
    const errorNode = root.querySelector("[data-planning-helper-error]");
    if (!errorNode) {
      return;
    }
    errorNode.textContent = message;
    errorNode.classList.remove("d-none", "alert-danger", "alert-warning", "alert-success");
    errorNode.classList.add(`alert-${tone}`);
    errorNode.classList.remove("d-none");
  }

  function clearError(root) {
    const errorNode = root.querySelector("[data-planning-helper-error]");
    if (!errorNode) {
      return;
    }
    errorNode.textContent = "";
    errorNode.classList.remove("alert-danger", "alert-warning", "alert-success");
    errorNode.classList.add("d-none");
  }

  function installPanel(root) {
    return root.querySelector("[data-planning-helper-install-panel]");
  }

  function installStatusNode(root) {
    return root.querySelector("[data-planning-helper-install-status]");
  }

  function hideInstallAssistant(root) {
    const panel = installPanel(root);
    if (!panel) {
      return;
    }
    panel.classList.add("d-none");
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

  function showInstallAssistant(root, retryAction, message) {
    const panel = installPanel(root);
    if (!panel) {
      showWarning(root, message || helperUnavailableMessage());
      return;
    }
    root._planningHelperRetryAction = retryAction;
    panel.classList.remove("d-none");
    showWarning(root, message || helperUnavailableMessage());
  }

  function isHelperUnavailableError(error) {
    const message = String((error && error.message) || "");
    return /helper local/i.test(message) || /Failed to fetch/i.test(message);
  }

  function helperUnavailableMessage() {
    return "Le helper local est indisponible. Vérifiez qu'il est démarré sur ce poste.";
  }

  function parseVersion(value) {
    return String(value || "")
      .split(".")
      .map((part) => {
        const numericPart = parseInt(part, 10);
        return Number.isFinite(numericPart) ? numericPart : 0;
      });
  }

  function compareVersions(left, right) {
    const leftParts = parseVersion(left);
    const rightParts = parseVersion(right);
    const partCount = Math.max(leftParts.length, rightParts.length, 3);
    for (let index = 0; index < partCount; index += 1) {
      const leftPart = leftParts[index] || 0;
      const rightPart = rightParts[index] || 0;
      if (leftPart < rightPart) {
        return -1;
      }
      if (leftPart > rightPart) {
        return 1;
      }
    }
    return 0;
  }

  function normalizeCapabilities(capabilities) {
    if (!Array.isArray(capabilities)) {
      return [];
    }
    return capabilities
      .map((capability) => String(capability || "").trim())
      .filter((capability) => capability);
  }

  function evaluateHelperStatus({ health, minimumVersion, latestVersion, requiredCapabilities }) {
    if (!health || health.ok !== true) {
      return {
        status: "missing",
        message: helperUnavailableMessage(),
      };
    }

    const helperVersion = String(health.helper_version || "").trim();
    if (!helperVersion) {
      return {
        status: "missing",
        message: helperUnavailableMessage(),
      };
    }

    if (compareVersions(helperVersion, minimumVersion) < 0) {
      return {
        status: "outdated_blocking",
        message: `Le helper local doit etre mis a jour avant de lancer cette action (minimum ${minimumVersion}).`,
      };
    }

    const availableCapabilities = new Set(normalizeCapabilities(health.capabilities));
    const missingCapabilities = normalizeCapabilities(requiredCapabilities).filter(
      (capability) => !availableCapabilities.has(capability)
    );
    if (missingCapabilities.length) {
      return {
        status: "unsupported_blocking",
        message: "Cette action requiert une version plus recente du helper local.",
      };
    }

    if (latestVersion && compareVersions(helperVersion, latestVersion) < 0) {
      return {
        status: "outdated_recommended",
        message: `Une version plus recente du helper local est disponible (${latestVersion}).`,
      };
    }

    return {
      status: "ready",
      message: "",
    };
  }

  function isBlockingHelperStatus(status) {
    return (
      status === "missing" ||
      status === "outdated_blocking" ||
      status === "unsupported_blocking"
    );
  }

  function requiresDirectRecipientAddress(family) {
    return (
      family === "email_correspondant" ||
      family === "email_expediteur" ||
      family === "email_destinataire"
    );
  }

  function rowOverrides(row, action) {
    if (!row) {
      return {};
    }
    const overrides = {};
    const subjectField = row.querySelector('input[name$="-subject"]');
    const bodyField = row.querySelector('textarea[name$="-body"]');
    const emailEditorSurface = row.querySelector("[data-planning-email-editor-surface='1']");
    if (action === "email" && subjectField) {
      overrides.subject = subjectField.value;
    }
    if (action === "email") {
      if (bodyField) {
        overrides.body_html = bodyField.value;
      } else if (emailEditorSurface) {
        overrides.body_html = emailEditorSurface.innerHTML;
      } else {
        overrides.body_html = "";
      }
    } else if (bodyField) {
      overrides.body = bodyField.value;
    }
    return overrides;
  }

  function mergeDraftPayload(payload, row) {
    return {
      ...payload,
      ...rowOverrides(row, payload.action),
    };
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

  async function fetchAttachment(attachment) {
    try {
      const response = await fetch(attachment.download_url, {
        credentials: "same-origin",
        headers: {
          Accept: "*/*",
        },
      });
      let errorPayload = {};
      if (!response.ok) {
        try {
          errorPayload = await response.json();
        } catch (error) {
          errorPayload = {};
        }
        throw new Error(errorPayload.error || `Telechargement impossible (${response.status})`);
      }
      return {
        attachment_type: attachment.attachment_type,
        filename: attachment.filename,
        mime_type: response.headers.get("Content-Type") || "application/octet-stream",
        content_base64: arrayBufferToBase64(await response.arrayBuffer()),
      };
    } catch (error) {
      if (attachment.optional) {
        return {
          skipped: true,
          filename: attachment.filename,
          error: error.message || "Piece jointe indisponible",
        };
      }
      throw error;
    }
  }

  async function hydrateEmailDraft(draft) {
    const resolvedAttachments = await Promise.all((draft.attachments || []).map(fetchAttachment));
    const attachments = resolvedAttachments.filter((attachment) => !attachment.skipped);
    const skippedAttachments = resolvedAttachments.filter((attachment) => attachment.skipped);
    return {
      ...draft,
      attachments,
      skippedAttachments,
    };
  }

  async function postToHelper(root, path, payload) {
    const helperOrigin = root.dataset.planningHelperOrigin;
    const helperUrl = `http://${helperOrigin}`;
    let response;
    try {
      response = await fetch(`${helperUrl}${path}`, {
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

  async function fetchHelperHealth(root) {
    return postToHelper(root, "/health", {});
  }

  async function fetchHelperCompatibility(root, requiredCapabilities) {
    try {
      const health = await fetchHelperHealth(root);
      return evaluateHelperStatus({
        health,
        minimumVersion: String(root.dataset.planningHelperMinimumVersion || "0.0.0"),
        latestVersion: String(
          root.dataset.planningHelperLatestVersion ||
            root.dataset.planningHelperMinimumVersion ||
            "0.0.0"
        ),
        requiredCapabilities,
      });
    } catch (error) {
      return {
        status: "missing",
        message: error.message || helperUnavailableMessage(),
      };
    }
  }

  async function ensureHelperCompatibility(root, requiredCapabilities) {
    const compatibility = await fetchHelperCompatibility(root, requiredCapabilities);
    if (isBlockingHelperStatus(compatibility.status)) {
      const error = new Error(compatibility.message);
      error.helperCompatibility = compatibility;
      throw error;
    }
    return compatibility;
  }

  async function openWhatsappDraft(root, button) {
    const payload = await fetchJson(button.dataset.draftActionUrl);
    const row = button.closest("[data-planning-draft-row]");
    const draft = mergeDraftPayload(payload, row);
    const waUrl = buildWaUrl(draft.recipient_contact, draft.body);
    if (!waUrl) {
      throw new Error("Numero WhatsApp indisponible pour ce brouillon.");
    }
    window.open(waUrl, "_blank", "noopener");
  }

  async function openEmailDraft(root, button) {
    const payload = await fetchJson(button.dataset.draftActionUrl);
    const compatibility = await ensureHelperCompatibility(
      root,
      payload.required_capabilities || []
    );
    const row = button.closest("[data-planning-draft-row]");
    const draft = await hydrateEmailDraft(mergeDraftPayload(payload, row));
    await postToHelper(root, "/v1/outlook/open", { drafts: [draft] });
    hideInstallAssistant(root);
    const warningMessages = [];
    if (compatibility.status === "outdated_recommended") {
      warningMessages.push(compatibility.message);
    }
    if (draft.skippedAttachments.length) {
      warningMessages.push(
        `Certaines pieces jointes sont indisponibles et ont ete ignorees: ${draft.skippedAttachments
          .map((attachment) => attachment.filename)
          .join(", ")}.`
      );
    }
    if (warningMessages.length) {
      showWarning(root, warningMessages.join(" "));
      return;
    }
    clearError(root);
  }

  async function openWhatsappDraftsDirectly(drafts) {
    for (const draft of drafts) {
      if (!draft.wa_url) {
        continue;
      }
      window.open(draft.wa_url, "_blank", "noopener");
      await new Promise((resolve) => window.setTimeout(resolve, 150));
    }
  }

  async function openFamilyDrafts(root, button) {
    const payload = await fetchJson(button.dataset.familyActionUrl);
    const article = button.closest("[data-family-key]");
    if (payload.action === "whatsapp") {
      const drafts = (payload.drafts || []).map((draft) => {
        const row = article.querySelector(
          `[data-planning-draft-row="1"][data-draft-id="${draft.draft_id}"]`
        );
        const mergedDraft = mergeDraftPayload(draft, row);
        return {
          ...mergedDraft,
          wa_url: buildWaUrl(mergedDraft.recipient_contact, mergedDraft.body),
        };
      });
      try {
        await postToHelper(root, "/v1/whatsapp/open", { drafts });
      } catch (error) {
        if (!isHelperUnavailableError(error)) {
          throw error;
        }
        await openWhatsappDraftsDirectly(drafts);
      }
      return;
    }
    const compatibility = await ensureHelperCompatibility(
      root,
      payload.required_capabilities || []
    );
    const drafts = await Promise.all(
      (payload.drafts || []).map(async (draft) => {
        const row = article.querySelector(
          `[data-planning-draft-row="1"][data-draft-id="${draft.draft_id}"]`
        );
        return hydrateEmailDraft(mergeDraftPayload(draft, row));
      })
    );
    const openableDrafts = drafts.filter(
      (draft) => !requiresDirectRecipientAddress(draft.family) || draft.recipient_contact
    );
    if (!openableDrafts.length) {
      showWarning(root, "Aucun mail disponible pour ce groupe.");
      return;
    }
    await postToHelper(root, "/v1/outlook/open", { drafts: openableDrafts });
    const skippedAttachments = openableDrafts.flatMap((draft) => draft.skippedAttachments || []);
    hideInstallAssistant(root);
    const warningMessages = [];
    if (compatibility.status === "outdated_recommended") {
      warningMessages.push(compatibility.message);
    }
    if (skippedAttachments.length) {
      warningMessages.push(
        `Certaines pieces jointes sont indisponibles et ont ete ignorees: ${skippedAttachments
          .map((attachment) => attachment.filename)
          .join(", ")}.`
      );
    }
    if (warningMessages.length) {
      showWarning(root, warningMessages.join(" "));
      return;
    }
    clearError(root);
  }

  async function handleClick(root, button) {
    hideInstallAssistant(root);
    clearError(root);
    button.disabled = true;
    try {
      if (button.hasAttribute("data-communication-open-family")) {
        await openFamilyDrafts(root, button);
      } else if (
        button.closest("[data-family-key]") &&
        button.closest("[data-family-key]").dataset.familyKey === "whatsapp_benevole"
      ) {
        await openWhatsappDraft(root, button);
      } else {
        await openEmailDraft(root, button);
      }
    } catch (error) {
      if (error.helperCompatibility && isBlockingHelperStatus(error.helperCompatibility.status)) {
        showInstallAssistant(root, function () {
          handleClick(root, button);
        }, error.message);
        return;
      }
      if (isHelperUnavailableError(error)) {
        showInstallAssistant(root, function () {
          handleClick(root, button);
        }, error.message);
      } else {
        showError(root, error.message || "Une erreur est survenue.");
      }
    } finally {
      button.disabled = false;
    }
  }

  async function copyInstallCommand(root) {
    const command = root.dataset.planningHelperInstallCommand || "";
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
    const action = root._planningHelperRetryAction;
    if (!action) {
      showInstallStatus(root, "Lancez l'installation, puis recliquez sur le bouton voulu.");
      return;
    }
    action();
  }

  document.addEventListener("DOMContentLoaded", function () {
    const root = document.querySelector('[data-planning-communication-helper="1"]');
    if (!root) {
      return;
    }
    root
      .querySelectorAll("[data-communication-open-draft], [data-communication-open-family]")
      .forEach((button) => {
        button.addEventListener("click", function () {
          handleClick(root, button);
        });
      });
    const installLink = root.querySelector("[data-planning-helper-install-link]");
    if (installLink) {
      installLink.addEventListener("click", function () {
        showInstallStatus(
          root,
          "Installeur telecharge. Lancez-le sur ce poste, puis cliquez sur Reessayer."
        );
      });
    }
    const copyButton = root.querySelector("[data-planning-helper-copy-command]");
    if (copyButton) {
      copyButton.addEventListener("click", function () {
        copyInstallCommand(root);
      });
    }
    const retryButton = root.querySelector("[data-planning-helper-retry]");
    if (retryButton) {
      retryButton.addEventListener("click", function () {
        retryPendingAction(root);
      });
    }
    const dismissButton = root.querySelector("[data-planning-helper-dismiss]");
    if (dismissButton) {
      dismissButton.addEventListener("click", function () {
        hideInstallAssistant(root);
      });
    }
  });
})();
