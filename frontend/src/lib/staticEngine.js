// In-browser search engine for the static (GitHub Pages) build.
//
// Loads a JSON snapshot of the real inverted index exported from the backend database
// (backend/scripts/export_static.py) and runs the same algorithms as the Python engine:
// analyzer (NFKC → lowercase → tokenize → stop words → Porter), BM25 term-at-a-time scoring,
// bounded min-heap Top-K, best-window snippets, Levenshtein "did you mean", prefix autocomplete.

// ------------------------------------------------------------------ Porter stemmer (port of porter.py)
function makeStemmer(word) {
  let b = word;
  let k = word.length - 1;
  let j = 0;
  const cons = (i) => {
    const ch = b[i];
    if ("aeiou".includes(ch)) return false;
    if (ch === "y") return i === 0 || !cons(i - 1);
    return true;
  };
  const m = () => {
    let n = 0, i = 0;
    for (;;) { if (i > j) return n; if (!cons(i)) break; i++; }
    i++;
    for (;;) {
      for (;;) { if (i > j) return n; if (cons(i)) break; i++; }
      i++; n++;
      for (;;) { if (i > j) return n; if (!cons(i)) break; i++; }
      i++;
    }
  };
  const vowelInStem = () => { for (let i = 0; i <= j; i++) if (!cons(i)) return true; return false; };
  const doubleC = (x) => x >= 1 && b[x] === b[x - 1] && cons(x);
  const cvc = (i) => !(i < 2 || !cons(i) || cons(i - 1) || !cons(i - 2)) && !"wxy".includes(b[i]);
  const ends = (s) => {
    if (s.length > k + 1 || b.slice(k - s.length + 1, k + 1) !== s) return false;
    j = k - s.length;
    return true;
  };
  const setTo = (s) => { b = b.slice(0, j + 1) + s; k = j + s.length; };
  const r = (s) => { if (m() > 0) setTo(s); };
  const STEP2 = {
    a: [["ational", "ate"], ["tional", "tion"]], c: [["enci", "ence"], ["anci", "ance"]], e: [["izer", "ize"]],
    l: [["bli", "ble"], ["alli", "al"], ["entli", "ent"], ["eli", "e"], ["ousli", "ous"]],
    o: [["ization", "ize"], ["ation", "ate"], ["ator", "ate"]],
    s: [["alism", "al"], ["iveness", "ive"], ["fulness", "ful"], ["ousness", "ous"]],
    t: [["aliti", "al"], ["iviti", "ive"], ["biliti", "ble"]], g: [["logi", "log"]],
  };
  const STEP3 = { e: [["icate", "ic"], ["ative", ""], ["alize", "al"]], i: [["iciti", "ic"]], l: [["ical", "ic"], ["ful", ""]], s: [["ness", ""]] };
  const STEP4 = { a: ["al"], c: ["ance", "ence"], e: ["er"], i: ["ic"], l: ["able", "ible"], n: ["ant", "ement", "ment", "ent"],
    o: ["ion", "ou"], s: ["ism"], t: ["ate", "iti"], u: ["ous"], v: ["ive"], z: ["ize"] };
  const applyTable = (table, key) => { for (const [suf, rep] of table[key] || []) if (ends(suf)) { r(rep); return; } };

  return () => {
    if (k <= 1) return b;
    // step 1ab
    if (b[k] === "s") {
      if (ends("sses")) k -= 2;
      else if (ends("ies")) setTo("i");
      else if (b[k - 1] !== "s") k -= 1;
    }
    b = b.slice(0, k + 1);
    if (ends("eed")) { if (m() > 0) k -= 1; }
    else if ((ends("ed") || ends("ing")) && vowelInStem()) {
      k = j; b = b.slice(0, k + 1);
      if (ends("at")) setTo("ate");
      else if (ends("bl")) setTo("ble");
      else if (ends("iz")) setTo("ize");
      else if (doubleC(k)) { if (!"lsz".includes(b[k])) k -= 1; }
      else if (m() === 1 && cvc(k)) { j = k; setTo("e"); }
    }
    b = b.slice(0, k + 1);
    if (k < 0) return b;
    // step 1c
    if (ends("y") && vowelInStem()) b = b.slice(0, k) + "i";
    // step 2, 3
    if (k >= 1) applyTable(STEP2, b[k - 1]);
    applyTable(STEP3, b[k]);
    // step 4
    if (k >= 1) {
      for (const suf of STEP4[b[k - 1]] || []) {
        if (ends(suf)) {
          if (suf === "ion" && !(j >= 0 && "st".includes(b[j]))) continue;
          if (m() > 1) { k = j; b = b.slice(0, k + 1); }
          break;
        }
      }
    }
    // step 5
    j = k;
    if (b[k] === "e") { const a = m(); if (a > 1 || (a === 1 && !cvc(k - 1))) k -= 1; }
    if (b[k] === "l" && doubleC(k) && m() > 1) k -= 1;
    b = b.slice(0, k + 1);
    return b;
  };
}

