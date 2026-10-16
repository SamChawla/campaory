export type Platform = "linkedin" | "instagram" | "whatsapp" | "x";

const LABEL: Record<Platform, { initial: string; name: string }> = {
  linkedin: { initial: "in", name: "LinkedIn" },
  instagram: { initial: "IG", name: "Instagram" },
  whatsapp: { initial: "W", name: "WhatsApp" },
  x: { initial: "X", name: "X" },
};

export function PlatformDot({ platform, className = "" }: { platform: Platform; className?: string }) {
  const { initial, name } = LABEL[platform];
  return (
    <span className={`dot dot-${platform} ${className}`} title={name}>
      <span aria-hidden="true">{initial}</span>
      <span className="sr-only">{name}</span>
    </span>
  );
}
