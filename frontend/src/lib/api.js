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

export const STATIC = import.meta.env.VITE_STATIC === "1";
export const REPO_URL = "https://github.com/mudramg685/quick-search-";

// ---- static mode (GitHub Pages): the real index snapshot is searched in the browser ----
let enginePromise = null;
function staticData() {
  enginePromise ??= Promise.all([
    fetch(`${import.meta.env.BASE_URL}index.json`).then((r) => {
      if (!r.ok) throw new ApiError("Could not load the search index snapshot.", r.status);
      return r.json();
    }),
    import("./staticEngine.js"),
  ]).then(([data, mod]) => ({ data, engine: mod.createEngine(data) }));
  return enginePromise;
}
const backendOnly = () =>
  Promise.reject(new ApiError("Crawling needs the Python backend. This hosted demo searches a snapshot of the index; run the project locally to crawl.", 501));

const staticApi = {
  search: (q, opts = {}) => staticData().then(({ engine }) => {
    const res = engine.search(q, opts);
    // Corpus pages were crawled from the local backend; the static site hosts copies of them.
    const corpusBase = new URL(`${import.meta.env.BASE_URL}corpus/`, window.location.href).href;
    res.results.forEach((r) => { r.url = r.url.replace(/^http:\/\/127\.0\.0\.1:8000\/corpus\//, corpusBase); });
    return res;
  }),
  suggestions: (q) => staticData().then(({ engine }) => ({ query: q, suggestions: engine.suggest(q) })),
  stats: () => staticData().then(({ data }) => ({
    ...data.stats,
    index: { documents: data.docs.length, terms: Object.keys(data.postings).length, vocabulary: Object.keys(data.vocab).length,
      loaded_at: Date.parse(data.generated_at) / 1000, last_reload_ms: null },
    crawl: { running: false, job_id: null, live: null },
  })),
  health: () => staticData().then(({ data }) => ({ status: "ok", documents: data.docs.length })),
  documents: () => staticData().then(({ data }) => data.documents),
  crawlStatus: () => staticData().then(({ data }) => ({
    running: false, job: data.stats.recent_jobs[0] ? { ...data.stats.recent_jobs[0], seeds: [] } : null,
    live: null, recent_errors: data.stats.recent_errors,
  })),
  startCrawl: backendOnly,
  cancelCrawl: backendOnly,
};

const serverApi = {
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

export const api = STATIC ? staticApi : serverApi;