const stemCache = new Map();
export function stem(word) {
  if (!/^[a-z]+$/.test(word)) return /^\p{L}+$/u.test(word) ? makeStemmer(word)() : word;
  let s = stemCache.get(word);
  if (s === undefined) { s = makeStemmer(word)(); stemCache.set(word, s); }
  return s;
}

// ------------------------------------------------------------------ analyzer
let STOP = new Set();
const normalize = (t) => (t || "").normalize("NFKC").toLowerCase().replace(/['’ʼ]/g, "");
const tokenize = (t) => normalize(t).match(/[\p{L}\p{N}]+/gu) || [];
const indexable = (t) => !STOP.has(t) && ((t.length >= 2 && t.length <= 40) || (/^\d+$/.test(t) && t.length <= 40));
const termOf = (word) => { const t = normalize(word).replace(/[^\p{L}\p{N}]/gu, ""); return t && indexable(t) ? stem(t) : null; };

// A chunk is an (optionally +/-) "quoted phrase" or a run of non-space characters.
const CHUNK = /([+-]?)"([^"]*)"?|(\S+)/g;

function parseQuery(raw) {
  const original = raw;
  let domain = null;
  const m = raw.match(/\bsite:(\S+)/i);
  if (m) { domain = m[1].toLowerCase().replace(/^\/+|\/+$/g, ""); raw = raw.replace(/\bsite:\S+/gi, " "); }
  const terms = [], required = new Set(), excluded = new Set(), words = [], phrases = [];
  for (const c of raw.matchAll(CHUNK)) {
    let prefix, body, quoted;
    if (c[3] !== undefined) {
      const chunk = c[3];
      prefix = "+-".includes(chunk[0]) && chunk.length > 1 ? chunk[0] : "";
      body = prefix ? chunk.slice(1) : chunk;
      quoted = false;
    } else {
      prefix = c[1]; body = c[2]; quoted = true;
    }
    const phrase = [];
    for (const tok of tokenize(body)) {
      if (!indexable(tok)) continue;
      const t = stem(tok);
      if (prefix === "-") { excluded.add(t); continue; }
      words.push(tok);
      phrase.push(t);
      if (prefix === "+" || quoted) required.add(t);
      if (!terms.includes(t)) terms.push(t);
    }
    if (quoted && phrase.length > 1) phrases.push(phrase);
  }
  return { raw: original, terms, required, excluded, domain, words, phrases };
}

// Ranking = BM25 × coverage, so pages containing every query word beat one-word repeats.
const coverage = (matched, n) => (n ? (1 + matched) / (1 + n) : 1);
const termSequence = (text) => tokenize(text).filter(indexable).map(stem);
function containsPhrase(seq, phrase) {
  outer: for (let i = 0; i + phrase.length <= seq.length; i++) {
    for (let j = 0; j < phrase.length; j++) if (seq[i + j] !== phrase[j]) continue outer;
    return true;
  }
  return false;
}
const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
// Swap misspelled words inside the raw query, keeping operators, quotes and site:.
function replaceWords(raw, fixes) {
  let out = raw;
  for (const [wrong, right] of fixes) {
    const next = out.replace(new RegExp(`(?<![\\p{L}\\p{N}_])${escapeRe(wrong)}(?![\\p{L}\\p{N}_])`, "giu"), right);
    if (next === out) return null;
    out = next;
  }
  return out;
}

// ------------------------------------------------------------------ BM25 + heap Top-K
const idf = (n, df) => Math.log(1 + (n - df + 0.5) / (df + 0.5));
const termScore = (tf, len, avgdl, w, k1, b) => (tf <= 0 ? 0 : (w * tf * (k1 + 1)) / (tf + k1 * (1 - b + (b * len) / avgdl)));

// Bounded min-heap: keeps the k best [doc, score] pairs in O(m log k).
function topK(entries, k) {
  const heap = [];
  const less = (a, b) => a[1] < b[1] || (a[1] === b[1] && a[0] > b[0]);
  const up = (i) => { while (i > 0) { const p = (i - 1) >> 1; if (!less(heap[i], heap[p])) break; [heap[i], heap[p]] = [heap[p], heap[i]]; i = p; } };
  const down = (i) => {
    for (;;) {
      const l = 2 * i + 1, r = l + 1; let s = i;
      if (l < heap.length && less(heap[l], heap[s])) s = l;
      if (r < heap.length && less(heap[r], heap[s])) s = r;
      if (s === i) return; [heap[i], heap[s]] = [heap[s], heap[i]]; i = s;
    }
  };
  for (const e of entries) {
    if (heap.length < k) { heap.push(e); up(heap.length - 1); }
    else if (k > 0 && less(heap[0], e)) { heap[0] = e; down(0); }
  }
  return heap.sort((a, b) => b[1] - a[1] || a[0] - b[0]);
}

