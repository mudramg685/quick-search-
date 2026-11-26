import React, { Suspense, lazy, useState } from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, HashRouter, Route, Routes } from "react-router-dom";
import { X } from "lucide-react";
import { REPO_URL, STATIC } from "./lib/api";
import { applySettings } from "./lib/settings";
import "./index.css";
import Home from "./pages/Home";
import Results from "./pages/Results";

// The dashboard pulls in the charting library; load it only when visited (code splitting).
const Dashboard = lazy(() => import("./pages/Dashboard"));

function PageFallback() {
  return (
    <div className="mx-auto max-w-6xl space-y-4 px-6 py-24">
      <div className="skeleton h-8 w-64" />
      <div className="skeleton h-32" />
    </div>
  );
}

// GitHub Pages has no server-side routing, so the static build uses #/ URLs.
const Router = STATIC ? HashRouter : BrowserRouter;

function StaticBanner() {
  const [hidden, setHidden] = useState(() => {
    try { return sessionStorage.getItem("qs-banner") === "0"; } catch { return false; }
  });
  if (!STATIC || hidden) return null;
  const close = () => {
    setHidden(true);
    try { sessionStorage.setItem("qs-banner", "0"); } catch { /* fine */ }
  };
  return (
    <div className="relative z-50 flex items-center justify-center gap-3 border-b border-line bg-surface-2/70 px-10 py-1.5 text-center text-[12.5px] text-ink-2">
      <p>
        <span className="smallcaps font-medium text-ink">Demo</span> · searching a saved snapshot of the real index, right in your browser.
        <span className="hidden sm:inline">Crawling needs the local backend </span>·{" "}
        <a href={REPO_URL} target="_blank" rel="noopener noreferrer" className="underline underline-offset-2 hover:text-ink">source</a>
      </p>
      <button onClick={close} aria-label="Dismiss" className="focus-ring absolute right-3 grid h-6 w-6 place-items-center rounded-full text-ink-3 hover:text-ink">
        <X size={14} />
      </button>
    </div>
  );
}

applySettings();

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <Router>
      <div className="flex min-h-screen flex-col">
        <StaticBanner />
        <div className="flex flex-1 flex-col">
          <Suspense fallback={<PageFallback />}>
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/search" element={<Results />} />
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="*" element={<Home />} />
            </Routes>
          </Suspense>
        </div>
      </div>
    </Router>
  </React.StrictMode>,
);
