import { BACKUP_KEY, GUEST_KEY, loadGuest, saveGuest } from "./storage";
import { sampleDoc } from "../test/fixtures";

beforeEach(() => localStorage.clear());
afterEach(() => vi.restoreAllMocks());

test("save then load restores the same document", () => {
  const doc = sampleDoc();
  expect(saveGuest(doc)).toBe("ok");
  const res = loadGuest();
  expect(res.status).toBe("ok");
  if (res.status === "ok") expect(res.doc).toEqual(doc);
  const raw = JSON.parse(localStorage.getItem(GUEST_KEY)!);
  expect(raw.schema).toBe(1);
  expect(typeof raw.savedAt).toBe("string");
});

test("empty storage is empty", () => {
  expect(loadGuest().status).toBe("empty");
});

test("corrupted storage is backed up and reset", () => {
  localStorage.setItem(GUEST_KEY, "{not json");
  expect(loadGuest()).toEqual({ status: "reset", reason: "invalid" });
  expect(localStorage.getItem(BACKUP_KEY)).toBe("{not json");
  expect(localStorage.getItem(GUEST_KEY)).toBeNull();
});

test("newer schema is backed up and reset", () => {
  const raw = JSON.stringify({ schema: 2, savedAt: "x", doc: {} });
  localStorage.setItem(GUEST_KEY, raw);
  expect(loadGuest()).toEqual({ status: "reset", reason: "newer" });
  expect(localStorage.getItem(BACKUP_KEY)).toBe(raw);
});

test("quota errors are reported, not thrown", () => {
  vi.spyOn(Storage.prototype, "setItem").mockImplementation((key: string) => {
    if (key === GUEST_KEY) throw new DOMException("full", "QuotaExceededError");
  });
  expect(saveGuest(sampleDoc())).toBe("quota");
});

test("blocked storage is reported as unavailable", () => {
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
    throw new DOMException("denied", "SecurityError");
  });
  expect(loadGuest().status).toBe("unavailable");
  expect(saveGuest(sampleDoc())).toBe("unavailable");
});
