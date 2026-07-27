import { useEffect, useRef, useState } from 'react';

/**
 * RippleWake — the wake a small boat leaves on a still lake, trailing the
 * cursor. Not concentric rings: a real Kelvin wake is *directional*.
 *
 *   • two divergent arms — the feathered V that opens behind the boat at the
 *                          classic ~19.5° Kelvin half-angle, drawn as smooth
 *                          continuous curves (Catmull-Rom → Bézier) through the
 *                          path so the wake flows rather than facets, and
 *   • transverse crests  — short arcs bowing in the direction of travel, spaced
 *                          along the path like real transverse waves, filling
 *                          the V just behind the hull.
 *
 * The pointer is the boat. As it moves it seeds wavelets along its path (each
 * remembering the heading there); the arms ride outward and the whole wake
 * fades from the tail as the water settles. Stop moving and nothing new is
 * seeded — the lake goes calm. Colourless throughout (a lit crest + a shadowed
 * back edge, no hue) so it reads on both the paper and dark themes, and kept
 * faint so it never fights the content.
 *
 * Full-screen fixed <canvas>, pointer-events-none. Fine-pointer only, disabled
 * under prefers-reduced-motion.
 */

const CONFIG = {
  MIN_SPEED: 0.04, // px/ms below which the pointer counts as "still"
  SAMPLE_DISTANCE: 5, // px of travel between seeded wavelets (denser = smoother)
  HEADING_SMOOTH: 0.2, // 0–1, how quickly the wake heading eases toward the pointer
  LIFE: 1300, // ms for a wavelet to ride out and fade
  MAX_SAMPLES: 260,

  KELVIN_ANGLE: 0.3401, // 19.5° — the real Kelvin wake half-angle
  ARM_SPREAD: 92, // how far the arms ride out from the path over their life
  ARM_OFFSET: 1.2, // gap (px) between the lit crest and its shadowed back edge

  ARC_EVERY: 3, // draw a transverse crest every Nth sample
  ARC_R_START: 2,
  ARC_R_MAX: 20, // transverse crest radius at full expansion
  ARC_HALF_SPAN: 0.7, // radians; angular half-width of the forward-facing crest

  // Colourless ink levels (peak, before per-wavelet fade).
  ARM_CREST_ALPHA: 0.24,
  ARM_TROUGH_ALPHA: 0.14,
  ARC_CREST_ALPHA: 0.12,
  ARC_TROUGH_ALPHA: 0.07,
  LINE_WIDTH: 1.1,
};

const easeOut = (t) => 1 - Math.pow(1 - t, 3);

