// Start form (Main.dc.html): page link, pasted text, or the sample; platforms, language, tone.
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { LimitBanner } from "../components/LimitBanner";
import { SampleButton } from "../components/Nav";
import { PlatformDot } from "../components/PlatformDot";
import { factValue, LANGUAGE_LABEL } from "../lib/facts";
import { formatIsoDate } from "../lib/dates";
import { loadGuest } from "../lib/storage";
import { PLATFORMS, type CampaignDoc, type Language } from "../lib/types";
import { PLATFORM_NAME } from "../lib/share";
import { postCounts, useCampaign } from "../store/campaign";
import { lastStep } from "../store/importer";
import { useStart } from "../store/startSample";

export function StartForm() {
  const navigate = useNavigate();
  const { platforms, language, tone, busy, error, errorCode, errorSource, setOptions, start } = useStart();
  const [url, setUrl] = useState("");
  const [text, setText] = useState("");
  const [showText, setShowText] = useState(false);
  const textRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (errorCode === "fetch_failed") {
      setShowText(true);
      requestAnimationFrame(() => textRef.current?.focus());
    }
  }, [errorCode]);

  async function submitUrl(e: FormEvent) {
    e.preventDefault();
    if (!url.trim()) return;
    if (await start({ kind: "url", url: url.trim() })) navigate("/facts");
  }

  async function submitText(e: FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    if (await start({ kind: "text", text })) navigate("/facts");
  }

  function togglePlatform(p: (typeof PLATFORMS)[number]) {
    const on = platforms.includes(p);
    if (on && platforms.length === 1) return;
    setOptions({ platforms: on ? platforms.filter((x) => x !== p) : PLATFORMS.filter((x) => x === p || platforms.includes(x)) });
  }

  const urlError = error && errorSource === "url" && errorCode !== "fetch_failed";
  const textError = error && (errorSource === "text" || errorCode === "fetch_failed");
  const sampleError = error && errorSource === "sample";

  return (
    <div id="start" className="start rise d2">
      <form className="start-url" onSubmit={submitUrl}>
        <label htmlFor="start-url" className="sr-only">
          Event page link
        </label>
        <input
          id="start-url"
          type="url"
          inputMode="url"
          placeholder="Paste your event page link"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          aria-describedby={urlError ? "start-url-err" : undefined}
          aria-invalid={urlError ? true : undefined}
        />
        <button type="submit" className="btn btn-highlight cta" aria-disabled={busy !== null}>
          {busy === "url" ? "Reading the page..." : "Read the page"}
        </button>
      </form>
      {urlError && (
        <p id="start-url-err" role="alert" className="field-error center">
          {error}
        </p>
      )}

      <div className="start-links">
        <button type="button" className="link-btn" aria-expanded={showText} aria-controls="start-text-panel" onClick={() => setShowText(!showText)}>
          Paste text instead <span aria-hidden="true">&rarr;</span>
        </button>
        <SampleButton className="link-btn" children="Try a sample event →" />
      </div>
      {sampleError && (
        <p role="alert" className="field-error center">
          {error}
        </p>
      )}

      {showText && (
        <form id="start-text-panel" className="start-text card-flat" onSubmit={submitText}>
          <label htmlFor="start-text">Event details</label>
          <textarea
            id="start-text"
            ref={textRef}
            rows={7}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Paste the event description: name, date, time, venue, who it is for, and the registration link."
            aria-describedby={textError ? "start-text-err" : undefined}
            aria-invalid={textError ? true : undefined}
          />
          {textError && (
            <p id="start-text-err" role="alert" className="field-error">
              {error}
            </p>
          )}
        </form>
      )}

      <fieldset className="start-options">
        <legend className="sr-only">Campaign options</legend>
        <div className="start-platforms" role="group" aria-label="Platforms">
          {PLATFORMS.map((p) => (
            <button key={p} type="button" className="toggle" aria-pressed={platforms.includes(p)} onClick={() => togglePlatform(p)}>
              <PlatformDot platform={p} />
              {PLATFORM_NAME[p]}
            </button>
          ))}
        </div>
        <div className="start-fields">
          <label>
            <span>Language</span>
            <select value={language} onChange={(e) => setOptions({ language: e.target.value as Language })}>
              {(Object.keys(LANGUAGE_LABEL) as Language[]).map((l) => (
                <option key={l} value={l}>
                  {LANGUAGE_LABEL[l]}
                  {l !== "en" ? " (early)" : ""}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Tone</span>
            <input value={tone} maxLength={40} onChange={(e) => setOptions({ tone: e.target.value })} />
          </label>
        </div>
      </fieldset>

      {showText && (
        <button type="submit" form="start-text-panel" className="btn btn-primary btn-lg" aria-disabled={busy !== null}>
          {busy === "text" ? "Reading..." : "Check the facts"}
        </button>
      )}
      <LimitBanner />
      <p className="small muted">Public pages only. Saved on this device. No account.</p>
    </div>
  );
}

function summary(doc: CampaignDoc) {
  const counts = postCounts(doc);
  const total = doc.posts.length;
  const approved = counts.approved + counts.scheduled + counts.published;
  const toConfirm = doc.facts.filter((f) => f.status === "needs_review" || (f.critical && f.status === "missing")).length;
  const needs = counts.needs_review ? `${counts.needs_review} ${counts.needs_review === 1 ? "post" : "posts"} to review` : toConfirm ? `${toConfirm} ${toConfirm === 1 ? "fact" : "facts"} to confirm` : total ? `${counts.draft} drafts` : "No posts yet";
  return { approved: `${approved} of ${total} approved`, needs };
}

export function OnThisDevice() {
  const navigate = useNavigate();
  const [guest] = useState(() => {
    const res = loadGuest();
    return res.status === "ok" ? res.doc : null;
  });
  if (!guest) return null;
  const { approved, needs } = summary(guest);
  const date = factValue(guest.facts, "start_date");

  function open() {
    const store = useCampaign.getState();
    if (store.mode !== "guest" || store.doc?.id !== guest!.id) {
      store.reset();
      store.init();
    }
    navigate(`/${lastStep()}`);
  }

  return (
    <section id="recent" className="recent" aria-labelledby="recent-h">
      <h2 id="recent-h" className="section-title">
        On this device
      </h2>
      <button type="button" className="recent-card card" onClick={open}>
        <span className="recent-main">
          <span className="recent-name">{guest.name}</span>
          <span className="recent-meta">
            {date ? `${formatIsoDate(date)} · ` : ""}
            {approved}
          </span>
        </span>
        <span className="pill pill-lime">{needs}</span>
      </button>
    </section>
  );
}