// ------------------------------------------------------------------ snippets
const SNIPPET_SCAN_CHARS = 25000; // same bounded prefix the server analyses (repository.py)
function highlight(text, qset) {
  const segs = [];
  for (const part of text.split(/([\p{L}\p{N}_]+)/u)) {
    if (!part) continue;
    const hl = qset.size > 0 && /^[\p{L}\p{N}]/u.test(part) && qset.has(termOf(part));
    if (segs.length && segs[segs.length - 1].highlight === hl) segs[segs.length - 1].text += part;
    else segs.push({ text: part, highlight: hl });
  }
  return segs;
}

function makeSnippet(content, description, qset, window = 32) {
  const words = content.split(/\s+/).filter(Boolean);
  let start = 0;
  if (words.length > window && qset.size) {
    const prefixes = new Set([...qset].map((t) => t.slice(0, 2)));
    const hits = [];
    words.forEach((w, i) => {
      const lw = w.toLowerCase();
      if (prefixes.has(lw.slice(0, 2)) || prefixes.has(lw.slice(1, 3))) { const t = termOf(w); if (qset.has(t)) hits.push([i, t]); }
    });
    let best = [-1, -1], hi = 0; const counts = new Map();
    hits.forEach(([pos], lo) => {
      while (hi < hits.length && hits[hi][0] < pos + window) { counts.set(hits[hi][1], (counts.get(hits[hi][1]) || 0) + 1); hi++; }
      const key = [counts.size, [...counts.values()].reduce((a, c) => a + c, 0)];
      if (key[0] > best[0] || (key[0] === best[0] && key[1] > best[1])) { best = key; start = pos; }
      const t = hits[lo][1]; counts.set(t, counts.get(t) - 1); if (!counts.get(t)) counts.delete(t);
    });
    start = Math.max(0, Math.min(start - 4, words.length - window));
  }
  const end = Math.min(words.length, start + window);
  const text = words.slice(start, end).join(" ") || description;
  const segs = highlight(text, qset);
  if (start > 0) segs.unshift({ text: "… ", highlight: false });
  if (end < words.length) segs.push({ text: " …", highlight: false });
  return segs;
}

function levenshtein(a, b, limit = 2) {
  if (Math.abs(a.length - b.length) > limit) return limit + 1;
  let prev = Array.from({ length: b.length + 1 }, (_, i) => i);
  for (let i = 1; i <= a.length; i++) {
    const cur = [i];
    for (let j = 1; j <= b.length; j++) cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] !== b[j - 1] ? 1 : 0));
    if (Math.min(...cur) > limit) return limit + 1;
    prev = cur;
  }
  return prev[b.length];
}

