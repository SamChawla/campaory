// Fact labels and grouping for display (LLD 3.1). The BR01 gate itself lives on the server;
// `displayBlockers` only tells the user which required facts still need their OK, and the
// server's 422 `blocked` answer always wins.
import type { Fact, FactKey, FactValue, Language, Person } from "./types";

export const FACT_LABEL: Record<FactKey, string> = {
  event_name: "Event name",
  event_type: "Event type",
  short_description: "Short description",
  start_date: "Start date",
  end_date: "End date",
  start_time: "Start time",
  end_time: "End time",
  timezone: "Timezone",
  venue: "Venue",
  address: "Address",
  city: "City",
  event_mode: "Event mode",
  registration_url: "Registration link",
  registration_status: "Registration status",
  capacity: "Capacity",
  registration_deadline: "Registration closes",
  audience: "Audience",
  speakers: "Speakers",
  judges: "Judges",
  mentors: "Mentors",
  partners: "Partners",
  hashtags: "Hashtags",
  handles: "Handles",
  language: "Language",
};

export const GATE_KEYS: FactKey[] = ["event_name", "start_date", "timezone", "audience", "language", "registration_url"];

export const FACT_ORDER: FactKey[] = [
  "event_name",
  "start_date",
  "timezone",
  "audience",
  "language",
  "registration_url",
  "event_mode",
  "event_type",
  "short_description",
  "end_date",
  "start_time",
  "end_time",
  "venue",
  "address",
  "city",
  "registration_status",
  "capacity",
  "registration_deadline",
  "speakers",
  "judges",
  "mentors",
  "partners",
  "hashtags",
  "handles",
];

export const PEOPLE_KEYS: FactKey[] = ["speakers", "judges", "mentors", "partners"];
export const LIST_KEYS: FactKey[] = [...PEOPLE_KEYS, "hashtags", "handles"];

export const LANGUAGE_LABEL: Record<Language, string> = { en: "English", hi: "Hindi", hinglish: "Hinglish" };

export const MODE_LABEL: Record<string, string> = { offline: "In person", online: "Online", hybrid: "Hybrid" };

export const FACT_HINT: Partial<Record<FactKey, string>> = {
  start_date: "Use the form YYYY-MM-DD, for example 2026-10-24.",
  end_date: "Use the form YYYY-MM-DD.",
  registration_deadline: "Use the form YYYY-MM-DD.",
  start_time: "24-hour time, for example 10:00.",
  end_time: "24-hour time, for example 17:30.",
  timezone: "A timezone name, for example Asia/Kolkata.",
  speakers: "One per line: name, role.",
  judges: "One per line: name, role.",
  mentors: "One per line: name, role.",
  partners: "One per line: name, role.",
  hashtags: "One per line.",
  handles: "One per line.",
};

export function isFilled(value: FactValue): boolean {
  return typeof value === "string" ? value.trim().length > 0 : value.length > 0;
}

export function factText(fact: Pick<Fact, "key" | "value">): string {
  const v = fact.value;
  if (fact.key === "language" && typeof v === "string") return LANGUAGE_LABEL[v as Language] ?? v;
  if (fact.key === "event_mode" && typeof v === "string") return MODE_LABEL[v] ?? v;
  if (typeof v === "string") return v;
  return (v as (Person | string)[])
    .map((p) => (typeof p === "string" ? p : p.role ? `${p.name}, ${p.role}` : p.name))
    .join("\n");
}

export function parseFactInput(key: FactKey, input: string): FactValue {
  if (!LIST_KEYS.includes(key)) return input.trim();
  const lines = input
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);
  if (!PEOPLE_KEYS.includes(key)) return lines;
  return lines.map((line) => {
    const [name, ...rest] = line.split(",");
    return { name: name.trim(), role: rest.join(",").trim() };
  });
}

export function sameValue(a: FactValue, b: FactValue): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}

export function factByKey(facts: Fact[], key: FactKey): Fact | undefined {
  return facts.find((f) => f.key === key && f.status !== "superseded");
}

export function confirmedFacts(facts: Fact[]): Fact[] {
  return facts.filter((f) => f.status === "confirmed");
}

export function displayBlockers(facts: Fact[]): FactKey[] {
  return GATE_KEYS.filter((key) => {
    const f = factByKey(facts, key);
    if (!f || f.status !== "confirmed") return true;
    if (key === "registration_url" && f.not_applicable) return false;
    return !isFilled(f.value);
  });
}

export function factValue(facts: Fact[], key: FactKey): string {
  const f = factByKey(facts, key);
  return f && typeof f.value === "string" ? f.value : "";
}
