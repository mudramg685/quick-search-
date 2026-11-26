export function ResultSkeleton() {
  return (
    <div className="max-w-[640px]" aria-hidden="true">
      <div className="flex items-center gap-3">
        <div className="skeleton h-7 w-7 rounded-full" />
        <div className="space-y-1.5">
          <div className="skeleton h-2.5 w-28" />
          <div className="skeleton h-2 w-44" />
        </div>
      </div>
      <div className="skeleton mt-3 h-5 w-3/4" />
      <div className="skeleton mt-2.5 h-3 w-full" />
      <div className="skeleton mt-1.5 h-3 w-5/6" />
    </div>
  );
}

export function ErrorState({ error, onRetry }) {
  return (
    <div role="alert" className="max-w-[640px] py-6">
      <p className="font-display text-[30px] leading-tight text-ink">Something went sideways.</p>
      <p className="mt-2 text-[15px] text-ink-2">{error?.message || "Unexpected error."}</p>
      {onRetry && (
        <button onClick={onRetry}
          className="focus-ring mt-5 rounded-full border border-line px-4 py-2 text-sm text-ink transition hover:border-ink-3">
          Try again
        </button>
      )}
    </div>
  );
}

export function EmptyState({ query, didYouMean, onSearch, suggestions = [] }) {
  return (
    <div className="max-w-[640px] py-4">
      <p className="font-read text-[17px] text-ink">
        Your search — <span className="font-semibold">{query}</span> — did not match any pages.
      </p>
      {didYouMean && (
        <p className="mt-3 font-read text-[17px] text-ink-2">
          Did you mean{" "}
          <button onClick={() => onSearch(didYouMean)} className="result-title focus-ring rounded-sm font-semibold italic underline-offset-4 hover:underline">
            {didYouMean}
          </button>
          ?
        </p>
      )}
      <div className="mt-5 text-[15px] text-ink-2">
        Suggestions:
        <ul className="mt-2 list-disc space-y-1 pl-6 marker:text-ink-3">
          <li>Check the spelling, or switch on <em>Fix spelling automatically</em> in Settings.</li>
          <li>Use fewer or more general words, or drop the quotes around a phrase.</li>
          <li>This index is small (it only holds what the crawler has fetched) — crawl more from the dashboard.</li>
        </ul>
      </div>
      {suggestions.length > 0 && (
        <p className="mt-5 text-sm text-ink-3">
          Or try{" "}
          {suggestions.map((s, i) => (
            <span key={s}>
              {i > 0 && ", "}
              <button onClick={() => onSearch(s)} className="result-title focus-ring rounded-sm hover:underline">{s}</button>
            </span>
          ))}
          .
        </p>
      )}
    </div>
  );
}
