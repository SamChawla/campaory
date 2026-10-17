// Save requires sign-in (T4.7). Uses the test-only login route that exists when APP_ENV=test.
import { expect, test } from "@playwright/test";
import { confirmRequiredFacts, startSample } from "./helpers";

test("a guest campaign is saved to the account after sign-in", async ({ page }) => {
  await startSample(page);
  await confirmRequiredFacts(page);

  // As a guest, Save asks to sign in and nothing else does.
  await page.getByRole("button", { name: "Save my campaign" }).click();
  await expect(page.getByRole("dialog", { name: "Save your campaign" })).toBeVisible();
  await page.getByRole("button", { name: "Not now" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);

  const login = await page.request.post("/api/auth/test-login", {
    data: { email: `e2e-${Date.now()}@example.org` },
    headers: { "X-Requested-With": "campaory" },
  });
  expect(login.ok()).toBeTruthy();
  const localDoc = await page.evaluate(() => JSON.parse(localStorage.getItem("campaory.guest.v1") ?? "{}").doc);

  await page.reload();
  await page.getByRole("button", { name: "Save my campaign" }).click();
  await expect(page).toHaveURL(new RegExp(`/c/${localDoc.id}/`));
  await expect(page.getByText("Saved. Your campaign is in your account.")).toBeVisible();
  expect(await page.evaluate(() => localStorage.getItem("campaory.guest.v1"))).toBeNull();

  await page.goto("/saved");
  await expect(page.getByRole("heading", { name: localDoc.name })).toBeVisible();
  await page.getByRole("button", { name: "Open" }).first().click();
  await expect(page).toHaveURL(new RegExp(`/c/${localDoc.id}/`));
});
