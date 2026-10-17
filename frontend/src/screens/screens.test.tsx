import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { GUEST_KEY, loadGuest, saveGuest } from "../lib/storage";
import type { CampaignDoc } from "../lib/types";
import { useCampaign } from "../store/campaign";
import { extractResponse, makePost, POST_ID, sampleDoc } from "../test/fixtures";
import { renderApp } from "../test/render";
import { calls, mockApi } from "../test/server";

const USER = { id: "u1", email: "sam@example.org", name: "Sam", avatar_url: null };

/** The server stores UTC, so compare instants rather than offset strings. */
function normalise(doc: CampaignDoc): unknown {
  return JSON.parse(JSON.stringify(doc), (_k, v) =>
    typeof v === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(v) ? new Date(v).toISOString() : v,
  );
}

describe("facts", () => {
  test("the plan stays locked until the required facts are confirmed", async () => {
    mockApi({
      "POST /api/plan/propose": () => ({
        body: { items: [{ title: "Announcement", purpose: "Say it", stage: "pre", scheduled_for: "2026-10-18T09:00:00+05:30", fact_keys: ["event_name"] }] },
      }),
    });
    useCampaign.getState().applyExtraction(extractResponse(), { platforms: ["x"], language: "en", tone: "" });
    const { router } = renderApp("/facts");
    const cta = await screen.findByRole("button", { name: "Make the plan" });
    expect(cta).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByText(/1 of 6 required facts confirmed/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /confirm all 4 to review/i }));
    await userEvent.click(screen.getByRole("button", { name: "Add timezone" }));
    await userEvent.type(screen.getByLabelText("Timezone"), "Asia/Kolkata");
    await userEvent.click(screen.getByRole("button", { name: "Confirm timezone" }));
    expect(screen.getByText(/6 of 6 required facts confirmed/)).toBeInTheDocument();
    expect(cta).toHaveAttribute("aria-disabled", "false");

    await userEvent.click(cta);
    await waitFor(() => expect(router.state.location.pathname).toBe("/plan"));
    const propose = calls.find((c) => c.key === "POST /api/plan/propose")!.body as { facts: { status: string }[]; timezone: string };
    expect(propose.facts.every((f) => f.status === "confirmed")).toBe(true);
    expect(propose.timezone).toBe("Asia/Kolkata");
    expect(await screen.findByRole("heading", { name: "Announcement" })).toBeInTheDocument();
  });

  test("a server blocked answer is shown in plain words", async () => {
    mockApi({ "POST /api/plan/propose": () => ({ status: 422, body: { error: { code: "blocked", message: "", details: { missing: ["timezone"] } } } }) });
    saveGuest(sampleDoc({ plan: [], posts: [] }));
    renderApp("/facts");
    await userEvent.click(await screen.findByRole("button", { name: "Make the plan" }));
    expect(await screen.findByText(/need a valid, confirmed value first: Timezone/)).toBeInTheDocument();
  });
});

describe("plan", () => {
  test("a before-the-event item cannot move past the event", async () => {
    saveGuest(sampleDoc());
    renderApp("/plan");
    await userEvent.click(await screen.findByRole("button", { name: "Edit" }));
    const when = screen.getByLabelText(/date and time/i);
    await userEvent.clear(when);
    await userEvent.type(when, "2026-10-25T10:00");
    await userEvent.click(screen.getByRole("button", { name: "Save item" }));
    expect(screen.getByRole("alert")).toHaveTextContent(/must be dated before 24 Oct 2026/);
  });

  test("a past event shows the server's notice with the follow-up plan", async () => {
    const notice = "This event ended on Saturday, 24 October 2026, so the plan only has follow-up posts. Check the dates if that is wrong.";
    mockApi({
      "POST /api/plan/propose": () => ({
        body: {
          event_status: "past",
          notice,
          items: [{ title: "Post-event thank-you", purpose: "Thank people", stage: "post", scheduled_for: "2026-11-30T09:00:00+05:30", fact_keys: ["event_name"], platforms: ["x"] }],
        },
      }),
    });
    saveGuest({ ...sampleDoc(), plan: [], posts: [] });
    renderApp("/plan");
    await userEvent.click(await screen.findByRole("button", { name: "Make the plan" }));
    expect(await screen.findByText(notice)).toBeInTheDocument();
    expect(screen.getByText("Post-event thank-you")).toBeInTheDocument();
  });
});

