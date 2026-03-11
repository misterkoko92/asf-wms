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
    const errorNode = root.querySelector("[data-planning-helper-error]");
    if (!errorNode) {
      return;
    }
    errorNode.textContent = message;
    errorNode.classList.remove("d-none");
  }

  function clearError(root) {
    const errorNode = root.querySelector("[data-planning-helper-error]");
    if (!errorNode) {
      return;
    }
    errorNode.textContent = "";
    errorNode.classList.add("d-none");
  }

  function rowOverrides(row, action) {
    if (!row) {
      return {};
    }
    const overrides = {};
    const subjectField = row.querySelector('input[name$="-subject"]');
    const bodyField = row.querySelector('textarea[name$="-body"]');
    if (action === "email" && subjectField) {
      overrides.subject = subjectField.value;
    }
    if (bodyField) {
      if (action === "email") {
        overrides.body_html = bodyField.value;
      } else {
        overrides.body = bodyField.value;
      }
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
  }

  async function hydrateEmailDraft(draft) {
    const attachments = await Promise.all((draft.attachments || []).map(fetchAttachment));
    return {
      ...draft,
      attachments,
    };
  }

  async function postToHelper(root, path, payload) {
    const helperOrigin = root.dataset.planningHelperOrigin;
    const helperUrl = `http://${helperOrigin}`;
    const response = await fetch(`${helperUrl}${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-ASF-Planning-Helper": "1",
      },
      body: JSON.stringify(payload),
    });
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
    const row = button.closest("[data-planning-draft-row]");
    const draft = await hydrateEmailDraft(mergeDraftPayload(payload, row));
    await postToHelper(root, "/v1/outlook/open", { drafts: [draft] });
  }

  async function openFamilyDrafts(root, button) {
    const payload = await fetchJson(button.dataset.familyActionUrl);
    const article = button.closest("[data-family-key]");
    const drafts = await Promise.all(
      (payload.drafts || []).map(async (draft) => {
        const row = article.querySelector(
          `[data-planning-draft-row="1"][data-draft-id="${draft.draft_id}"]`
        );
        const mergedDraft = mergeDraftPayload(draft, row);
        if (mergedDraft.action === "email") {
          return hydrateEmailDraft(mergedDraft);
        }
        return {
          ...mergedDraft,
          wa_url: buildWaUrl(mergedDraft.recipient_contact, mergedDraft.body),
        };
      })
    );
    if (payload.action === "whatsapp") {
      await postToHelper(root, "/v1/whatsapp/open", { drafts });
      return;
    }
    await postToHelper(root, "/v1/outlook/open", { drafts });
  }

  async function handleClick(root, button) {
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
      showError(root, error.message || "Une erreur est survenue.");
    } finally {
      button.disabled = false;
    }
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
  });
})();
