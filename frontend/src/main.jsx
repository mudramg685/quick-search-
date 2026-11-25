import React, { Suspense, lazy } from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
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

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <Suspense fallback={<PageFallback />}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/search" element={<Results />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="*" element={<Home />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  </React.StrictMode>,
);
