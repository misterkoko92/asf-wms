type ApiErrorEnvelope = {
  code?: string;
  message?: string;
  field_errors?: Record<string, unknown>;
  non_field_errors?: unknown[];
};

export class ApiClientError extends Error {
  status: number;

  code: string;

  fieldErrors: Record<string, unknown>;

  nonFieldErrors: unknown[];

  constructor(
    message: string,
    status: number,
    code = "api_error",
    fieldErrors: Record<string, unknown> = {},
    nonFieldErrors: unknown[] = [],
  ) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.code = code;
    this.fieldErrors = fieldErrors;
    this.nonFieldErrors = nonFieldErrors;
  }
}

function getCookieValue(name: string): string {
  if (typeof document === "undefined") {
    return "";
  }
  const cookiePrefix = `${name}=`;
  const cookies = document.cookie.split(";");
  for (const rawCookie of cookies) {
    const cookie = rawCookie.trim();
    if (cookie.startsWith(cookiePrefix)) {
      return decodeURIComponent(cookie.slice(cookiePrefix.length));
    }
  }
  return "";
}

function csrfHeadersForMethod(
  method: "GET" | "POST" | "PATCH" | "DELETE",
): Record<string, string> {
  if (method === "GET") {
    return {};
  }
  const csrfToken = getCookieValue("csrftoken");
  return csrfToken ? { "x-csrftoken": csrfToken } : {};
}

async function apiRequestJson<T>(
  path: string,
  method: "GET" | "POST" | "PATCH" | "DELETE",
  body?: unknown,
): Promise<T> {
  const headers: Record<string, string> = {
    accept: "application/json",
    ...csrfHeadersForMethod(method),
  };
  if (body) {
    headers["content-type"] = "application/json";
  }
  const response = await fetch(path, {
    method,
    credentials: "same-origin",
    headers,
    body: body ? JSON.stringify(body) : undefined,
    cache: "no-store",
  });
  const payload = response.headers.get("content-type")?.includes("application/json")
    ? ((await response.json()) as unknown)
    : null;
  if (!response.ok) {
    const errorPayload = (payload ?? {}) as ApiErrorEnvelope;
    throw new ApiClientError(
      errorPayload.message ?? `API request failed (${response.status}) for ${path}`,
      response.status,
      errorPayload.code ?? "api_error",
      errorPayload.field_errors ?? {},
      errorPayload.non_field_errors ?? [],
    );
  }
  return payload as T;
}

export function apiGetJson<T>(path: string): Promise<T> {
  return apiRequestJson<T>(path, "GET");
}

export function apiPostJson<T>(path: string, body: unknown): Promise<T> {
  return apiRequestJson<T>(path, "POST", body);
}

export function apiPatchJson<T>(path: string, body: unknown): Promise<T> {
  return apiRequestJson<T>(path, "PATCH", body);
}

export function apiDeleteJson<T>(path: string): Promise<T> {
  return apiRequestJson<T>(path, "DELETE");
}

export async function apiPostFormData<T>(path: string, body: FormData): Promise<T> {
  const headers: Record<string, string> = {
    accept: "application/json",
    ...csrfHeadersForMethod("POST"),
  };
  const response = await fetch(path, {
    method: "POST",
    credentials: "same-origin",
    headers,
    body,
    cache: "no-store",
  });
  const payload = response.headers.get("content-type")?.includes("application/json")
    ? ((await response.json()) as unknown)
    : null;
  if (!response.ok) {
    const errorPayload = (payload ?? {}) as ApiErrorEnvelope;
    throw new ApiClientError(
      errorPayload.message ?? `API request failed (${response.status}) for ${path}`,
      response.status,
      errorPayload.code ?? "api_error",
      errorPayload.field_errors ?? {},
      errorPayload.non_field_errors ?? [],
    );
  }
  return payload as T;
}
