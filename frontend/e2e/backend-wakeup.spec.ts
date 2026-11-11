import { expect, test } from "@playwright/test";

// The hosted backend sleeps when idle. The login page must say so rather than
// leave a first-time visitor guessing why sign-in hangs.

test("login explains a slow backend, then confirms it is awake", async ({ page }) => {
  // Hold the wake-up ping for 3 s: a deterministic stand-in for a cold start.
  await page.route("**/health/live", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 3000));
    await route.fulfill({ status: 200, body: "{}" });
  });
  await page.goto("/login");
  await expect(page.getByText(/Waking up the backend/)).toBeVisible();
  await expect(page.getByText("Backend is awake.")).toBeVisible({ timeout: 10_000 });
});

test("login stays quiet when the backend answers promptly", async ({ page }) => {
  await page.goto("/login");
  // The real e2e backend is already up; give the ping time to resolve.
  await page.waitForTimeout(2500);
  await expect(page.getByText(/Waking up the backend/)).toHaveCount(0);
  await expect(page.getByText("Backend is awake.")).toHaveCount(0);
});

test("login reports an unreachable backend", async ({ page }) => {
  await page.route("**/health/live", (route) => route.abort("internetdisconnected"));
  await page.goto("/login");
  await expect(page.getByText(/Can't reach the backend/)).toBeVisible();
});
