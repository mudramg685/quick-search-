import { AlertTriangle, RotateCw, SearchX } from "lucide-react";

export function ResultSkeleton() {
  return (
    <div className="rounded-2xl border border-line bg-surface p-5" aria-hidden="true">
      <div className="flex items-center gap-2">
        <div className="skeleton h-6 w-6 rounded-lg" />
        <div className="skeleton h-3 w-40" />
      </div>
      <div className="skeleton mt-4 h-5 w-3/4" />
      <div className="skeleton mt-3 h-3 w-full" />
      <div className="skeleton mt-2 h-3 w-5/6" />
      <div className="skeleton mt-4 h-2 w-24 rounded-full" />
    </div>
  );
}

export function ErrorState({ error, onRetry }) {
  return (
    <div role="alert" className="rounded-2xl border border-red-500/30 bg-surface p-8 text-center">
      <div className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-red-500/10 text-red-600 dark:text-red-400">
        <AlertTriangle size={22} />
      </div>
      <h3 className="mt-4 font-display text-lg font-semibold">Something went sideways</h3>
      <p className="mx-auto mt-1 max-w-md text-sm text-ink-2">{error?.message || "Unexpected error."}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="focus-ring mt-5 inline-flex items-center gap-2 rounded-xl border border-line px-4 py-2 text-sm font-medium transition hover:bg-surface-2"
        >
          <RotateCw size={15} /> Try again
        </button>
      )}
    </div>
  );
}

export function EmptyState({ query, didYouMean, onSearch, suggestions = [] }) {
  return (
    <div className="rounded-2xl border border-dashed border-line bg-surface/60 px-6 py-12 text-center">
      <div className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-surface-2 text-ink-3">
        <SearchX size={26} />
      </div>
      <h3 className="mt-4 font-display text-xl font-semibold">
        No pages match <span className="text-gradient">“{query}”</span>
      </h3>
      {didYouMean ? (
        <p className="mt-2 text-ink-2">
          Did you mean{" "}
          <button onClick={() => onSearch(didYouMean)} className="focus-ring rounded font-semibold text-brand-ink underline decoration-brand/40 underline-offset-4 hover:decoration-brand">
            {didYouMean}
          </button>
          ?
        </p>
      ) : (
        <p className="mx-auto mt-2 max-w-md text-sm text-ink-2">
          Try fewer or more general words, check the spelling, or crawl more pages from the dashboard.
        </p>
      )}
      {suggestions.length > 0 && (
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          {suggestions.map((s) => (
            <button key={s} onClick={() => onSearch(s)} className="focus-ring rounded-full border border-line bg-surface px-3.5 py-1.5 text-sm text-ink-2 transition hover:border-brand/40 hover:text-ink">
              {s}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
