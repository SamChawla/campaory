import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { wordDiff } from "../lib/worddiff";
import { useCampaign } from "../store/campaign";
import { useSession } from "../store/session";
import { useUi } from "../store/ui";
import { makePost, POST_ID, sampleDoc } from "../test/fixtures";
import { calls, mockApi } from "../test/server";
import { Diff } from "./Diff";
import { ModelBadge } from "./ModelBadge";
import { PostCard } from "./PostCard";
import { SignInSheet } from "./SignInSheet";
import { StatusChip } from "./StatusChip";

const ok = (length = 28) => ({ validation: { ok: true, length, limit: 280, hashtags: 0, issues: [] }, guard_flags: [], placeholders: [] });

test("status chips carry text, not colour alone", () => {
  render(
    <>
      <StatusChip status="needs_review" />
      <StatusChip status="missing" />
      <StatusChip status="superseded" />
    </>,
  );
  expect(screen.getByText("Needs review")).toBeInTheDocument();
  expect(screen.getByText("Missing")).toBeInTheDocument();
  expect(screen.getByText("Superseded")).toHaveClass("strike");
});

test("word diff keeps both texts exactly", () => {
  const segs = wordDiff("Sat 24 Oct, 10:00 IST", "Sat 24 Oct, 09:30 IST");
  expect(segs.filter((s) => s.kind !== "added").map((s) => s.text).join("")).toBe("Sat 24 Oct, 10:00 IST");
  expect(segs.filter((s) => s.kind !== "removed").map((s) => s.text).join("")).toBe("Sat 24 Oct, 09:30 IST");
  expect(segs.find((s) => s.kind === "removed")?.text).toBe("10:00");
  expect(segs.find((s) => s.kind === "added")?.text).toBe("09:30");
});

test("diff shows removed and added words with a legend", () => {
  render(<Diff oldText="Starts 10:00" newText="Starts 09:30" />);
  expect(screen.getByText(/struck-through text is removed/i)).toBeInTheDocument();
  expect(document.querySelector("del")).toHaveTextContent("10:00");
  expect(document.querySelector("ins")).toHaveTextContent("09:30");
});

test("model badge shows Demo model for the mock provider", () => {
  useSession.setState({ config: { provider: "euri", llm_is_mock: false, auth_providers: [] } });
  const { rerender } = render(<ModelBadge />);
  expect(screen.queryByText("Demo model")).not.toBeInTheDocument();
  act(() => useCampaign.setState({ lastMeta: { provider: "mock" } }));
  rerender(<ModelBadge />);
  expect(screen.getByText("Demo model")).toBeInTheDocument();
});

function renderCard(post = makePost()) {
  useCampaign.getState().loadSaved(sampleDoc({ posts: [post] }));
  const live = () => useCampaign.getState().doc!.posts[0];
  const utils = render(
    <MemoryRouter>
      <Card />
    </MemoryRouter>,
  );
  function Card() {
    const p = useCampaign((s) => s.doc!.posts[0]);
    return <PostCard post={p} tz="Asia/Kolkata" />;
  }
  return { live, ...utils };
}

