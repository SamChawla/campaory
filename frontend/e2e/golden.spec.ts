// Golden path with the mock model (T3.10): sample → facts → plan → posts → approve → copy →
// change a fact → redraft → reload restores. No sign-in prompt anywhere.
import { expect, test } from "@playwright/test";
import { confirmRequiredFacts, expectNoSignInPrompt, findApprovableCard, goToStep, startSample } from "./helpers";

test.beforeEach(async ({ context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
});

test("guest golden path", async ({ page }) => {
  const popups: string[] = [];
  page.context().on("page", (p) => popups.push(p.url()));

  await startSample(page);
  await expect(page.getByText("Demo model").first()).toBeVisible();
  await confirmRequiredFacts(page);

  await page.getByRole("button", { name: "Make the plan" }).click();
  await expect(page).toHaveURL(/\/plan$/);
  await expect(page.getByRole("heading", { name: "Shape the plan" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Before the event" })).toBeVisible();
  await expectNoSignInPrompt(page);

  await page.getByRole("button", { name: /^Write \d+ posts$/ }).click();
  await expect(page).toHaveURL(/\/posts/);
  await expect(page.getByRole("heading", { name: "Review the posts" })).toBeVisible();
  await expect(page.getByRole("progressbar")).toHaveCount(0, { timeout: 60_000 });
  await expect(page.getByText("Demo model").first()).toBeVisible();

  // Approve one post the server says is clean, then copy it.
  const card = await findApprovableCard(page);
  const platform = await card.getAttribute("data-platform");
  const text = (await card.locator(".post-text").first().innerText()).trim();
  await card.getByRole("button", { name: "Approve" }).click();
  await expect(card.getByText("Approved", { exact: true })).toBeVisible();
  await card.getByRole("button", { name: "Copy text" }).click();
  await expect(page.getByRole("status").getByText(/^Copied for /)).toBeVisible();
  const clip = await page.evaluate(() => navigator.clipboard.readText());
  expect(clip.trim()).toBe(text);

  // Opening the platform never marks it published (BR05).
  if (platform !== "instagram") {
    await card.getByRole("button", { name: /^Open / }).click();
    await expect(card.getByText("Approved", { exact: true })).toBeVisible();
  }
  await expectNoSignInPrompt(page);

  // Change a fact the posts use, and accept the proposed update.
  await goToStep(page, "Changes");
  await expect(page).toHaveURL(/\/changes$/);
  await page.getByLabel("Fact").selectOption("event_name");
  await page.getByLabel("New value").fill("Riverside Hack Day 2026");
  await page.getByRole("button", { name: "Check what this affects" }).click();
  await expect(page.getByRole("heading", { name: "The event name changed" })).toBeVisible();
  const update = page.getByRole("button", { name: "Update this post" }).first();
  await expect(update).toBeVisible({ timeout: 30_000 });
  await expect(page.locator("ins").first()).toBeVisible();
  await update.click();

  // Reload restores everything from this browser.
  const before = await page.evaluate(() => localStorage.getItem("campaory.guest.v1"));
  expect(before).toContain("Riverside Hack Day 2026");
  await page.reload();
  await expect(page.getByRole("heading", { name: "The event name changed" }).or(page.getByRole("heading", { name: "Changes" }))).toBeVisible();
  await goToStep(page, "Posts");
  await expect(page.getByRole("heading", { name: "Review the posts" })).toBeVisible();
  await expect(page.locator("article.post-card").first()).toBeVisible();
  const after = await page.evaluate(() => JSON.parse(localStorage.getItem("campaory.guest.v1") ?? "{}"));
  expect(after.doc.name).toBe("Riverside Hack Day 2026");
  expect(after.doc.posts.length).toBeGreaterThan(0);
  await expectNoSignInPrompt(page);

  // No horizontal scroll at this width.
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});
