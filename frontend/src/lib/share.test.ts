import { intentUrl, openPlatform } from "./share";

afterEach(() => vi.restoreAllMocks());

function mockClipboard() {
  const writeText = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
  return writeText;
}

test("intent URLs encode the text", () => {
  const text = "Hack day & more #oss\nhttps://ex.org/r?a=1";
  expect(intentUrl("x", text, null)).toBe(`https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}`);
  expect(intentUrl("whatsapp", text, null)).toBe(`https://wa.me/?text=${encodeURIComponent(text)}`);
  expect(intentUrl("linkedin", text, "https://ex.org/r")).toBe(
    "https://www.linkedin.com/sharing/share-offsite/?url=https%3A%2F%2Fex.org%2Fr",
  );
  expect(intentUrl("linkedin", text, null)).toBe("https://www.linkedin.com/feed/");
  expect(intentUrl("instagram", text, null)).toBeNull();
});

test("open copies the exact text first, then opens a new tab", async () => {
  const order: string[] = [];
  const writeText = mockClipboard();
  writeText.mockImplementation(async () => void order.push("copy"));
  const win = { opener: {} } as unknown as Window;
  const open = vi.spyOn(window, "open").mockImplementation(() => {
    order.push("open");
    return win;
  });
  const res = await openPlatform("x", "Exact text", null);
  expect(writeText).toHaveBeenCalledWith("Exact text");
  expect(open).toHaveBeenCalledWith(expect.stringContaining("twitter.com/intent/tweet"), "_blank");
  expect(order).toEqual(["copy", "open"]);
  expect(win.opener).toBeNull();
  expect(res.message).toBe("Copied for X");
});

test("a blocked popup returns the link to show", async () => {
  mockClipboard();
  vi.spyOn(window, "open").mockReturnValue(null);
  const res = await openPlatform("whatsapp", "Hi", null);
  expect(res.opened).toBe(false);
  expect(res.blockedUrl).toMatch(/^https:\/\/wa\.me/);
});

test("instagram copies with the app note and opens nothing", async () => {
  mockClipboard();
  const open = vi.spyOn(window, "open");
  const res = await openPlatform("instagram", "Caption", null);
  expect(open).not.toHaveBeenCalled();
  expect(res.message).toBe("Copied for Instagram. Paste into the Instagram app.");
});