// ------------------------------------------------------------------ engine
export function createEngine(data) {
  STOP = new Set(data.stopwords);
  const { docs, postings, vocab, k1, b } = data;
  const n = docs.length;
  const avgdl = docs.reduce((s, d) => s + d.len, 0) / Math.max(n, 1);
  const post = new Map(Object.entries(postings).map(([t, list]) => [t, new Map(list)]));
  const words = Object.entries(vocab).map(([w, [, f]]) => [w, f]).sort((a, c) => c[1] - a[1] || (a[0] < c[0] ? -1 : 1));
  const queryLog = new Map();

  function correct(word) {
    if (vocab[word] || word.length < 3) return null;
    const limit = word.length <= 4 ? 1 : 2;
    let best = null;
    for (const [cand, f] of words) {
      if (cand[0] !== word[0]) continue;
      const dist = levenshtein(word, cand, limit);
      if (dist <= limit && (!best || dist < best[0] || (dist === best[0] && f > best[1]))) best = [dist, f, cand];
    }
    return best ? best[2] : null;
  }

  const seqCache = new Map(); // doc -> [title terms, content terms], built on the first phrase query
  const sequences = (d) => {
    let s = seqCache.get(d);
    if (!s) { s = [termSequence(docs[d].title), termSequence(docs[d].content)]; seqCache.set(d, s); }
    return s;
  };

  function spelling(q) {
    if (!q.words.length) return null;
    const fixes = new Map();
    for (const w of q.words) if (!fixes.has(w)) { const f = correct(w); if (f) fixes.set(w, f); }
    if (!fixes.size) return null;
    return replaceWords(q.raw, fixes) || q.words.map((w) => fixes.get(w) || w).join(" ");
  }

  function search(raw, { page = 1, pageSize = 10, domain, autocorrect = true } = {}) {
    const t0 = performance.now();
    const q = parseQuery(raw);
    domain = (domain || q.domain || "").toLowerCase() || null;
    const idfs = Object.fromEntries(q.terms.map((t) => [t, idf(n, post.get(t)?.size || 0)]));
    const scores = new Map(), matched = new Map();
    for (const t of q.terms) {
      for (const [d, tf] of post.get(t) || []) {
        scores.set(d, (scores.get(d) || 0) + termScore(tf, docs[d].len, avgdl, idfs[t], k1, b));
        matched.set(d, (matched.get(d) || 0) + 1);
      }
    }
    const has = (t, d) => post.get(t)?.has(d);
    let cand = [...scores]
      .filter(([d]) => [...q.required].every((t) => has(t, d)) && ![...q.excluded].some((t) => has(t, d)))
      .map(([d, s]) => [d, s * coverage(matched.get(d), q.terms.length)]);
    if (q.phrases.length) cand = cand.filter(([d]) => q.phrases.every((ph) => sequences(d).some((seq) => containsPhrase(seq, ph))));
    const facets = new Map();
    cand.forEach(([d]) => facets.set(docs[d].domain, (facets.get(docs[d].domain) || 0) + 1));
    if (domain) cand = cand.filter(([d]) => docs[d].domain === domain || docs[d].domain.endsWith("." + domain));
    const top = topK(cand, page * pageSize);
    const max = top.length ? top[0][1] : 1;
    const qset = new Set(q.terms);
    const results = top.slice((page - 1) * pageSize).map(([d, score], i) => {
      const doc = docs[d];
      const term_scores = {};
      q.terms.forEach((t) => { if (has(t, d)) term_scores[t] = +termScore(post.get(t).get(d), doc.len, avgdl, idfs[t], k1, b).toFixed(4); });
      return {
        rank: (page - 1) * pageSize + i + 1, doc_id: doc.id, url: doc.url, domain: doc.domain, title: doc.title,
        title_segments: highlight(doc.title, qset), snippet: makeSnippet(doc.content.slice(0, SNIPPET_SCAN_CHARS), doc.description, qset),
        description: doc.description, score: +score.toFixed(4), relevance: +(score / max).toFixed(4),
        matched_terms: matched.get(d), query_terms: q.terms.length,
        coverage: +coverage(matched.get(d), q.terms.length).toFixed(4), term_scores, fetched_at: doc.fetched_at,
      };
    });
    // unknown words get a suggestion even when other words matched ("netwrk protocol")
    const didYouMean = spelling(q);
    if (didYouMean && autocorrect && !cand.length) {
      const fixed = search(didYouMean, { page, pageSize, domain, autocorrect: false });
      if (fixed.total) {
        return { ...fixed, query: raw, corrected_query: didYouMean, did_you_mean: null, took_ms: +(performance.now() - t0).toFixed(3) };
      }
    }
    const normalized = q.words.join(" ");
    if (cand.length && page === 1 && normalized) queryLog.set(normalized, (queryLog.get(normalized) || 0) + 1);
    return {
      query: raw, normalized_query: normalized, terms: q.terms, excluded: [...q.excluded], domain,
      total: cand.length, page, page_size: pageSize, took_ms: +(performance.now() - t0).toFixed(3),
      results, facets: [...facets].sort((a, c) => c[1] - a[1]).slice(0, 10).map(([domain, count]) => ({ domain, count })),
      did_you_mean: didYouMean, corrected_query: null, phrases: q.phrases.map((p) => p.join(" ")), index_size: n,
    };
  }

  function suggest(prefix, limit = 7) {
    const text = normalize(prefix).trim();
    if (!text) return [];
    const out = [];
    const add = (s) => { if (s !== text && !out.includes(s)) out.push(s); };
    [...queryLog].filter(([q]) => q.startsWith(text)).sort((a, c) => c[1] - a[1]).forEach(([q]) => add(q));
    const cut = text.lastIndexOf(" ");
    const head = cut >= 0 ? text.slice(0, cut) : "";
    const last = text.slice(cut + 1).replace(/[^\p{L}\p{N}]/gu, "");
    if (last) for (const [w] of words) { if (out.length >= limit) break; if (w.startsWith(last)) add(`${head} ${w}`.trim()); }
    return out.slice(0, limit);
  }

  return { search, suggest, stem };
}
