import { expect, test, type Page } from "@playwright/test";

// The product's core promise, end to end: a turn goes in, streams back with
// live agent steps, and leaves an execution record that can be opened.

async function signUp(page: Page): Promise<void> {
  // example.com, not .test: the backend's email validator rejects special-use TLDs.
  const email = `e2e-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  await page.goto("/login");
  await page.getByRole("button", { name: "Sign up" }).click();
  await page.getByLabel("Full name").fill("E2E Tester");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("e2e-password-123");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

async function createProject(page: Page): Promise<string> {
  await page.goto("/projects");
  await page.getByLabel("Name").fill("E2E project");
  await page.getByRole("button", { name: "Create project" }).click();
  await expect(page).toHaveURL(/\/projects\/\d+$/);
  return page.url().split("/").pop() as string;
}

test("signed-out visitors are sent to the login page", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login$/);
});

test("an Orchestra turn streams agent steps and is traced", async ({ page }) => {
  await signUp(page);
  const projectId = await createProject(page);

  await page.goto(`/projects/${projectId}/chat`);
  await page.getByLabel(/Orchestra/).check();
  await page
    .getByLabel("Message")
    .fill("Compare Redis and Postgres for storing agent memory, in detail.");
  await page.getByRole("button", { name: "Send" }).click();

  // A comparison prompt takes the full route: all four agents report in.
  const trace = page.getByText(/Agent Execution/).locator("..");
  await expect(trace).toContainText("Planner");
  await expect(trace).toContainText("Research");
  await expect(trace).toContainText("Writer");
  await expect(trace).toContainText("Reviewer");
  await expect(page.getByText(/Deterministic test reply to:/).last()).toBeVisible();
  await expect(page.getByRole("button", { name: "Send" })).toBeVisible();

  // The turn left an execution record behind.
  await page.goto(`/projects/${projectId}/observability`);
  await page.getByRole("link", { name: /Execution #\d+/ }).first().click();
  await expect(page.getByRole("heading", { name: /Execution #\d+/ })).toBeVisible();
  await expect(page.getByText(/orchestra_full/).first()).toBeVisible();
  await expect(page.getByText(/· completed/).first()).toBeVisible();

  // Step names are lowercase in the DOM and capitalised by CSS.
  const steps = page.getByRole("heading", { name: "Pipeline steps" }).locator("..");
  for (const agent of ["planner", "research", "writer", "reviewer"]) {
    await expect(steps).toContainText(new RegExp(agent, "i"));
  }
  // Every stage succeeded. A failed agent once hid behind "completed".
  await expect(steps).not.toContainText("✗");
});
