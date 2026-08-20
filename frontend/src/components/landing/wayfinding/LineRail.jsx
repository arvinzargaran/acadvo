import { useEffect, useState } from 'react';

/**
 * The spine: one continuous line down the left margin with a station for each
 * section, so scrolling the page reads as travelling it. Replaces a plain
 * progress bar — the position indicator and the table of contents are the same
 * object here, which is what a route diagram in a train carriage is.
 *
 * Decorative and desktop-only; the section headings are the real navigation.
 */
export default function LineRail({ stops }) {
  const [active, setActive] = useState(stops[0]?.id);

  useEffect(() => {
    const sections = stops
      .map((s) => document.getElementById(s.id))
      .filter(Boolean);
    if (!sections.length) return undefined;

    const io = new IntersectionObserver(
      (entries) => {
        // The topmost section currently crossing the middle band wins.
        const hit = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
        if (hit) setActive(hit.target.id);
      },
      { rootMargin: '-45% 0px -45% 0px' },
    );
    sections.forEach((s) => io.observe(s));
    return () => io.disconnect();
  }, [stops]);

  const activeIndex = Math.max(0, stops.findIndex((s) => s.id === active));

  return (
    <nav
      aria-label="Page sections"
      className="wf-rail fixed left-8 top-1/2 -translate-y-1/2 z-40"
    >
      <ol className="relative flex flex-col gap-7 pl-[9px]">
        {/* Track behind the stations: travelled portion in the live colour. */}
        <span
          aria-hidden="true"
          className="absolute left-[9px] top-1 bottom-1 w-[3px] -translate-x-1/2 rounded-full"
          style={{ background: 'var(--wf-rule)' }}
        />
        <span
          aria-hidden="true"
          className="absolute left-[9px] top-1 w-[3px] -translate-x-1/2 rounded-full transition-all duration-500"
          style={{
            background: 'var(--wf-live)',
            height: `calc((100% - 0.5rem) * ${activeIndex / Math.max(1, stops.length - 1)})`,
          }}
        />

        {stops.map((stop, i) => {
          const isActive = stop.id === active;
          const travelled = i <= activeIndex;
          return (
            <li key={stop.id} className="relative">
              <a
                href={`#${stop.id}`}
                className="group flex items-center gap-3.5"
                aria-current={isActive ? 'true' : undefined}
              >
                <span
                  aria-hidden="true"
                  className="relative z-10 block rounded-full transition-all duration-300"
                  style={{
                    width: isActive ? 15 : 9,
                    height: isActive ? 15 : 9,
                    marginLeft: isActive ? -3 : 0,
                    background: travelled ? 'var(--wf-live)' : 'var(--wf-canvas)',
                    boxShadow: `0 0 0 3px ${travelled ? 'var(--wf-live)' : 'var(--wf-rule)'}`,
                  }}
                />
                <span
                  className="wf-signage text-[10px] transition-opacity duration-300 opacity-0 group-hover:opacity-100 group-focus-visible:opacity-100 whitespace-nowrap"
                  style={{ color: 'var(--wf-muted)', opacity: isActive ? 1 : undefined }}
                >
                  {stop.label}
                </span>
              </a>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
