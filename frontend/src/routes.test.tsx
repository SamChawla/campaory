import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { saveGuest } from "./lib/storage";
import { useCampaign } from "./store/campaign";
import { extractResponse, sampleDoc } from "./test/fixtures";
import { renderApp } from "./test/render";
import { calls, mockApi } from "./test/server";

test("start screen renders the promise and the sample action", () => {
  renderApp("/");
  expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(/event promotion/i);
  expect(screen.getAllByRole("button", { name: /try a sample event/i })).toHaveLength(2);
  expect(screen.getByText("No account needed. Your work is saved in this browser.")).toBeInTheDocument();
});

test("nav is present with the brand", () => {
  renderApp("/");
  expect(screen.getByRole("navigation", { name: /main/i })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /campaory home/i })).toBeInTheDocument();
});

test("unknown route shows a way back", () => {
  renderApp("/nowhere");
  expect(screen.getByRole("heading", { name: /page not found/i })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /back to start/i })).toHaveAttribute("href", "/");
});

test("start screen explains the four steps and where guest work is kept", () => {
  renderApp("/");
  expect(screen.getByRole("heading", { name: /how it works/i })).toBeInTheDocument();
  expect(screen.getAllByRole("listitem")).toHaveLength(4);
  expect(screen.getByText(/your work is saved in this browser/i)).toBeInTheDocument();
});

test.each(["nav", "hero"])("the %s sample button starts the sample and opens Facts", async (which) => {
  mockApi({ "POST /api/brief/extract": () => ({ body: extractResponse() }) });
  const { router } = renderApp("/");
  const buttons = screen.getAllByRole("button", { name: /try a sample event/i });
  await userEvent.click(which === "nav" ? buttons[0] : buttons[1]);
  await waitFor(() => expect(router.state.location.pathname).toBe("/facts"));
  const extract = calls.find((c) => c.key === "POST /api/brief/extract")!;
  expect(extract.body).toEqual({ source: { kind: "sample" } });
  expect(extract.headers["X-Requested-With"]).toBe("campaory");
  expect(await screen.findByRole("heading", { name: /confirm the facts/i })).toBeInTheDocument();
  expect(useCampaign.getState().doc?.name).toBe("Riverside Hack Day");
});

test("a page that cannot be read asks for pasted text with the box focused", async () => {
  mockApi({ "POST /api/brief/extract": () => ({ status: 422, body: { error: { code: "fetch_failed", message: "" } } }) });
  renderApp("/");
  await userEvent.type(screen.getByLabelText(/event page link/i), "https://example.org/e");
  await userEvent.click(screen.getByRole("button", { name: /read the page/i }));
  expect(await screen.findByRole("alert")).toHaveTextContent("We could not read that page. Paste the event text instead.");
  await waitFor(() => expect(screen.getByLabelText(/event details/i)).toHaveFocus());
});

test("on this device appears only when a guest doc exists", () => {
  renderApp("/");
  expect(screen.queryByRole("heading", { name: /on this device/i })).not.toBeInTheDocument();
});

test("on this device lists the guest campaign", () => {
  saveGuest(sampleDoc());
  renderApp("/");
  expect(screen.getByRole("heading", { name: /on this device/i })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /riverside hack day/i })).toBeInTheDocument();
});

test("workspace routes without a campaign go back to start", async () => {
  const { router } = renderApp("/posts");
  await waitFor(() => expect(router.state.location.pathname).toBe("/"));
});

test("guest workspace shows the notice and steps, and no sign-in prompt", async () => {
  saveGuest(sampleDoc());
  renderApp("/upcoming");
  expect(await screen.findByText("Your work is saved on this device only. Sign in to keep it.")).toBeInTheDocument();
  const steps = screen.getByRole("list", { name: /campaign steps/i });
  expect(within(steps).getAllByRole("link").map((a) => a.textContent)).toEqual(["Facts", "Plan", "Posts", "Changes", "Upcoming"]);
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});
