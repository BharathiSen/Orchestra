/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Standalone emits a self-contained server bundle for the Docker runtime
  // stage. It is opt-in because the Cloudflare/OpenNext build produces its own
  // output and must not be switched to standalone.
  ...(process.env.NEXT_OUTPUT === "standalone" ? { output: "standalone" } : {}),
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
