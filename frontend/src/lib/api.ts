import type {
  CompanionCreate,
  CompanionRead,
  CompanionReply,
  CompanionUpdate,
  ContinueRequest,
  HistoryMessage,
  TestChatRequest,
} from "./types";

const BASE_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/+$/, "");
const TENANT_ID = process.env.NEXT_PUBLIC_TENANT_ID || "astrotamil";
const DEV_USER_ID = process.env.NEXT_PUBLIC_DEV_USER_ID || "owner-1";

const COMPANIONS_PREFIX = "/api/v1/companions";

/** External user id used by the dashboard test chat ("Forget me" targets this id). */
export const testExternalUserId = `owner-test:${DEV_USER_ID}`;

export class ApiError extends Error {
  readonly status: number;
  readonly error: string;

  constructor(status: number, error: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.error = error;
    Object.setPrototypeOf(this, ApiError.prototype);
  }
}

type Method = "GET" | "POST" | "PATCH" | "DELETE";

interface RequestOptions {
  method: Method;
  body?: unknown;
  /** Root routes (such as /health) sit outside the companions prefix and skip tenant headers. */
  root?: boolean;
}

function describeValidationDetail(detail: unknown): string | null {
  if (typeof detail === "string") return detail;
  if (!Array.isArray(detail) || detail.length === 0) return null;
  const parts = detail.map((item: unknown) => {
    const d = (item ?? {}) as { loc?: unknown; msg?: unknown };
    const where = Array.isArray(d.loc) ? d.loc.slice(1).join(".") : "";
    const msg = typeof d.msg === "string" ? d.msg : "is invalid";
    return where ? `${where}: ${msg}` : msg;
  });
  return parts.join("; ");
}

async function request<T>(path: string, { method, body, root = false }: RequestOptions): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (!root) {
    headers["X-Tenant-Id"] = TENANT_ID;
    headers["X-User-Id"] = DEV_USER_ID;
  }

  let payload: string | undefined;
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  const url = `${BASE_URL}${root ? "" : COMPANIONS_PREFIX}${path}`;

  let res: Response;
  try {
    res = await fetch(url, { method, headers, body: payload, cache: "no-store" });
  } catch {
    throw new ApiError(0, "network_error", `Cannot reach the backend at ${BASE_URL}. Is it running?`);
  }

  if (res.status === 204) {
    return undefined as T;
  }

  const text = await res.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = null;
    }
  }

  if (!res.ok) {
    const obj = (data && typeof data === "object" ? data : {}) as Record<string, unknown>;
    if (typeof obj.error === "string" && typeof obj.message === "string") {
      throw new ApiError(res.status, obj.error, obj.message);
    }
    // FastAPI request validation errors come back as {detail: [...]}.
    const detail = describeValidationDetail(obj.detail);
    if (detail) {
      throw new ApiError(res.status, "validation_error", detail);
    }
    throw new ApiError(res.status, `http_${res.status}`, `Request failed with status ${res.status}.`);
  }

  return data as T;
}

const enc = (value: string) => encodeURIComponent(value);

export const api = {
  health: () => request<{ status: string }>("/health", { method: "GET", root: true }),

  listCompanions: () => request<CompanionRead[]>("", { method: "GET" }),

  createCompanion: (body: CompanionCreate) => request<CompanionRead>("", { method: "POST", body }),

  getCompanion: (id: string) => request<CompanionRead>(`/${enc(id)}`, { method: "GET" }),

  updateCompanion: (id: string, body: CompanionUpdate) =>
    request<CompanionRead>(`/${enc(id)}`, { method: "PATCH", body }),

  deleteCompanion: (id: string) => request<void>(`/${enc(id)}`, { method: "DELETE" }),

  testChat: (id: string, body: TestChatRequest) =>
    request<CompanionReply>(`/${enc(id)}/test-chat`, { method: "POST", body }),

  continueTestChat: (body: ContinueRequest) =>
    request<CompanionReply>("/test-chat/continue", { method: "POST", body }),

  getTestChatHistory: (id: string) =>
    request<HistoryMessage[]>(`/${enc(id)}/test-chat/history`, { method: "GET" }),

  forgetEndUser: (externalUserId: string) =>
    request<void>(`/end-users/${enc(externalUserId)}/forget`, { method: "POST" }),
};

/** Turns any thrown value into the text shown in the UI. */
export function errorText(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 503 || err.error === "companion_busy") {
      return "Busy, try again";
    }
    return err.message;
  }
  if (err instanceof Error) {
    return err.message;
  }
  return "Something went wrong.";
}
