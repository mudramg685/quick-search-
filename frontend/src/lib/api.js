// Thin wrapper around fetch() for the QuirkSearch REST API.
// Errors are normalized into ApiError so every page can render the same error state.

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function request(path, { method = "GET", params, body, signal } = {}) {
  const url = new URL(path, window.location.origin);
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, v);
    });
  }
  let res;
  try {
    res = await fetch(url.pathname + url.search, {
      method,
      signal,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch (err) {
    if (err.name === "AbortError") throw err;
    throw new ApiError("Can't reach the QuirkSearch server. Is the backend running on port 8000?", 0);
  }
  let data = null;
  try {
    data = await res.json();
  } catch {
    /* non-JSON body */
  }
  if (!res.ok) {
    const detail = data?.errors?.map((e) => `${e.field}: ${e.message}`).join("; ") || data?.detail;
    if (res.status === 429) throw new ApiError("You're searching faster than our rate limit allows. Take a breath and retry.", 429);
    throw new ApiError(detail || `Request failed (${res.status})`, res.status);
  }
  return data;
}

export const api = {
  search: (q, { page = 1, pageSize = 10, domain } = {}, signal) =>
    request("/api/search", { params: { q, page, page_size: pageSize, domain }, signal }),
  suggestions: (q, signal) => request("/api/suggestions", { params: { q, limit: 7 }, signal }),
  stats: (signal) => request("/api/stats", { signal }),
  health: (signal) => request("/api/health", { signal }),
  documents: (page = 1, pageSize = 8) => request("/api/documents", { params: { page, page_size: pageSize } }),
  crawlStatus: (jobId) => request("/api/crawl/status", { params: { job_id: jobId } }),
  startCrawl: (body) => request("/api/crawl", { method: "POST", body }),
  cancelCrawl: () => request("/api/crawl/cancel", { method: "POST" }),
};