export default function RippleWake() {
  const canvasRef = useRef(null);

  const [enabled, setEnabled] = useState(false);
  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return undefined;
    const fine = window.matchMedia('(pointer: fine)');
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setEnabled(fine.matches && !reduce.matches);
    update();
    fine.addEventListener?.('change', update);
    reduce.addEventListener?.('change', update);
    return () => {
      fine.removeEventListener?.('change', update);
      reduce.removeEventListener?.('change', update);
    };
  }, []);

  useEffect(() => {
    if (!enabled) return undefined;
    const canvas = canvasRef.current;
    if (!canvas) return undefined;
    const ctx = canvas.getContext('2d');
    if (!ctx) return undefined;

    let dpr = Math.min(window.devicePixelRatio || 1, 2);
    const resize = () => {
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.floor(window.innerWidth * dpr);
      canvas.height = Math.floor(window.innerHeight * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    window.addEventListener('resize', resize, { passive: true });

    let dark = document.documentElement.classList.contains('dark');
    const themeObserver = new MutationObserver(() => {
      dark = document.documentElement.classList.contains('dark');
    });
    themeObserver.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['class'],
    });

    const crest = (a) => `rgba(255,255,255,${a * (dark ? 1 : 0.85)})`;
    const trough = (a) => `rgba(0,0,0,${a * (dark ? 0.6 : 1)})`;

    // Each sample is a wavelet seed: where the boat was, and its heading there.
    const samples = []; // { x, y, hx, hy, born }
    const pointer = { x: 0, y: 0, has: false };
    let hx = 1; // smoothed heading (unit vector)
    let hy = 0;
    let lastX = 0;
    let lastY = 0;
    let lastTime = performance.now();

    const seed = (x, y) => {
      samples.push({ x, y, hx, hy, born: performance.now() });
      if (samples.length > CONFIG.MAX_SAMPLES) samples.shift();
    };

    const handleMove = (e) => {
      const now = performance.now();
      const dt = now - lastTime || 16;
      const { clientX: x, clientY: y } = e;

      if (!pointer.has) {
        pointer.x = lastX = x;
        pointer.y = lastY = y;
        pointer.has = true;
        lastTime = now;
        return;
      }

      const vx = x - pointer.x;
      const vy = y - pointer.y;
      const speed = Math.hypot(vx, vy) / dt;

      if (speed > CONFIG.MIN_SPEED) {
        const len = Math.hypot(vx, vy) || 1;
        const k = CONFIG.HEADING_SMOOTH;
        hx += (vx / len - hx) * k;
        hy += (vy / len - hy) * k;
        const hl = Math.hypot(hx, hy) || 1;
        hx /= hl;
        hy /= hl;

        let dist = Math.hypot(x - lastX, y - lastY);
        while (dist >= CONFIG.SAMPLE_DISTANCE) {
          const t = CONFIG.SAMPLE_DISTANCE / dist;
          lastX += (x - lastX) * t;
          lastY += (y - lastY) * t;
          seed(lastX, lastY);
          dist = Math.hypot(x - lastX, y - lastY);
        }
      } else {
        lastX = x;
        lastY = y;
      }

      pointer.x = x;
      pointer.y = y;
      lastTime = now;
    };
    window.addEventListener('mousemove', handleMove, { passive: true });

    // Smooth curve through a list of {x,y,fade} points, one Catmull-Rom→Bézier
    // segment at a time so the alpha can taper along its length.
    const smoothCurve = (pts, colorFor) => {
      if (pts.length < 2) return;
      for (let i = 0; i < pts.length - 1; i += 1) {
        const p0 = pts[i - 1] || pts[i];
        const p1 = pts[i];
        const p2 = pts[i + 1];
        const p3 = pts[i + 2] || p2;
        const f = Math.min(p1.fade, p2.fade);
        if (f <= 0.01) continue;
        const c1x = p1.x + (p2.x - p0.x) / 6;
        const c1y = p1.y + (p2.y - p0.y) / 6;
        const c2x = p2.x - (p3.x - p1.x) / 6;
        const c2y = p2.y - (p3.y - p1.y) / 6;
        ctx.strokeStyle = colorFor(f);
        ctx.beginPath();
        ctx.moveTo(p1.x, p1.y);
        ctx.bezierCurveTo(c1x, c1y, c2x, c2y, p2.x, p2.y);
        ctx.stroke();
      }
    };

    let rafId;
    const frame = () => {
      const now = performance.now();
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.lineWidth = CONFIG.LINE_WIDTH;
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';

      // One pass over the live samples: build the four arm point-lists and draw
      // the transverse crests. Anchors ride out along the Kelvin edges with age.
      const upCrest = [];
      const upTrough = [];
      const dnCrest = [];
      const dnTrough = [];

      for (let i = 0; i < samples.length; i += 1) {
        const s = samples[i];
        const age = (now - s.born) / CONFIG.LIFE;
        if (age >= 1) continue;

        const grow = easeOut(age);
        const fade = age < 0.1 ? age / 0.1 : 1 - (age - 0.1) / 0.9;
        const back = Math.atan2(-s.hy, -s.hx);
        const d = grow * CONFIG.ARM_SPREAD;

        const au = back + CONFIG.KELVIN_ANGLE;
        const ad = back - CONFIG.KELVIN_ANGLE;
        const cu = Math.cos(au);
        const su = Math.sin(au);
        const cd = Math.cos(ad);
        const sd = Math.sin(ad);
        upCrest.push({ x: s.x + cu * d, y: s.y + su * d, fade });
        upTrough.push({ x: s.x + cu * (d + CONFIG.ARM_OFFSET), y: s.y + su * (d + CONFIG.ARM_OFFSET), fade });
        dnCrest.push({ x: s.x + cd * d, y: s.y + sd * d, fade });
        dnTrough.push({ x: s.x + cd * (d + CONFIG.ARM_OFFSET), y: s.y + sd * (d + CONFIG.ARM_OFFSET), fade });

        // Transverse crest — a short arc bowing in the direction of travel.
        if (i % CONFIG.ARC_EVERY === 0) {
          const fwd = Math.atan2(s.hy, s.hx);
          const r = CONFIG.ARC_R_START + grow * (CONFIG.ARC_R_MAX - CONFIG.ARC_R_START);
          ctx.strokeStyle = trough(CONFIG.ARC_TROUGH_ALPHA * fade);
          ctx.beginPath();
          ctx.arc(s.x, s.y, r + CONFIG.ARM_OFFSET, fwd - CONFIG.ARC_HALF_SPAN, fwd + CONFIG.ARC_HALF_SPAN);
          ctx.stroke();
          ctx.strokeStyle = crest(CONFIG.ARC_CREST_ALPHA * fade);
          ctx.beginPath();
          ctx.arc(s.x, s.y, Math.max(0.5, r), fwd - CONFIG.ARC_HALF_SPAN, fwd + CONFIG.ARC_HALF_SPAN);
          ctx.stroke();
        }
      }

      // Divergent arms — continuous smooth curves, shadow edge then lit crest.
      smoothCurve(upTrough, (f) => trough(CONFIG.ARM_TROUGH_ALPHA * f));
      smoothCurve(dnTrough, (f) => trough(CONFIG.ARM_TROUGH_ALPHA * f));
      smoothCurve(upCrest, (f) => crest(CONFIG.ARM_CREST_ALPHA * f));
      smoothCurve(dnCrest, (f) => crest(CONFIG.ARM_CREST_ALPHA * f));

      while (samples.length && (now - samples[0].born) / CONFIG.LIFE >= 1) {
        samples.shift();
      }

      rafId = requestAnimationFrame(frame);
    };
    rafId = requestAnimationFrame(frame);

    return () => {
      cancelAnimationFrame(rafId);
      themeObserver.disconnect();
      window.removeEventListener('resize', resize);
      window.removeEventListener('mousemove', handleMove);
    };
  }, [enabled]);

  if (!enabled) return null;

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className="fixed inset-0 z-[45] pointer-events-none"
      style={{ width: '100%', height: '100%' }}
    />
  );
}
