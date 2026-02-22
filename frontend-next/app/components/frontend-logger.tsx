"use client";

import { usePathname } from "next/navigation";
import { useEffect } from "react";

type FrontendLogPayload = {
  event: string;
  level?: "info" | "warning" | "error";
  message?: string;
  path?: string;
  meta?: Record<string, string | number | boolean | null | undefined>;
};

const LOG_ENDPOINT = "/ui/frontend-log/";

function postEvent(payload: FrontendLogPayload) {
  const body = JSON.stringify(payload);
  if (typeof navigator !== "undefined" && typeof navigator.sendBeacon === "function") {
    const blob = new Blob([body], { type: "application/json" });
    navigator.sendBeacon(LOG_ENDPOINT, blob);
    return;
  }
  fetch(LOG_ENDPOINT, {
    method: "POST",
    credentials: "same-origin",
    headers: { "content-type": "application/json" },
    body,
    keepalive: true,
  }).catch(() => {
    // Best effort telemetry: never block the UI.
  });
}

function normalizeError(error: unknown): string {
  if (error instanceof Error) {
    return `${error.name}: ${error.message}`;
  }
  return String(error ?? "unknown-error");
}

export function FrontendLogger() {
  const pathname = usePathname();

  useEffect(() => {
    const navigationEntry = performance.getEntriesByType("navigation")[0];
    const timing =
      navigationEntry && "duration" in navigationEntry
        ? Math.round(navigationEntry.duration)
        : null;
    postEvent({
      event: "page.view",
      level: "info",
      path: pathname,
      meta: {
        load_ms: timing,
      },
    });
  }, [pathname]);

  useEffect(() => {
    const onWindowError = (event: ErrorEvent) => {
      postEvent({
        event: "window.error",
        level: "error",
        path: window.location.pathname,
        message: event.message || normalizeError(event.error),
        meta: {
          line: event.lineno,
          column: event.colno,
        },
      });
    };

    const onPromiseRejection = (event: PromiseRejectionEvent) => {
      postEvent({
        event: "window.unhandledrejection",
        level: "error",
        path: window.location.pathname,
        message: normalizeError(event.reason),
      });
    };

    const onTrackedClick = (event: MouseEvent) => {
      const target = event.target as HTMLElement | null;
      const element = target?.closest<HTMLElement>("[data-track]");
      if (!element) {
        return;
      }
      const eventName = element.dataset.track || "ui.action";
      postEvent({
        event: eventName,
        level: "info",
        path: window.location.pathname,
        meta: {
          label: element.getAttribute("aria-label") || element.textContent?.trim() || "",
        },
      });
    };

    window.addEventListener("error", onWindowError);
    window.addEventListener("unhandledrejection", onPromiseRejection);
    document.addEventListener("click", onTrackedClick);
    return () => {
      window.removeEventListener("error", onWindowError);
      window.removeEventListener("unhandledrejection", onPromiseRejection);
      document.removeEventListener("click", onTrackedClick);
    };
  }, []);

  return null;
}
