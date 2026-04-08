/** Klient API -- komunikacja z backendem PIT-38. */

import type { CalculateResponse, ErrorResponse, HealthResponse } from "./api-types";

const API_BASE = "/api";

class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const body = await response.json();
      const d = body?.detail;
      if (typeof d === "string") {
        detail = d;
      } else if (Array.isArray(d)) {
        // FastAPI validation errors: [{loc, msg, type}, ...]
        detail = d.map((e: { msg?: string; loc?: string[] }) =>
          e.msg ? `${(e.loc ?? []).join(".")}: ${e.msg}` : JSON.stringify(e)
        ).join("; ");
      } else if (d) {
        detail = JSON.stringify(d);
      }
    } catch {
      // ignoruj błędy parsowania
    }
    throw new ApiError(response.status, detail);
  }
  return response.json() as Promise<T>;
}

/** Health check. */
export async function fetchHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE}/health`);
  return handleResponse<HealthResponse>(response);
}

/** Oblicz PIT-38 z plików CSV. */
export async function calculatePit38(
  files: File[],
  taxYear: number,
  priorLosses: string = "0"
): Promise<CalculateResponse> {
  const formData = new FormData();
  for (const f of files) {
    formData.append("files", f);
  }
  formData.append("tax_year", String(taxYear));
  formData.append("prior_losses", priorLosses);

  const response = await fetch(`${API_BASE}/calculate`, {
    method: "POST",
    body: formData,
  });
  return handleResponse<CalculateResponse>(response);
}

export { ApiError };
