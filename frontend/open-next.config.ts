import { defineCloudflareConfig } from "@opennextjs/cloudflare";
import staticAssetsIncrementalCache from "@opennextjs/cloudflare/overrides/incremental-cache/static-assets-incremental-cache";

// Every page in this app is prerendered at build time and nothing uses
// revalidation or ISR (client pages fetch their data in the browser). With no
// incremental cache configured, OpenNext reported `x-nextjs-cache: MISS` on
// every request and booted the Next server inside the Worker just to return a
// file that never changes — 230 ms to 1.4 s to first byte.
//
// - staticAssetsIncrementalCache: serve the prerendered output from Workers
//   static assets. Read-only by design; switch to the R2 cache if a page ever
//   needs `revalidate`.
// - enableCacheInterception: answer cache hits before the Next server is
//   loaded at all. Must be turned off if Partial Prerendering is adopted.
export default defineCloudflareConfig({
  incrementalCache: staticAssetsIncrementalCache,
  enableCacheInterception: true,
});
