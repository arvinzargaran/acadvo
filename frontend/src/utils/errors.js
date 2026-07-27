// FastAPI validation errors return `detail` as an array of {msg, loc, ...}
// objects rather than a string. Rendering that array directly as JSX crashes
// React, so every call site needs to normalize it first.
export function getErrorMessage(err, fallback) {
  const detail = err?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map((d) => d.msg || String(d)).join(', ');
  return fallback;
}
