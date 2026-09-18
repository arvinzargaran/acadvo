import { useId } from 'react';

/* The mark is the wayfinding vocabulary applied to the letterform: a route
   climbing from a first station to a solid terminus, with the crossbar as an
   interchange. Geometry is on one grid — stroke 44, node 88 (2x stroke), hole
   44 (1x stroke) — so it stays even at any size.

   The node holes are punched with a mask rather than filled white, which is
   what lets the same file sit on the canvas and on ink without a variant. */
function Logo({ size = '1.5rem', className = '', title }) {
  // Masks resolve against document-global ids, so every instance needs its own
  // — the landing page renders this twice at the same size.
  const maskId = `acadvo-holes-${useId()}`;

  return (
    <svg
      viewBox="0 0 512 512"
      width={size}
      height={size}
      className={className}
      style={{ flexShrink: 0 }}
      role={title ? 'img' : 'presentation'}
      aria-label={title}
      aria-hidden={title ? undefined : 'true'}
    >
      {title ? <title>{title}</title> : null}
      <mask id={maskId}>
        <rect width="512" height="512" fill="#fff" />
        <circle cx="227" cy="296" r="22" fill="#000" />
        <circle cx="373" cy="296" r="22" fill="#000" />
        <circle cx="139" cy="416" r="22" fill="#000" />
        <circle cx="373" cy="416" r="22" fill="#000" />
      </mask>
      <g mask={`url(#${maskId})`} fill="var(--wf-live)">
        <g stroke="var(--wf-live)" strokeWidth="44" strokeLinecap="round" fill="none">
          <path d="M139 416 L373 96" />
          <path d="M373 96 L373 416" />
          <path d="M227 296 L373 296" />
        </g>
        <circle cx="373" cy="96" r="44" />
        <circle cx="227" cy="296" r="44" />
        <circle cx="373" cy="296" r="44" />
        <circle cx="139" cy="416" r="44" />
        <circle cx="373" cy="416" r="44" />
      </g>
    </svg>
  );
}

export default Logo;
