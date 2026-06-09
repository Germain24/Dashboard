/**
 * En-têtes de sécurité HTTP appliqués à toutes les routes (#194).
 *
 * Appliqués via `headers()` dans next.config.ts. La CSP reste compatible avec
 * Next.js (script inline d'anti-flash thème/densité, HMR en dev) : on autorise
 * `unsafe-inline`/`unsafe-eval` pour les scripts, mais on verrouille le framing
 * (`frame-ancestors 'none'` + X-Frame-Options) contre le clickjacking.
 */

// Origines backend jointes en direct par certains clients (api proxyfié via
// /api est same-origin, mais on tolère l'appel direct au backend local).
const BACKEND_ORIGINS = "http://127.0.0.1:8000 http://localhost:8000";

const csp = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  `connect-src 'self' ${BACKEND_ORIGINS}`,
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join("; ");

export const securityHeaders: { key: string; value: string }[] = [
  { key: "Content-Security-Policy", value: csp },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
];
