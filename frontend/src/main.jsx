import React, { Suspense, lazy } from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, HashRouter, Route, Routes } from "react-router-dom";
import { REPO_URL, STATIC } from "./lib/api";
import "./index.css";
import Home from "./pages/Home";
import Results from "./pages/Results";

// The dashboard pulls in the charting library; load it only when visited (code splitting).
const Dashboard = lazy(() => import("./pages/Dashboard"));

function PageFallback() {
  return (
    <div className="mx-auto max-w-6xl space-y-4 px-6 py-24">
      <div className="skeleton h-8 w-64" />
      <div className="skeleton h-32 rounded-2xl" />
    </div>
  );
}

// GitHub Pages has no server-side routing, so the static build uses #/ URLs.
const Router = STATIC ? HashRouter : BrowserRouter;

function StaticBanner() {
  if (!STATIC) return null;
  return (
    <div className="relative z-50 border-b border-line bg-surface px-4 py-2 text-center text-xs text-ink-2">
      Live demo: searching a snapshot of the real index (crawled pages, BM25 ranking) directly in your browser.
      Crawling needs the Python backend —{" "}
      <a href={REPO_URL} target="_blank" rel="noopener noreferrer" className="font-medium text-brand-ink underline underline-offset-2">
        source &amp; setup on GitHub
      </a>
      .
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <Router>
      <StaticBanner />
      <Suspense fallback={<PageFallback />}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/search" element={<Results />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="*" element={<Home />} />
        </Routes>
      </Suspense>
    </Router>
  </React.StrictMode>,
);
