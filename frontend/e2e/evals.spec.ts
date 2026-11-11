import { expect, test } from "@playwright/test";

test("evaluations page explains how runs are produced when there are none", async ({ page }) => {
  await page.goto("/login");
  await page.getByRole("button", { name: "Sign up" }).click();
  await page.getByLabel("Full name").fill("Eval Viewer");
  await page.getByLabel("Email").fill(`evals-${Date.now()}@example.com`);
  await page.getByLabel("Password").fill("evals-password-1");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  await page.getByRole("link", { name: "Evaluations" }).click();
  await expect(page).toHaveURL(/\/evals$/);
  await expect(page.getByRole("heading", { name: "Evaluations", level: 1 })).toBeVisible();
  // Runs come from a CLI with a live model, never from the browser.
  await expect(page.getByText("No evaluation runs yet")).toBeVisible();
  await expect(page.getByText("python scripts/run_eval.py --label baseline")).toBeVisible();
});
