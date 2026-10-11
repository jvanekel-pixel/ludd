/**
 * The LUDD mark: a hammer and a needle crossed in a hoop, with a loose thread.
 * Colors come from the theme (--logo-ink, --logo-gap, --logo-thread), so it follows light and dark mode.
 */
export function LuddMark({ size = 28, title = "LUDD" }: { size?: number; title?: string }) {
  const ink = "var(--logo-ink)";
  const gap = "var(--logo-gap)";
  const thread = "M124 58 L142 74.5 C162 92 188 82 186 58 C184 38 166 34 172 16";
  return (
    <svg className="ludd-mark" viewBox="0 0 200 200" width={size} height={size} role="img" aria-label={title}>
      <circle cx="100" cy="104" r="78" fill="none" stroke={ink} strokeWidth="9" />
      <circle cx="100" cy="104" r="68" fill="none" stroke={ink} strokeWidth="2.5" />
      <rect x="97.5" y="16" width="5" height="18" fill={gap} />
      <rect x="85" y="12" width="12" height="20" rx="2" fill={ink} />
      <rect x="103" y="12" width="12" height="20" rx="2" fill={ink} />
      <rect x="78" y="18" width="44" height="7" rx="3.5" fill={ink} />
      <g transform="rotate(-42 100 104)">
        <rect x="95.5" y="66" width="9" height="100" rx="4.5" fill={ink} />
        <rect x="70" y="46" width="60" height="24" rx="3" fill={ink} />
      </g>
      <g transform="rotate(42 100 104)">
        <path
          d="M100 168 L95.5 74 L95.5 48 Q95.5 39 100 39 Q104.5 39 104.5 48 L104.5 74 Z"
          fill={ink}
          stroke={gap}
          strokeWidth="6"
          strokeLinejoin="round"
          paintOrder="stroke"
        />
        <rect x="98.2" y="46" width="3.6" height="16" rx="1.8" fill={gap} />
      </g>
      <path d={thread} fill="none" stroke={gap} strokeWidth="10" strokeLinecap="round" strokeLinejoin="round" />
      <path d={thread} fill="none" stroke="var(--logo-thread)" strokeWidth="4.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** Mark plus the LUDD wordmark. */
export function LuddLogo({ size = 28 }: { size?: number }) {
  return (
    <span className="ludd-logo" style={{ fontSize: size * 0.82 }}>
      <LuddMark size={size} title="" />
      <span className="ludd-word">LUDD</span>
    </span>
  );
}
