import { expect, type Locator, type Page } from "@playwright/test";

export const isPhone = (page: Page) => (page.viewportSize()?.width ?? 1280) < 768;

/** Values used when the mock extractor leaves a required fact empty. */
const FILL: Record<string, string> = {
  event_name: "Riverside Open Source Hack Day 2026",
  start_date: "2026-10-24",
  timezone: "Asia/Kolkata",
  audience: "Students and early-career developers",
  registration_url: "https://example.org/riverside-hackday/register",
};

export async function expectNoSignInPrompt(page: Page) {
  await expect(page.getByRole("dialog", { name: "Save your campaign" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /continue with google/i })).toHaveCount(0);
}

export async function goToStep(page: Page, name: string) {
  if (isPhone(page)) {
    const menu = page.getByRole("button", { name: "Menu" });
    if (await menu.isVisible()) await menu.click();
  }
  await page.getByRole("list", { name: "Campaign steps" }).getByRole("link", { name, exact: true }).click();
}

export async function startSample(page: Page) {
  await page.goto("/");
  await expectNoSignInPrompt(page);
  // The hero button sits next to "Paste text instead".
  await page.locator("#start").getByRole("button", { name: /try a sample event/i }).click();
  await expect(page).toHaveURL(/\/facts$/);
  await expect(page.getByRole("heading", { name: "Confirm the facts" })).toBeVisible();
}

/** Confirm every required fact, filling in any the extractor did not find. */
export async function confirmRequiredFacts(page: Page) {
  const confirmAll = page.getByRole("button", { name: /^Confirm all \d+ to review$/ });
  if (await confirmAll.isVisible()) await confirmAll.click();
  for (const [key, value] of Object.entries(FILL)) {
    const row = page.locator(`[data-fact="${key}"]`).first();
    if ((await row.getByText("Confirmed", { exact: true }).count()) > 0) continue;
    await row.getByRole("button", { name: /^(Add|Edit) / }).click();
    const input = row.locator("input, textarea, select").first();
    await input.fill(value);
    await row.getByRole("button", { name: /^Confirm / }).click();
    await expect(row.getByText("Confirmed", { exact: true })).toBeVisible();
  }
  await expect(page.getByText("6 of 6 required facts confirmed.")).toBeVisible();
}

/** Returns a visible post card whose Approve button is enabled, switching tabs on phones. */
export async function findApprovableCard(page: Page): Promise<Locator> {
  const tabs = page.getByRole("tab");
  const tabCount = isPhone(page) ? await tabs.count() : 1;
  for (let i = 0; i < tabCount; i++) {
    if (isPhone(page)) await tabs.nth(i).click();
    const cards = page.locator("article.post-card:visible");
    // Wait for the server validation of each card.
    await expect(page.getByRole("button", { name: "Checking..." })).toHaveCount(0);
    const n = await cards.count();
    for (let j = 0; j < n; j++) {
      const card = cards.nth(j);
      const approve = card.getByRole("button", { name: "Approve" });
      if ((await approve.count()) && (await approve.getAttribute("aria-disabled")) === "false") return card;
    }
  }
  throw new Error("No post could be approved; check the mock writer output.");
}
