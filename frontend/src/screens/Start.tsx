import { Link } from "react-router-dom";
import { PlatformDot, type Platform } from "../components/PlatformDot";

const PLATFORMS: Platform[] = ["linkedin", "instagram", "whatsapp", "x"];

export function Start() {
  return (
    <section className="hero">
      <div className="hero-dots" aria-hidden="true">
        {PLATFORMS.map((p) => (
          <PlatformDot key={p} platform={p} className="float" />
        ))}
      </div>
      <h1 className="display rise">
        Event promotion, minus the <span className="underline">copy-paste</span>
      </h1>
      <p className="lead rise d1">
        Give Campaory a page link or your event details. You confirm the facts once, it drafts the
        LinkedIn, Instagram, WhatsApp and X posts from them, and each post waits for your OK.
      </p>
      <p className="rise d2">
        <Link id="start" to="/#start" className="btn btn-highlight">
          Try a sample event
        </Link>
      </p>
      <p className="small muted rise d3">Public pages only. Saved on this device. No account.</p>
    </section>
  );
}
