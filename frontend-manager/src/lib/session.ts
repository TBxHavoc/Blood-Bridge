import type { Role, User } from "./types";

/** A display label for the sidebar brand. The API exposes only an opaque
 *  `affiliated_org_id`, so we derive a short code from the seeded username. */
export function orgLabel(user: User): string {
  const match = user.username.match(/^(?:hospital|bank)_(.+)$/i);
  if (match) return match[1].toUpperCase();
  if (user.role === "admin") return "BloodBridge";
  if (user.role === "auditor") return "Audit";
  return user.username;
}

export function roleLabel(role: Role): string {
  switch (role) {
    case "hospital_user":
      return "Hospital";
    case "bloodbank_user":
      return "Blood bank";
    case "admin":
      return "Administrator";
    case "auditor":
      return "Auditor";
    default:
      return role;
  }
}

export function greetingFor(date: Date): string {
  const h = date.getHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

export function datelineFor(date: Date, org: string): string {
  const day = date.toLocaleDateString("en-US", { weekday: "long" });
  const md = date.toLocaleDateString("en-US", { month: "long", day: "numeric" });
  const time = date.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
  return `${day}, ${md} · ${time} / ${org}`;
}
