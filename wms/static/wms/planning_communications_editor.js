(function () {
  const ALLOWED_TAGS = new Set([
    "a",
    "b",
    "br",
    "div",
    "em",
    "i",
    "li",
    "mark",
    "ol",
    "p",
    "span",
    "strong",
    "table",
    "tbody",
    "td",
    "th",
    "thead",
    "tr",
    "u",
    "ul",
  ]);
  const BLOCKED_TAGS = new Set(["embed", "iframe", "link", "meta", "object", "script", "style"]);
  const ALLOWED_STYLE_PROPERTIES = new Set([
    "background",
    "background-color",
    "border",
    "border-bottom",
    "border-collapse",
    "border-left",
    "border-right",
    "border-top",
    "color",
    "font-style",
    "font-weight",
    "padding",
    "padding-bottom",
    "padding-left",
    "padding-right",
    "padding-top",
    "table-layout",
    "text-align",
    "text-decoration",
    "white-space",
    "width",
  ]);

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function sanitizeStyle(value) {
    return String(value || "")
      .split(";")
      .map((entry) => entry.trim())
      .filter(Boolean)
      .map((entry) => {
        const separatorIndex = entry.indexOf(":");
        if (separatorIndex === -1) {
          return "";
        }
        const property = entry.slice(0, separatorIndex).trim().toLowerCase();
        const propertyValue = entry.slice(separatorIndex + 1).trim();
        if (!ALLOWED_STYLE_PROPERTIES.has(property)) {
          return "";
        }
        if (/expression|javascript:|url\(/i.test(propertyValue)) {
          return "";
        }
        return `${property}: ${propertyValue}`;
      })
      .filter(Boolean)
      .join("; ");
  }

  function sanitizeHref(value) {
    const href = String(value || "").trim();
    if (!href) {
      return "";
    }
    if (/^(https?:|mailto:|#)/i.test(href)) {
      return href;
    }
    return "";
  }

  function sanitizeElementAttributes(element, tagName) {
    Array.from(element.attributes).forEach((attribute) => {
      const name = attribute.name.toLowerCase();
      const value = attribute.value;
      if (name.startsWith("on")) {
        element.removeAttribute(attribute.name);
        return;
      }
      if (name === "style") {
        const sanitizedStyle = sanitizeStyle(value);
        if (sanitizedStyle) {
          element.setAttribute("style", sanitizedStyle);
        } else {
          element.removeAttribute("style");
        }
        return;
      }
      if (tagName === "a" && name === "href") {
        const sanitizedHref = sanitizeHref(value);
        if (sanitizedHref) {
          element.setAttribute("href", sanitizedHref);
          element.setAttribute("rel", "noopener noreferrer");
        } else {
          element.removeAttribute("href");
          element.removeAttribute("rel");
        }
        return;
      }
      if (tagName === "a" && name === "target") {
        element.setAttribute("target", "_blank");
        element.setAttribute("rel", "noopener noreferrer");
        return;
      }
      if (
        (tagName === "table" && (name === "cellpadding" || name === "cellspacing")) ||
        ((tagName === "td" || tagName === "th") && (name === "colspan" || name === "rowspan"))
      ) {
        return;
      }
      element.removeAttribute(attribute.name);
    });
  }

  function sanitizeNodeTree(root) {
    Array.from(root.childNodes).forEach((node) => {
      if (node.nodeType !== Node.ELEMENT_NODE) {
        return;
      }
      const tagName = node.tagName.toLowerCase();
      if (BLOCKED_TAGS.has(tagName)) {
        node.remove();
        return;
      }
      sanitizeNodeTree(node);
      if (!ALLOWED_TAGS.has(tagName)) {
        while (node.firstChild) {
          node.parentNode.insertBefore(node.firstChild, node);
        }
        node.remove();
        return;
      }
      sanitizeElementAttributes(node, tagName);
    });
  }

  function sanitizeHtml(value) {
    const template = document.createElement("template");
    template.innerHTML = String(value || "");
    sanitizeNodeTree(template.content);
    return template.innerHTML;
  }

  function normalizeEditorHtml(surface) {
    const html = String(surface.innerHTML || "").trim();
    const text = String(surface.textContent || "").replace(/\u00a0/g, " ").trim();
    if (!text && !surface.querySelector("table, ul, ol, li, p, div, mark, strong, em, u")) {
      return "";
    }
    if (html === "<br>") {
      return "";
    }
    return html;
  }

  function syncEditorToSource(wrapper) {
    const source = wrapper.querySelector("[data-planning-email-body-source='1']");
    const surface = wrapper.querySelector("[data-planning-email-editor-surface='1']");
    if (!source || !surface) {
      return;
    }
    source.value = sanitizeHtml(normalizeEditorHtml(surface));
  }

  function insertHtmlAtCursor(html) {
    if (typeof document.execCommand === "function") {
      document.execCommand("insertHTML", false, html);
      return;
    }
    const selection = window.getSelection();
    if (!selection || !selection.rangeCount) {
      return;
    }
    const range = selection.getRangeAt(0);
    range.deleteContents();
    const fragment = range.createContextualFragment(html);
    range.insertNode(fragment);
    range.collapse(false);
    selection.removeAllRanges();
    selection.addRange(range);
  }

  function applyCommand(surface, command) {
    surface.focus();
    if (command === "highlight") {
      if (typeof document.execCommand === "function") {
        document.execCommand("styleWithCSS", false, true);
        if (!document.execCommand("hiliteColor", false, "#fff59d")) {
          document.execCommand("backColor", false, "#fff59d");
        }
      }
      return;
    }
    if (typeof document.execCommand === "function") {
      document.execCommand(command, false, null);
    }
  }

  function handlePlainTextPaste(event, wrapper) {
    event.preventDefault();
    const pastedText = (event.clipboardData || window.clipboardData).getData("text");
    const html = escapeHtml(pastedText).replace(/\r?\n/g, "<br>");
    insertHtmlAtCursor(html);
    syncEditorToSource(wrapper);
  }

  function initEditor(wrapper) {
    if (wrapper.dataset.editorReady === "1") {
      return;
    }
    const source = wrapper.querySelector("[data-planning-email-body-source='1']");
    const surface = wrapper.querySelector("[data-planning-email-editor-surface='1']");
    const toolbar = wrapper.querySelector("[data-planning-email-editor-toolbar='1']");
    const hint = wrapper.querySelector("[data-planning-email-editor-hint='1']");
    if (!source || !surface || !toolbar) {
      return;
    }

    const sanitizedSourceHtml = sanitizeHtml(source.value || "");
    surface.innerHTML = sanitizedSourceHtml;
    source.value = sanitizedSourceHtml;
    toolbar.classList.remove("d-none");
    surface.classList.remove("d-none");
    if (hint) {
      hint.classList.remove("d-none");
    }
    source.classList.add("d-none");

    surface.addEventListener("input", function () {
      syncEditorToSource(wrapper);
    });
    surface.addEventListener("blur", function () {
      syncEditorToSource(wrapper);
    });
    surface.addEventListener("paste", function (event) {
      handlePlainTextPaste(event, wrapper);
    });

    toolbar.querySelectorAll("[data-planning-email-editor-command]").forEach((button) => {
      button.addEventListener("mousedown", function (event) {
        event.preventDefault();
      });
      button.addEventListener("click", function () {
        applyCommand(surface, button.dataset.planningEmailEditorCommand);
        syncEditorToSource(wrapper);
      });
    });

    wrapper.dataset.editorReady = "1";
    syncEditorToSource(wrapper);
  }

  function syncEditorsWithin(root) {
    root.querySelectorAll("[data-planning-email-editor='1']").forEach((wrapper) => {
      syncEditorToSource(wrapper);
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-planning-email-editor='1']").forEach((wrapper) => {
      initEditor(wrapper);
    });
    document.querySelectorAll("[data-planning-communication-helper='1'] form").forEach((form) => {
      form.addEventListener("submit", function () {
        syncEditorsWithin(form);
      });
    });
  });
})();
