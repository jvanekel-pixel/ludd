/**
 * Tool icons: simple line drawings on a 24 px grid, drawn in the current text colour so they
 * follow light and dark mode and the selected-tool highlight.
 */
import type { ReactNode } from "react";

function Svg({ children, title }: { children: ReactNode; title?: string }) {
  return (
    <svg className="tool-icon" viewBox="0 0 24 24" width={24} height={24} fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" aria-hidden={!title} role={title ? "img" : undefined}>
      {title && <title>{title}</title>}
      {children}
    </svg>
  );
}

/** Select: an arrow pointer. */
export const SelectIcon = () => (
  <Svg>
    <path d="M5 3.5 L5 18.5 L9.2 14.6 L12 20.5 L14.6 19.3 L11.9 13.5 L17.5 13.2 Z" fill="currentColor" fillOpacity={0.12} />
  </Svg>
);

/** Line: a running stitch along a gentle curve, with needle points. */
export const LineIcon = () => (
  <Svg>
    <path d="M3 16 C 7 6, 11 6, 13 11 S 19 17, 21 7" strokeDasharray="3.2 2.2" />
    <circle cx="3" cy="16" r="1.1" fill="currentColor" stroke="none" />
    <circle cx="21" cy="7" r="1.1" fill="currentColor" stroke="none" />
  </Svg>
);

/** Satin: a column filled with close zigzag stitches. */
export const SatinIcon = () => (
  <Svg>
    <path d="M6 4 L10 4 L18 20 L14 20 Z" strokeWidth={1.3} />
    <path d="M6.6 5.2 L10.1 5 M7.4 6.9 L10.9 6.6 M8.2 8.6 L11.7 8.3 M9 10.3 L12.6 10 M9.8 12 L13.4 11.7 M10.6 13.7 L14.2 13.4 M11.4 15.4 L15 15.1 M12.2 17.1 L15.9 16.8 M13 18.8 L16.7 18.5" strokeWidth={1.1} />
  </Svg>
);

/** Fill: a rounded shape hatched with angled rows. */
export const FillIcon = () => (
  <Svg>
    <defs>
      <clipPath id="ludd-fill-clip">
        <path d="M5 8 C 5 4, 11 3, 14 5 C 18 7, 21 10, 19 15 C 17 20, 10 21, 7 18 C 4 15, 5 11, 5 8 Z" />
      </clipPath>
    </defs>
    <path d="M5 8 C 5 4, 11 3, 14 5 C 18 7, 21 10, 19 15 C 17 20, 10 21, 7 18 C 4 15, 5 11, 5 8 Z" />
    <g clipPath="url(#ludd-fill-clip)" strokeWidth={1.1}>
      <path d="M0 9 L12 -3 M0 13 L16 -3 M0 17 L20 -3 M0 21 L24 -3 M2 23 L26 -1 M6 23 L26 3 M10 23 L26 7 M14 23 L26 11" />
    </g>
  </Svg>
);

/** Text: a capital A with a baseline. */
export const TextIcon = () => (
  <Svg>
    <path d="M5 19 L11 4.5 L13 4.5 L19 19" />
    <path d="M7.8 13.5 L16.2 13.5" />
    <path d="M3.5 21 L20.5 21" strokeWidth={1.2} />
  </Svg>
);

/** Shapes: a square and a circle overlapping. */
export const ShapesIcon = () => (
  <Svg>
    <rect x="3.5" y="3.5" width="10" height="10" rx="1.2" />
    <circle cx="15" cy="15" r="5.5" fill="currentColor" fillOpacity={0.12} />
  </Svg>
);

/** Picture: a framed landscape. */
export const PictureIcon = () => (
  <Svg>
    <rect x="3" y="4.5" width="18" height="15" rx="2" />
    <circle cx="9" cy="9.5" r="1.7" />
    <path d="M3.5 17.5 L9 12.5 L12.5 15.5 L15.5 12.5 L20.5 17" />
  </Svg>
);
