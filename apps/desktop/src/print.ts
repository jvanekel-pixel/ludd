/** Print a 1:1 template (with centre lines for hooping) and a thread list for the open design. */

import { Kind, type Design, type Hoop } from "./design/types";
import { selectHoop, selectMachine, useStore } from "./store";

const MARGIN_MM = 12;
const CROSS_EXTRA_MM = 8;

const esc = (s: string) => s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);

/** One SVG path per color block, in mm. Jumps and trims lift the pen. */
export function stitchPaths(d: Design): { color: string; d: string }[] {
  const { x, y, kind } = d.records;
  return d.blocks.map((b) => {
    let path = "";
    let down = false;
    for (let i = b.start; i < b.end; i++) {
      if (kind[i] !== Kind.Stitch) {
        down = false;
        continue;
      }
      path += `${down ? "L" : "M"}${x[i].toFixed(2)} ${y[i].toFixed(2)}`;
      down = true;
    }
    return { color: d.threads[b.thread]?.color ?? "#808080", d: path };
  });
}

/** Stitches in each color block, for the thread list. */
export function blockStitchCounts(d: Design): number[] {
  return d.blocks.map((b) => {
    let n = 0;
    for (let i = b.start; i < b.end; i++) if (d.records.kind[i] === Kind.Stitch) n++;
    return n;
  });
}

export function templateSvg(d: Design, hoop: Hoop | null): string {
  const [x0, y0, x1, y1] = d.info.bounds_mm;
  const cx = (x0 + x1) / 2;
  const cy = (y0 + y1) / 2;
  const half = (v: number) => v / 2;
  let left = x0 - MARGIN_MM;
  let top = y0 - MARGIN_MM;
  let right = x1 + MARGIN_MM;
  let bottom = y1 + MARGIN_MM;
  if (hoop) {
    left = Math.min(left, cx - half(hoop.width_mm) - 4);
    right = Math.max(right, cx + half(hoop.width_mm) + 4);
    top = Math.min(top, cy - half(hoop.height_mm) - 4);
    bottom = Math.max(bottom, cy + half(hoop.height_mm) + 4);
  }
  const w = right - left;
  const h = bottom - top;
  const paths = stitchPaths(d)
    .map((p) => `<path d="${p.d}" stroke="${p.color}" />`)
    .join("");
  const hoopRect = hoop
    ? `<rect class="hoop" x="${cx - half(hoop.width_mm)}" y="${cy - half(hoop.height_mm)}" width="${hoop.width_mm}" height="${hoop.height_mm}" />`
    : "";
  const cross =
    `<line class="cross" x1="${x0 - CROSS_EXTRA_MM}" y1="${cy}" x2="${x1 + CROSS_EXTRA_MM}" y2="${cy}" />` +
    `<line class="cross" x1="${cx}" y1="${y0 - CROSS_EXTRA_MM}" x2="${cx}" y2="${y1 + CROSS_EXTRA_MM}" />`;
  return (
    `<svg xmlns="http://www.w3.org/2000/svg" width="${w}mm" height="${h}mm" viewBox="${left} ${top} ${w} ${h}">` +
    `<style>path{fill:none;stroke-width:.35;stroke-linecap:round;stroke-linejoin:round}` +
    `.hoop{fill:none;stroke:#888;stroke-width:.3;stroke-dasharray:2 1.5}.cross{stroke:#d33;stroke-width:.25}</style>` +
    hoopRect +
    paths +
    cross +
    `</svg>`
  );
}

function checkBars(): string {
  // 1 inch and 25 mm bars: measure them to confirm the page printed at 100%.
  return (
    `<svg xmlns="http://www.w3.org/2000/svg" width="80mm" height="12mm" viewBox="0 0 80 12">` +
    `<g stroke="#000" stroke-width=".3"><line x1="0" y1="3" x2="25.4" y2="3"/><line x1="0" y1="1" x2="0" y2="5"/><line x1="25.4" y1="1" x2="25.4" y2="5"/>` +
    `<line x1="40" y1="3" x2="65" y2="3"/><line x1="40" y1="1" x2="40" y2="5"/><line x1="65" y1="1" x2="65" y2="5"/></g>` +
    `<g font-size="3" font-family="sans-serif"><text x="0" y="10">1 inch</text><text x="40" y="10">25 mm</text></g></svg>`
  );
}

