import { PlatformDot, type Platform } from "../components/PlatformDot";
import { OnThisDevice, StartForm } from "./StartForm";

const PLATFORMS: Platform[] = ["linkedin", "instagram", "whatsapp", "x"];

const BAND = ["One brief", "Four platforms", "Every fact confirmed", "You press publish"];

const STEPS = [
  {
    n: "01",
    tint: "step-blue",
    title: "Facts",
    text: "Dates, venue, links and names are pulled out with the sentence each came from.",
    who: "You confirm",
  },
  {
    n: "02",
    tint: "step-mint",
    title: "Plan",
    text: "A calendar of announcements, reminders and thank-yous. Move or delete any of it.",
    who: "You shape",
  },
  {
    n: "03",
    tint: "step-peach",
    title: "Posts",
    text: "One draft per platform, built only from facts you confirmed.",
    who: "You approve",
  },
  {
    n: "04",
    tint: "step-yellow",
    title: "Publish",
    text: "Copy the text and open the platform. Nothing is posted for you.",
    who: "You post",
  },
];

export function Start() {
  return (
    <>
      <section className="hero">
        <div className="hero-orbit" aria-hidden="true">
          {PLATFORMS.map((p) => (
            <PlatformDot key={p} platform={p} className={`float orbit-${p}`} />
          ))}
          <span className="float orbit-blob orbit-pink" />
          <span className="float orbit-blob orbit-lime" />
        </div>
        <div className="hero-dots" aria-hidden="true">
          {PLATFORMS.map((p) => (
            <PlatformDot key={p} platform={p} />
          ))}
        </div>
        <h1 className="display rise">
          Event promotion, minus the <span className="underline">copy-paste</span>
        </h1>
        <p className="lead rise d1">
          Give Campaory a page link or your event details. You confirm the facts once, it drafts
          the LinkedIn, Instagram, WhatsApp and X posts from them, and each post waits for your OK.
        </p>
        <StartForm />

        <p className="small muted rise d3">
          No account needed. Your work stays in this browser until you sign in to save it.
        </p>
      </section>

      <div className="band" aria-hidden="true">
        <div className="band-track">
          {[...BAND, ...BAND].map((word, i) => (
            <span key={i} className="band-item">
              {word}
              <span className={i % 2 ? "band-dot lime" : "band-dot coral"}>●</span>
            </span>
          ))}
        </div>
      </div>

      <section id="how" className="how">
        <h2 className="section-title">How it works in 4 steps</h2>
        <ol className="steps">
          {STEPS.map((s) => (
            <li key={s.n} className="step card reveal">
              <span className={`step-n ${s.tint}`}>{s.n}</span>
              <h3>{s.title}</h3>
              <p className="muted">{s.text}</p>
              <p className="step-who">{s.who}</p>
            </li>
          ))}
        </ol>
      </section>

      <OnThisDevice />

      <footer className="foot small muted">
        Drafts are written by Gemma, an open-weight model. It only sees the facts you confirmed.
        You press publish.
      </footer>
    </>
  );
}
