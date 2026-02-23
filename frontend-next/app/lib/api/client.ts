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

async function apiRequestJson<T>(
  path: string,
  method: "GET" | "POST" | "PATCH",
  body?: unknown,
): Promise<T> {
  const response = await fetch(path, {
    method,
    credentials: "same-origin",
    headers: {
      accept: "application/json",
      ...(body ? { "content-type": "application/json" } : {}),
    },
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
