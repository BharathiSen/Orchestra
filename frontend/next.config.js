/** @type {import('next').NextConfig} */

// The browser must be allowed to reach the API for both fetch and the chat
// EventStream. Derived from the same variable the client uses, so the policy
// cannot drift from the origin the app actually calls.
const apiOrigin = (() => {
  try {
    return new URL(process.env.NEXT_PUBLIC_API_URL || "http://localhost:18000").origin;
  } catch {
    return "http://localhost:18000";
  }
})();

// Next.js injects inline bootstrap scripts and inline style tags with no nonce
// in the App Router's static output, so 'unsafe-inline' is required for these
// two directives. Everything else is locked to same-origin.
const csp = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  `connect-src 'self' ${apiOrigin}`,
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "object-src 'none'",
].join("; ");

const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=(), interest-cohort=()",
  },
  {
    key: "Strict-Transport-Security",
    value: "max-age=31536000; includeSubDomains",
  },
  { key: "Content-Security-Policy", value: csp },
];

const nextConfig = {
  reactStrictMode: true,
  // Standalone emits a self-contained server bundle for the Docker runtime
  // stage. It is opt-in because the Cloudflare/OpenNext build produces its own
  // output and must not be switched to standalone.
  ...(process.env.NEXT_OUTPUT === "standalone" ? { output: "standalone" } : {}),
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

module.exports = nextConfig;

// Cloudflare binding emulation for `next dev`, opt-in via ENABLE_CLOUDFLARE_DEV.
//
// This spawns a `workerd` binary, which only exists when the platform-specific
// @cloudflare/workerd-* package is installed. In a Linux container it usually is
// not, and the spawn fails asynchronously — outside any try/catch — taking the
// dev server down with it. Gating on an explicit flag keeps Docker and CI
// working while leaving the Cloudflare workflow available to those who want it.
if (process.env.ENABLE_CLOUDFLARE_DEV === "true") {
  try {
    const { initOpenNextCloudflareForDev } = require("@opennextjs/cloudflare");
    initOpenNextCloudflareForDev();
  } catch (error) {
    console.warn(
      "Cloudflare dev bindings requested but unavailable:",
      error instanceof Error ? error.message : error,
    );
  }
}