/** `fabric`: e.g. "T-shirt knit — Stabilizer: …", printed on the thread list. */
export function printHtml(d: Design, hoop: Hoop | null, machineName: string | null, fabric: string | null = null): string {
  const { info } = d;
  const inch = (mm: number) => (mm / 25.4).toFixed(2);
  const counts = blockStitchCounts(d);
  const rows = d.blocks
    .map((b, i) => {
      const t = d.threads[b.thread];
      const brand = [t.brand, t.catalog].filter(Boolean).join(" ");
      return `<tr><td>${i + 1}</td><td><span class="sw" style="background:${t.color}"></span></td><td>${esc(t.name || t.color)}</td><td>${esc(brand)}</td><td class="n">${counts[i].toLocaleString()}</td><td class="tick"></td></tr>`;
    })
    .join("");
  const date = new Date().toLocaleDateString();
  return `<!doctype html><html><head><meta charset="utf-8"><title>${esc(d.name)}</title><style>
    @page { margin: 12mm; }
    body { font: 11pt system-ui, sans-serif; color: #111; margin: 0; }
    h1 { font-size: 15pt; margin: 0 0 2mm; }
    .meta { color: #555; margin: 0 0 4mm; }
    .page { page-break-after: always; }
    .page:last-child { page-break-after: auto; }
    .note { font-size: 9pt; color: #555; margin: 3mm 0; }
    table { border-collapse: collapse; width: 100%; }
    th, td { text-align: left; padding: 1.5mm 2mm; border-bottom: .2mm solid #ccc; }
    th { font-size: 9pt; color: #555; }
    .n { text-align: right; font-variant-numeric: tabular-nums; }
    .tick { width: 8mm; border: .2mm solid #999; }
    .sw { display: inline-block; width: 6mm; height: 6mm; border: .2mm solid #0003; border-radius: 1mm; vertical-align: middle;
          -webkit-print-color-adjust: exact; print-color-adjust: exact; }
    svg { display: block; }
  </style></head><body>
  <section class="page">
    <h1>${esc(d.name)} — template</h1>
    <p class="meta">${info.width_mm.toFixed(1)} × ${info.height_mm.toFixed(1)} mm (${inch(info.width_mm)} × ${inch(info.height_mm)} in)${
      hoop ? ` · ${esc(hoop.name)} hoop` : ""
    }${machineName ? ` · ${esc(machineName)}` : ""}</p>
    ${templateSvg(d, hoop)}
    <p class="note">Red lines cross at the design centre: line them up with the marks on your fabric. Print at 100% (“Actual size”). Check the bars below measure correctly:</p>
    ${checkBars()}
  </section>
  <section class="page">
    <h1>${esc(d.name)} — thread list</h1>
    <p class="meta">${info.stitches.toLocaleString()} stitches · ${info.colors} colors · ${info.stops} stops · ${info.trims} trims · ${date}</p>
    <table><thead><tr><th>#</th><th></th><th>Thread</th><th>Brand / number</th><th class="n">Stitches</th><th>Done</th></tr></thead>
    <tbody>${rows}</tbody></table>
    ${fabric ? `<p class="note">${esc(fabric)}</p>` : ""}
  </section>
  </body></html>`;
}

/** Open the system print dialog for the open design. */
export function printDesign() {
  const s = useStore.getState();
  if (!s.design) return;
  const fabric = s.checks?.fabric;
  const html = printHtml(s.design, s.showHoop ? selectHoop(s) : null, selectMachine(s)?.name ?? null, fabric ? `${fabric.name}. ${fabric.advice}` : null);
  const frame = document.createElement("iframe");
  frame.setAttribute("aria-hidden", "true");
  frame.style.cssText = "position:fixed;right:0;bottom:0;width:0;height:0;border:0;visibility:hidden";
  frame.srcdoc = html;
  frame.onload = () => {
    frame.contentWindow?.focus();
    frame.contentWindow?.print();
    // Give the print dialog time to take its snapshot before removing the frame.
    setTimeout(() => frame.remove(), 60_000);
  };
  document.body.appendChild(frame);
}
