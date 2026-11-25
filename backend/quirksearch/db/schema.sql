-- QuirkSearch relational schema (SQLite dialect, portable to PostgreSQL with minor type edits)
--
-- Normalization (3NF):
--   * every non-key column depends on the key, the whole key and nothing but the key
--   * domain names live once in `domains`; seed URLs once per job in `crawl_job_seeds`
--   * postings form the M:N relationship between `terms` and `documents`
-- Deliberate, controlled denormalization:
--   * terms.doc_freq  (= COUNT of postings rows for the term) is cached for O(1) IDF
--     lookups and kept exact by the two triggers at the bottom.

CREATE TABLE IF NOT EXISTS schema_migrations (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- ---------------------------------------------------------------- crawling
CREATE TABLE IF NOT EXISTS crawl_jobs (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    status            TEXT    NOT NULL DEFAULT 'queued'
                      CHECK (status IN ('queued', 'running', 'completed', 'failed', 'cancelled')),
    max_depth         INTEGER NOT NULL CHECK (max_depth BETWEEN 0 AND 10),
    max_pages         INTEGER NOT NULL CHECK (max_pages BETWEEN 1 AND 5000),
    pages_discovered  INTEGER NOT NULL DEFAULT 0 CHECK (pages_discovered >= 0),
    pages_fetched     INTEGER NOT NULL DEFAULT 0 CHECK (pages_fetched >= 0),
    pages_stored      INTEGER NOT NULL DEFAULT 0 CHECK (pages_stored >= 0),
    pages_failed      INTEGER NOT NULL DEFAULT 0 CHECK (pages_failed >= 0),
    error_message     TEXT,
    created_at        TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    started_at        TEXT,
    finished_at       TEXT,
    CHECK (finished_at IS NULL OR started_at IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS idx_crawl_jobs_status ON crawl_jobs(status);

CREATE TABLE IF NOT EXISTS crawl_job_seeds (
    job_id  INTEGER NOT NULL REFERENCES crawl_jobs(id) ON DELETE CASCADE,
    url     TEXT    NOT NULL,
    PRIMARY KEY (job_id, url)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS crawl_errors (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id       INTEGER NOT NULL REFERENCES crawl_jobs(id) ON DELETE CASCADE,
    url          TEXT    NOT NULL,
    depth        INTEGER NOT NULL DEFAULT 0 CHECK (depth >= 0),
    error_type   TEXT    NOT NULL CHECK (error_type IN
                 ('dns', 'connection', 'timeout', 'http_error', 'not_html', 'too_large',
                  'redirect', 'protocol', 'robots', 'duplicate', 'internal', 'unknown')),
    status_code  INTEGER CHECK (status_code IS NULL OR status_code BETWEEN 100 AND 599),
    message      TEXT    NOT NULL DEFAULT '',
    occurred_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_crawl_errors_job  ON crawl_errors(job_id);
CREATE INDEX IF NOT EXISTS idx_crawl_errors_type ON crawl_errors(error_type);

-- ---------------------------------------------------------------- documents
CREATE TABLE IF NOT EXISTS domains (
    id    INTEGER PRIMARY KEY,
    name  TEXT NOT NULL UNIQUE CHECK (length(name) > 0)
);

CREATE TABLE IF NOT EXISTS documents (
    id            INTEGER PRIMARY KEY,
    url           TEXT    NOT NULL UNIQUE,
    url_hash      TEXT    NOT NULL UNIQUE CHECK (length(url_hash) = 40),   -- SHA-1 hex
    domain_id     INTEGER NOT NULL REFERENCES domains(id),
    crawl_job_id  INTEGER REFERENCES crawl_jobs(id) ON DELETE SET NULL,
    title         TEXT    NOT NULL,
    description   TEXT    NOT NULL DEFAULT '',
    headings      TEXT    NOT NULL DEFAULT '',     -- newline separated, for display/re-analysis
    content       TEXT    NOT NULL,                -- cleaned text, used for snippets
    content_hash  TEXT    NOT NULL CHECK (length(content_hash) = 64),  -- SHA-256 hex
    language      TEXT,
    status_code   INTEGER NOT NULL CHECK (status_code BETWEEN 100 AND 599),
    depth         INTEGER NOT NULL CHECK (depth >= 0),
    doc_length    INTEGER NOT NULL CHECK (doc_length > 0),  -- |d| in BM25
    fetch_ms      REAL,
    fetched_at    TEXT    NOT NULL,
    indexed_at    TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_documents_domain       ON documents(domain_id);
CREATE INDEX IF NOT EXISTS idx_documents_content_hash ON documents(content_hash);
CREATE INDEX IF NOT EXISTS idx_documents_job          ON documents(crawl_job_id);
CREATE INDEX IF NOT EXISTS idx_documents_indexed_at   ON documents(indexed_at);

-- Outgoing hyperlinks: the edges of the crawled web graph.
CREATE TABLE IF NOT EXISTS links (
    source_doc_id  INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    target_url     TEXT    NOT NULL,
    PRIMARY KEY (source_doc_id, target_url)
) WITHOUT ROWID;

-- ---------------------------------------------------------------- inverted index
CREATE TABLE IF NOT EXISTS terms (
    id        INTEGER PRIMARY KEY,
    term      TEXT    NOT NULL UNIQUE,
    doc_freq  INTEGER NOT NULL DEFAULT 0 CHECK (doc_freq >= 0)
);

-- One row per (term, document): the postings list of a term is a contiguous range of the
-- clustered primary key (WITHOUT ROWID ⇒ the table *is* the B-tree on (term_id, doc_id)).
CREATE TABLE IF NOT EXISTS postings (
    term_id    INTEGER NOT NULL REFERENCES terms(id)     ON DELETE CASCADE,
    doc_id     INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    term_freq  INTEGER NOT NULL CHECK (term_freq > 0),
    PRIMARY KEY (term_id, doc_id)
) WITHOUT ROWID;
-- Secondary index for the reverse access path: "all postings of document d" (re-index/delete).
CREATE INDEX IF NOT EXISTS idx_postings_doc ON postings(doc_id);

-- Surface words (unstemmed) for autocomplete; each maps to the stemmed index term.
CREATE TABLE IF NOT EXISTS vocabulary (
    word       TEXT    PRIMARY KEY,
    term_id    INTEGER NOT NULL REFERENCES terms(id) ON DELETE CASCADE,
    frequency  INTEGER NOT NULL CHECK (frequency > 0)
) WITHOUT ROWID;

-- ---------------------------------------------------------------- analytics
CREATE TABLE IF NOT EXISTS search_logs (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    query             TEXT    NOT NULL CHECK (length(query) BETWEEN 1 AND 256),
    normalized_query  TEXT    NOT NULL,
    result_count      INTEGER NOT NULL CHECK (result_count >= 0),
    latency_ms        REAL    NOT NULL CHECK (latency_ms >= 0),
    page              INTEGER NOT NULL DEFAULT 1 CHECK (page >= 1),
    created_at        TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_search_logs_created ON search_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_search_logs_norm    ON search_logs(normalized_query);

-- ---------------------------------------------------------------- integrity triggers
-- Keep terms.doc_freq == number of postings for the term, whatever path modifies postings
-- (explicit DELETE, ON DELETE CASCADE from documents, or INSERT).
CREATE TRIGGER IF NOT EXISTS trg_postings_insert AFTER INSERT ON postings
BEGIN
    UPDATE terms SET doc_freq = doc_freq + 1 WHERE id = NEW.term_id;
END;

CREATE TRIGGER IF NOT EXISTS trg_postings_delete AFTER DELETE ON postings
BEGIN
    UPDATE terms SET doc_freq = doc_freq - 1 WHERE id = OLD.term_id;
END;