describe("posts", () => {
  test("batched generation applies drafts and shows the demo badge", async () => {
    mockApi({
      "POST /api/posts/generate": (body) => {
        const b = body as { items: { id: string }[]; platforms: string[] };
        return {
          body: {
            posts: b.items.flatMap((it) =>
              b.platforms.map((p) => ({ plan_item_id: it.id, platform: p, text: `Post for ${p}`, facts_used: ["event_name"], status: "draft", guard_flags: [], placeholders: [], validation: { ok: true, length: 12, limit: 280 } })),
            ),
            failed: [],
            meta: { provider: "mock" },
          },
        };
      },
      "POST /api/posts/validate": () => ({ body: { validation: { ok: true, length: 12, limit: 280 }, guard_flags: [], placeholders: [] } }),
    });
    saveGuest(sampleDoc({ posts: [] }));
    renderApp("/posts");
    await userEvent.click(await screen.findByRole("button", { name: "Write the posts" }));
    expect(await screen.findByText("Post for linkedin")).toBeInTheDocument();
    expect(screen.getAllByText("Demo model").length).toBeGreaterThan(0);
    expect(useCampaign.getState().doc!.posts).toHaveLength(4);
    const gen = calls.find((c) => c.key === "POST /api/posts/generate")!.body as { facts: { status: string }[] };
    expect(gen.facts.every((f) => f.status === "confirmed")).toBe(true);
  });

  test("failed items are listed with Retry these", async () => {
    mockApi({ "POST /api/posts/generate": () => ({ body: { posts: [], failed: [{ plan_item_id: sampleDoc().plan[0].id, error: "llm_invalid_output" }], meta: { provider: "mock" } } }) });
    saveGuest(sampleDoc({ posts: [] }));
    renderApp("/posts");
    await userEvent.click(await screen.findByRole("button", { name: "Write the posts" }));
    expect(await screen.findByText(/could not be written: Announcement/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry these" })).toBeInTheDocument();
  });

  test("a rate limit shows the retry time and keeps the campaign", async () => {
    mockApi({ "POST /api/posts/generate": () => ({ status: 429, body: { error: { code: "rate_limited", message: "", retry_after_seconds: 720 } }, headers: { "Retry-After": "720" } }) });
    saveGuest(sampleDoc({ posts: [] }));
    renderApp("/posts");
    await userEvent.click(await screen.findByRole("button", { name: "Write the posts" }));
    expect(await screen.findByText(/Try again in 12 minutes, or sign in for a higher limit/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry in/i })).toHaveAttribute("aria-disabled", "true");
    expect(useCampaign.getState().doc!.plan).toHaveLength(1);
  });
});

describe("changes", () => {
  test("a changed fact shows the diff, protects published posts, and accepts the update", async () => {
    const published = makePost({ id: "44444444-4444-4444-8444-444444444444", platform: "linkedin", status: "published", text: "Starts 10:00", published_at: "2026-10-17T05:00:00Z" });
    const draft = makePost({ status: "approved", text: "Starts 10:00 sharp", facts_used: ["start_time"] });
    mockApi({
      "POST /api/impact/analyze": () => ({
        body: {
          affected: [{ post_id: POST_ID, reason: "facts_used", detail: "start_time changed from 10:00 to 09:30" }],
          protected: [{ post_id: published.id, status: "published", note: "Already public. Consider a correction post." }],
          plan_changes: [],
        },
      }),
      "POST /api/impact/redraft": () => ({ body: { proposed_text: "Starts 09:30 sharp", changed_spans: [], reason: "it gives the start time.", facts_used: ["start_time"], guard_flags: [], validation: { ok: true, length: 18, limit: 280 } } }),
    });
    saveGuest(sampleDoc({ posts: [draft, published] }));
    renderApp("/changes");
    await userEvent.selectOptions(await screen.findByLabelText("Fact"), "start_time");
    await userEvent.type(screen.getByLabelText("New value"), "09:30");
    await userEvent.click(screen.getByRole("button", { name: /check what this affects/i }));

    expect(await screen.findByRole("heading", { name: /the start time changed/i })).toBeInTheDocument();
    expect(await screen.findByText("Already public. Consider a correction post.")).toBeInTheDocument();
    expect(document.querySelector("ins")).toHaveTextContent("09:30");
    await userEvent.click(screen.getByRole("button", { name: "Update this post" }));
    const posts = useCampaign.getState().doc!.posts;
    expect(posts[0]).toMatchObject({ text: "Starts 09:30 sharp", status: "needs_review" });
    expect(posts[1]).toEqual(published);
    const redraft = calls.find((c) => c.key === "POST /api/impact/redraft")!.body as { post: { id: string } };
    expect(redraft.post.id).toBe(POST_ID);
  });
});

describe("sign-in and save (LLD 8.4)", () => {
  test("after /?auth=ok the guest doc is imported unchanged, then local is cleared", async () => {
    const guest = sampleDoc();
    saveGuest(guest);
    sessionStorage.setItem("campaory.pendingSave", "1");
    let localAtPost: string | null = "unset";
    mockApi({
      "GET /api/me": () => ({ body: { user: USER } }),
      "POST /api/campaigns": () => {
        localAtPost = localStorage.getItem(GUEST_KEY);
        return { status: 201, body: { id: guest.id, version: 1 } };
      },
      "GET /api/campaigns/33333333-3333-4333-8333-333333333333": () => ({
        body: { ...JSON.parse(JSON.stringify(guest).replace(/\+05:30/g, "")), version: 1 },
      }),
    });
    const { router } = renderApp("/?auth=ok");
    await waitFor(() => expect(router.state.location.pathname).toBe(`/c/${guest.id}/posts`));
    const sent = calls.find((c) => c.key === "POST /api/campaigns")!.body as CampaignDoc;
    expect(normalise(sent)).toEqual(normalise(guest));
    expect(localAtPost).not.toBeNull();
    expect(localStorage.getItem(GUEST_KEY)).toBeNull();
    expect(sessionStorage.getItem("campaory.pendingSave")).toBeNull();
    expect(await screen.findByText("Saved. Your campaign is in your account.")).toBeInTheDocument();
    expect(useCampaign.getState().mode).toBe("saved");
  });

  test("a failed import keeps the local copy and offers Retry", async () => {
    saveGuest(sampleDoc());
    sessionStorage.setItem("campaory.pendingSave", "1");
    mockApi({ "GET /api/me": () => ({ body: { user: USER } }), "POST /api/campaigns": () => ({ status: 500, body: { error: { code: "server_error" } } }) });
    renderApp("/facts?auth=ok");
    expect(await screen.findByText("We could not save yet. Your work is still on this device.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
    expect(loadGuest().status).toBe("ok");
  });

  test("the free-plan limit explains the options", async () => {
    saveGuest(sampleDoc());
    sessionStorage.setItem("campaory.pendingSave", "1");
    mockApi({ "GET /api/me": () => ({ body: { user: USER } }), "POST /api/campaigns": () => ({ status: 409, body: { error: { code: "campaign_limit", message: "", details: { limit: 1 } } } }) });
    renderApp("/facts?auth=ok");
    expect(await screen.findByText(/Delete the old one to save this one, or keep working on this device/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open saved campaigns" })).toBeInTheDocument();
    expect(loadGuest().status).toBe("ok");
  });

  test("signing in without a guest doc goes to saved campaigns", async () => {
    mockApi({ "GET /api/me": () => ({ body: { user: USER } }), "GET /api/campaigns": () => ({ body: { campaigns: [] } }) });
    const { router } = renderApp("/?auth=ok");
    await waitFor(() => expect(router.state.location.pathname).toBe("/saved"));
    expect(await screen.findByText("Nothing saved yet")).toBeInTheDocument();
  });

  test("auth=failed says so and keeps the work", async () => {
    saveGuest(sampleDoc());
    renderApp("/?auth=failed");
    expect(await screen.findByText("Sign-in did not finish. Your work is still here.")).toBeInTheDocument();
  });

  test("without sign-in configured, Save keeps the campaign in this browser", async () => {
    saveGuest(sampleDoc());
    mockApi({ "GET /api/config": () => ({ body: { provider: "mock", model: "mock", llm_is_mock: true, auth_providers: [] } }) });
    renderApp("/facts");
    expect(await screen.findByText("Your work is saved in this browser. Clearing browser data removes it.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Save now" }));
    expect(await screen.findByText("Saved in this browser")).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(loadGuest().status).toBe("ok");
  });

  test("Save opens the sign-in sheet for guests", async () => {
    saveGuest(sampleDoc());
    renderApp("/facts");
    await userEvent.click(await screen.findByRole("button", { name: "Save my campaign" }));
    expect(screen.getByRole("dialog", { name: "Save your campaign" })).toBeInTheDocument();
  });
});

describe("saved campaigns", () => {
  test("lists campaigns with counts and deletes after confirming by name", async () => {
    mockApi({
      "GET /api/me": () => ({ body: { user: USER } }),
      "GET /api/campaigns": () => ({ body: { campaigns: [{ id: "c1", name: "Riverside Hack Day", version: 2, updated_at: "2026-10-17T05:00:00Z", post_counts: { approved: 3, needs_review: 1, published: 2 } }] } }),
      "DELETE /api/campaigns/c1": () => ({ status: 204 }),
    });
    renderApp("/saved");
    const card = (await screen.findByRole("heading", { name: "Riverside Hack Day" })).closest("li")!;
    expect(within(card).getByText("3 approved")).toBeInTheDocument();
    expect(within(card).getByText("1 need review")).toBeInTheDocument();
    expect(within(card).getByText("2 published")).toBeInTheDocument();
    await userEvent.click(within(card).getByRole("button", { name: "Delete" }));
    const dialog = screen.getByRole("dialog", { name: "Delete Riverside Hack Day?" });
    await userEvent.click(within(dialog).getByRole("button", { name: "Delete campaign" }));
    await waitFor(() => expect(screen.queryByRole("heading", { name: "Riverside Hack Day" })).not.toBeInTheDocument());
    expect(calls.some((c) => c.key === "DELETE /api/campaigns/c1" && c.headers["X-Requested-With"] === "campaory")).toBe(true);
  });

  test("saved routes load the campaign and show times in the event timezone", async () => {
    const doc = sampleDoc({ version: 2 });
    const utc = JSON.parse(JSON.stringify(doc).replace("2026-10-18T09:00:00+05:30", "2026-10-18T03:30:00Z"));
    mockApi({ "GET /api/me": () => ({ body: { user: USER } }), [`GET /api/campaigns/${doc.id}`]: () => ({ body: utc }) });
    renderApp(`/c/${doc.id}/plan`);
    expect(await screen.findByText("09:00")).toBeInTheDocument();
    expect(useCampaign.getState().mode).toBe("saved");
    expect(screen.getByRole("link", { name: "Posts" })).toHaveAttribute("href", `/c/${doc.id}/posts`);
  });

  test("another user's campaign reads as not found", async () => {
    mockApi({ "GET /api/me": () => ({ body: { user: USER } }) });
    renderApp("/c/foreign/posts");
    expect(await screen.findByRole("heading", { name: "Campaign not found" })).toBeInTheDocument();
  });
});
