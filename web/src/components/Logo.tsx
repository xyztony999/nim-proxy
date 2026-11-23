interface LogoProps {
  size?: number;
  title?: string;
}

// NIM Proxy mark: client (white node) -> proxy (green hexagon) -> NIM (green node).
export default function Logo({ size = 28, title = "NIM Proxy" }: LogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      role="img"
      aria-label={title}
      style={{ display: "block", borderRadius: size * 0.22 }}
    >
      <rect x="2" y="2" width="60" height="60" rx="14" fill="#0f172a" />
      <line x1="14" y1="32" x2="27" y2="32" stroke="#ffffff" strokeWidth="3" />
      <line x1="37" y1="32" x2="50" y2="32" stroke="#ffffff" strokeWidth="3" />
      <circle cx="14" cy="32" r="5" fill="#ffffff" />
      <circle cx="50" cy="32" r="5" fill="#76b900" />
      <polygon points="32,23 40,27.5 40,36.5 32,41 24,36.5 24,27.5" fill="#76b900" />
    </svg>
  );
}
