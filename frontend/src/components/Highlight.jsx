// Renders API "segments" ([{text, highlight}]) – React escapes the text, so highlighting
// never requires dangerouslySetInnerHTML.
export function Highlight({ segments, fallback = "" }) {
  if (!segments?.length) return fallback;
  return segments.map((s, i) =>
    s.highlight ? (
      <mark key={i} className="qs-hl">
        {s.text}
      </mark>
    ) : (
      <span key={i}>{s.text}</span>
    ),
  );
}
