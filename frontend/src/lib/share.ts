// Copy and open (ADR-007). Copy first, then open the platform's web intent. Opening never
// changes a post's status: only "Mark published" does (BR05).
import { copyText } from "./clipboard";
import type { Platform } from "./types";

export const PLATFORM_NAME: Record<Platform, string> = {
  linkedin: "LinkedIn",
  instagram: "Instagram",
  whatsapp: "WhatsApp",
  x: "X",
};

/** The URL to open for a platform, or null when there is no web composer (Instagram). */
export function intentUrl(platform: Platform, text: string, url?: string | null): string | null {
  switch (platform) {
    case "x":
      return `https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}`;
    case "whatsapp":
      return `https://wa.me/?text=${encodeURIComponent(text)}`;
    case "linkedin":
      return url
        ? `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(url)}`
        : "https://www.linkedin.com/feed/";
    case "instagram":
      return null;
  }
}

export interface ShareResult {
  copied: boolean;
  opened: boolean;
  /** Set when a URL exists but the popup was blocked: show it as a link. */
  blockedUrl: string | null;
  message: string;
}

export async function copyFor(platform: Platform, text: string): Promise<ShareResult> {
  const copied = await copyText(text);
  const name = PLATFORM_NAME[platform];
  let message = copied ? `Copied for ${name}` : "Could not copy. Select the text and copy it yourself.";
  if (copied && platform === "instagram") message += ". Paste into the Instagram app.";
  return { copied, opened: false, blockedUrl: null, message };
}

export async function openPlatform(platform: Platform, text: string, url?: string | null): Promise<ShareResult> {
  const result = await copyFor(platform, text);
  const target = intentUrl(platform, text, url);
  if (!target) return result;
  // Not passing "noopener" as a feature: it makes window.open return null even on success,
  // which would hide a blocked popup. We cut the opener link by hand instead.
  let win: Window | null = null;
  try {
    win = window.open(target, "_blank");
  } catch {
    win = null;
  }
  if (!win) return { ...result, opened: false, blockedUrl: target };
  try {
    win.opener = null;
  } catch {
    // Cross-origin windows may refuse the assignment; the link is already open.
  }
  return { ...result, opened: true };
}
