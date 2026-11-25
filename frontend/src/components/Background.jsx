// Decorative animated backdrop: drifting aurora blobs, a fading grid and a few twinkling
// "index nodes". Purely CSS animations (GPU-friendly) and disabled by prefers-reduced-motion.
const DOTS = [
  [12, 22, 0], [86, 18, 1.2], [72, 64, 2.1], [20, 70, 0.6], [50, 12, 1.8], [92, 46, 2.7], [6, 48, 3.1], [38, 82, 1.5],
];

export function Background() {
  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden">
      <div className="absolute -left-[10%] -top-[20%] h-[60vh] w-[60vh] rounded-full bg-brand/25 blur-[110px] animate-drift dark:bg-brand/20" />
      <div className="absolute -right-[12%] top-[5%] h-[55vh] w-[55vh] rounded-full bg-brand-2/20 blur-[120px] animate-drift-slow dark:bg-brand-2/15" />
      <div className="absolute bottom-[-25%] left-[30%] h-[50vh] w-[50vh] rounded-full bg-sky-400/15 blur-[120px] animate-drift dark:bg-sky-500/10" />
      <div className="grid-bg absolute inset-0" />
      {DOTS.map(([x, y, d], i) => (
        <span
          key={i}
          className="absolute h-1.5 w-1.5 rounded-full bg-brand animate-twinkle"
          style={{ left: `${x}%`, top: `${y}%`, animationDelay: `${d}s` }}
        />
      ))}
    </div>
  );
}