describe("post card", () => {
  test("approve waits for the server and then approves", async () => {
    mockApi({ "POST /api/posts/validate": () => ({ body: ok() }) });
    const { live } = renderCard();
    const approve = screen.getByRole("button", { name: /checking/i });
    expect(approve).toHaveAttribute("aria-disabled", "true");
    expect(await screen.findByText("28 of 280 characters. Links count as 23.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Approve" }));
    expect(live().status).toBe("approved");
    expect(screen.getByRole("button", { name: "Copy text" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open X" })).toBeInTheDocument();
  });

  test("over-limit or unknown facts block approval with the reason", async () => {
    mockApi({
      "POST /api/posts/validate": () => ({
        body: {
          validation: { ok: false, length: 300, limit: 280, issues: [{ level: "error", code: "too_long", message: "X allows 280 characters; this is 300." }] },
          guard_flags: [{ code: "UNKNOWN_DATE", token: "25 Oct", span: [0, 6], blocking: true }],
          placeholders: [],
        },
      }),
    });
    const { live } = renderCard();
    expect(await screen.findByText(/X allows 280 characters; this is 300/)).toBeInTheDocument();
    expect(screen.getByText(/not in your facts: 25 Oct/)).toBeInTheDocument();
    const approve = screen.getByRole("button", { name: "Approve" });
    expect(approve).toHaveAttribute("aria-disabled", "true");
    await userEvent.click(approve);
    expect(live().status).toBe("draft");
  });

  test("live counter while editing comes from /posts/validate", async () => {
    mockApi({ "POST /api/posts/validate": (body) => ({ body: ok((body as { text: string }).text.length) }) });
    renderCard();
    await screen.findByText(/28 of 280/);
    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    const box = screen.getByLabelText("Text for X");
    await userEvent.clear(box);
    await userEvent.type(box, "Short");
    expect(await screen.findByText(/^5 of 280 characters/)).toBeInTheDocument();
    const last = calls.filter((c) => c.key === "POST /api/posts/validate").at(-1)!;
    expect(last.body).toMatchObject({ platform: "x", text: "Short" });
  });

  test("editing an approved post returns it to draft", async () => {
    mockApi({ "POST /api/posts/validate": () => ({ body: ok() }) });
    const { live } = renderCard(makePost({ status: "approved" }));
    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    await userEvent.type(screen.getByLabelText("Text for X"), "!");
    await userEvent.click(screen.getByRole("button", { name: "Save text" }));
    expect(live().status).toBe("draft");
    expect(live().versions.at(-1)?.text).toBe("Riverside Hack Day on 24 Oct");
  });

  test("published posts cannot be edited and opening does not mark published", async () => {
    Object.defineProperty(navigator, "clipboard", { value: { writeText: vi.fn().mockResolvedValue(undefined) }, configurable: true });
    const open = vi.spyOn(window, "open").mockReturnValue({ opener: {} } as Window);
    const { live } = renderCard(makePost({ status: "published", published_at: "2026-10-17T05:00:00Z" }));
    expect(screen.queryByRole("button", { name: "Edit" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /make shorter/i })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Open X" }));
    expect(open).toHaveBeenCalled();
    expect(live().status).toBe("published");
  });

  test("opening an approved post keeps it approved (BR05)", async () => {
    mockApi({ "POST /api/posts/validate": () => ({ body: ok() }) });
    Object.defineProperty(navigator, "clipboard", { value: { writeText: vi.fn().mockResolvedValue(undefined) }, configurable: true });
    vi.spyOn(window, "open").mockReturnValue({ opener: {} } as Window);
    const { live } = renderCard(makePost({ status: "approved" }));
    await userEvent.click(screen.getByRole("button", { name: "Open X" }));
    await waitFor(() => expect(useUi.getState().toasts.at(-1)?.message).toBe("Copied for X"));
    expect(live().status).toBe("approved");
  });

  test("make shorter keeps the previous text as a version", async () => {
    mockApi({
      "POST /api/posts/validate": () => ({ body: ok() }),
      "POST /api/posts/revise": () => ({ body: { text: "Hack Day 24 Oct", facts_used: ["event_name"], guard_flags: [], validation: { ok: true, length: 15, limit: 280 }, status: "draft", meta: { provider: "mock" } } }),
    });
    const { live } = renderCard();
    await userEvent.click(screen.getByRole("button", { name: /make shorter/i }));
    await waitFor(() => expect(live().text).toBe("Hack Day 24 Oct"));
    expect(live().versions.at(-1)).toMatchObject({ reason: "revise:make_shorter", text: "Riverside Hack Day on 24 Oct" });
    expect(live().id).toBe(POST_ID);
  });
});

describe("sign-in sheet", () => {
  test("shows Google only when the server lists it, and sets pendingSave before redirect", async () => {
    useSession.setState({ config: { provider: "mock", llm_is_mock: true, auth_providers: ["google"] } });
    useUi.setState({ signInOpen: true });
    const assign = vi.fn();
    Object.defineProperty(window, "location", { value: { ...window.location, assign }, configurable: true });
    render(
      <MemoryRouter>
        <SignInSheet />
      </MemoryRouter>,
    );
    expect(screen.getByRole("dialog", { name: "Save your campaign" })).toBeInTheDocument();
    expect(screen.getByText("We store your name, email and your campaigns. No passwords.", { exact: false })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /continue with google/i }));
    expect(sessionStorage.getItem("campaory.pendingSave")).toBe("1");
    expect(assign).toHaveBeenCalledWith("/api/auth/login/google");
    expect(screen.getByRole("button", { name: /opening google/i })).toBeDisabled();
  });

  test("no Google button when it is not configured; Escape closes", async () => {
    useSession.setState({ config: { provider: "mock", llm_is_mock: true, auth_providers: [] } });
    useUi.setState({ signInOpen: true });
    render(
      <MemoryRouter>
        <SignInSheet />
      </MemoryRouter>,
    );
    expect(screen.queryByRole("button", { name: /continue with google/i })).not.toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    expect(useUi.getState().signInOpen).toBe(false);
  });
});
