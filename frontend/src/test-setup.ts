import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { useCampaign } from "./store/campaign";
import { useGeneration } from "./store/generation";
import { useSession } from "./store/session";
import { useStart } from "./store/startSample";
import { useUi } from "./store/ui";
import { mockApi } from "./test/server";

// jsdom's AbortSignal is not the one Node's Request accepts; the data router builds a Request
// on every navigation, so drop the signal there. App code only uses the (mocked) fetch.
const NodeRequest = globalThis.Request;
globalThis.Request = class extends NodeRequest {
  constructor(input: RequestInfo | URL, init?: RequestInit) {
    if (init?.signal) {
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      const { signal, ...rest } = init;
      super(input, rest);
    } else super(input, init);
  }
} as typeof Request;

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  mockApi();
});

afterEach(() => {
  cleanup();
  useCampaign.getState().reset();
  useCampaign.setState({ lastMeta: null, storageError: null, storageNotice: null });
  useSession.setState({ user: null, config: null, loaded: false });
  useUi.setState({ toasts: [], limitUntil: null, signInOpen: false, importState: { state: "idle" }, guestBannerHidden: false });
  useStart.setState({ busy: null, error: null, errorCode: null, errorSource: null });
  useGeneration.setState({ running: false, done: 0, total: 0, failed: [] });
  vi.restoreAllMocks();
});
