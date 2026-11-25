import { Fragment, useEffect, useRef, useState } from "react";
import {
  command,
  commit,
  currentLayout,
  deleteColorBlock,
  itemLabel,
  setObjectThread,
  setPicture,
  setItemPinned,
  pickItem,
  recolorBlocks,
  recolorSources,
  renameThing,
  setItemsThread,
  moveItemTo,
  reorderItem,
  setText,
} from "../actions";
import { applyColorway, deleteColorway, saveColorway, toggleTravelUnder } from "../features";
import { GARMENTS } from "../design/garments";
import type { Garment } from "../store";
import { formatShortcut } from "../commands";
import { heldCount, holdEscape } from "../escape";
import { hasRecolors, scaleImageByMeasure } from "../design/layout";
import { hoopFit } from "../design/machine";
import { estimate, fmtMinutes, fmtThread } from "../design/estimate";
import { blockAt, visibleRecords } from "../design/player";
import { isObject, isText, type FileItem, type Layout, type LayoutItem, type RefImage, type Thread } from "../design/types";
import { selectHoop, selectImages, selectLayout, selectMachine, useStore } from "../store";
import { Section, Sub, Row, type SelKind } from "./Accordion";
import { Menu } from "./Menu";
import { itemMenu, openContextMenu, pictureMenu } from "../contextMenu";
import { AdvisorPanel } from "./AIPanels";
import { Cmd, fmtLen, fromUnits, NumberField, toUnits } from "./controls";
import { FileSections } from "./FilePanel";
import { KIND_TITLE, ObjectSections } from "./ObjectPanel";
import { Checks, FabricPicker } from "./QualityPanel";
import { SelectedText } from "./TextPanel";
import { MatchAllDialog, ThreadPicker } from "./ThreadDialogs";

// Used elsewhere from here before the panel was split.
export { fmtLen } from "./controls";
export { objectSummary } from "./ObjectPanel";

const FIT_TEXT = {
  fits: (hoop: string) => `Fits the ${hoop} hoop`,
  rotate: (hoop: string) => `Rotate 90° to fit the ${hoop} hoop`,
  too_big: (hoop: string) => `Too big for the ${hoop} hoop`,
};

/** Tabbing onto the slider (or letting go without moving it) changes nothing, so it's no undo step. */
function setOpacity(img: RefImage, opacity: number) {
  if (Math.abs(opacity - img.opacity) > 1e-9) setPicture(img.id, { opacity });
}

/** The selected picture's settings (see-through, real size), shown under its row in Pictures. */
function PictureSettings({ img }: { img: RefImage }) {
  const units = useStore((s) => s.units);
  const measure = useStore((s) => s.measure);
  const setMeasure = useStore((s) => s.setMeasure);
  const measuring = measure?.imageId === img.id;
  const pts = measuring ? measure.points : [];
  const measured = pts.length === 2 ? Math.hypot(pts[1][0] - pts[0][0], pts[1][1] - pts[0][1]) : 0;
  return (
    <div className="picture-settings">
      <label className="slider">
        See-through <strong>{Math.round((1 - img.opacity) * 100)}%</strong>
        <input
          type="range"
          min={0.1}
          max={1}
          step={0.05}
          defaultValue={img.opacity}
          key={`${img.id}-${img.opacity}`}
          onPointerUp={(e) => setOpacity(img, Number((e.target as HTMLInputElement).value))}
          onKeyUp={(e) => setOpacity(img, Number((e.target as HTMLInputElement).value))}
        />
      </label>
      {!measuring ? (
        <button className="wide" onClick={() => setMeasure({ imageId: img.id, points: [] })} title="Click two points on the picture whose real distance you know">
          📏 Set real size…
        </button>
      ) : (
        <div className="measure">
          {pts.length < 2 ? (
            <p className="hint">Click {pts.length === 0 ? "the first" : "the second"} point on the picture.</p>
          ) : (
            <NumberField
              label="Real distance between the points"
              value={toUnits(measured, units)}
              suffix={units}
              onCommit={(v) => {
                setPicture(img.id, scaleImageByMeasure(img, measured, fromUnits(v, units)));
                setMeasure(null);
              }}
            />
          )}
          <button className="link" onClick={() => setMeasure(null)}>
            Cancel
          </button>
        </div>
      )}
      <p className="hint">
        {img.locked
          ? "Pinned: it can't move, and clicks go through it so you can draw over it."
          : "Drag to move; drag a corner to resize, or a side to stretch it. Pin it (📌) once it's where you want it."}{" "}
        Saved inside your project.
      </p>
    </div>
  );
}

/** One color stop as the list shows it: which of the design's colors (in sewing order), its
 *  thread, and the item's own part of it (what changing it here changes). */
type ColorStop = { block: number; thread: Thread; was: Thread | null; sources: { item: number; block: number }[] };

/** What the thread picker is choosing for. */
type Picking =
  | { kind: "item"; id: string }
  | { kind: "stops"; stops: ColorStop[]; title: string }
  | { kind: "palette"; blocks: number[]; thread: Thread }
  | { kind: "knockdown"; thread: Thread };

const threadKey = (t: Thread) => [t.color.toLowerCase(), t.name, t.catalog, t.brand].join("|");

/** The design in sewing order, with each step's colors: drag to reorder, click a swatch or ✎ to
 *  change a thread, and the Palette (the threads in use) to change a thread everywhere at once.
 *  (It used to be two sections, Threads and Sewing order.) */
function OrderSection({ sel }: { sel: SelKind }) {
  const layout = useStore(selectLayout);
  const design = useStore((s) => s.design);
  const selectedId = useStore((s) => s.selectedId);
  const extraIds = useStore((s) => s.extraIds);
  const setSelection = useStore((s) => s.setSelection);
  const engine = useStore((s) => s.engine);
  const playhead = useStore((s) => s.playhead);
  const stitchIdx = useStore((s) => s.stitchIdx);
  const hasMine = useStore((s) => s.charts.some((c) => c.mine && c.count > 0));
  const list = useRef<HTMLOListElement>(null);
  const clickMods = useRef(false);
  const [picking, setPicking] = useState<Picking | null>(null);
  const [matching, setMatching] = useState(false);
  /** A row being dragged to a new place in the order, and where it would land. */
  const [drag, setDrag] = useState<{ id: string; to: number } | null>(null);
  /** Puts a dragged row back: the panel going away, or the row's item gone (New, Open, an undo). */
  const putBackDrag = useRef<(() => void) | null>(null);
  useEffect(() => () => putBackDrag.current?.(), []);
  useEffect(() => {
    if (drag && !layout?.items.some((it) => it.id === drag.id)) putBackDrag.current?.();
  }, [drag, layout]);
  if (!layout || (!layout.items.length && !design)) return null;

  const selected = new Set([selectedId, ...extraIds].filter((x): x is string => !!x));
  const sewing = !!design && playhead > 0 && playhead < stitchIdx.length;
  const currentBlock = sewing && design ? blockAt(design, visibleRecords(stitchIdx, playhead, design.records.kind.length) - 1) : -1;

  /** Each item's colors, in sewing order. */
  const stopsOf = (i: number): ColorStop[] =>
    (design?.blocks ?? []).flatMap((b, k) => {
      const mine = (b.sources ?? []).filter((src) => src.item === i);
      if (!mine.length || !design) return [];
      const t = design.threads[b.thread];
      const was = b.original && b.original.color.toLowerCase() !== t.color.toLowerCase() ? b.original : null;
      return [{ block: k, thread: t, was, sources: mine }];
    });
  /** Stitching LUDD adds (basting box, knockdown): sewn first, part of no item. */
  const added = (design?.blocks ?? []).flatMap((b, k) => {
    const what = design ? addedStitching(layout, b, k) : null;
    return what && design ? [{ block: k, what, thread: design.threads[b.thread] }] : [];
  });
  /** The palette: every thread in use (once each), with the colors that use it. */
  const palette: { thread: Thread; blocks: number[] }[] = [];
  (design?.blocks ?? []).forEach((b, k) => {
    if (!design || !b.sources?.length) return;
    const t = design.threads[b.thread];
    const hit = palette.find((x) => threadKey(x.thread) === threadKey(t));
    if (hit) hit.blocks.push(k);
    else palette.push({ thread: t, blocks: [k] });
  });

  /** Drag a row by its grip: the rows make room as you go; let go to sew it there. Esc puts it back. */
  const startDrag = (e: React.PointerEvent, id: string) => {
    if (e.button !== 0) return;
    e.preventDefault();
    const from = layout.items.findIndex((it) => it.id === id);
    let to = from;
    setDrag({ id, to });
    const panel = list.current?.closest<HTMLElement>(".info-panel");
    const move = (ev: PointerEvent) => {
      // No button down: the mouse came up where we didn't hear it, so the drag is over.
      if (ev.buttons === 0) return drop();
      const others = [...(list.current?.querySelectorAll<HTMLElement>("li[data-row]") ?? [])].filter((r) => r.dataset.row !== id);
      to = others.filter((r) => {
        const b = r.getBoundingClientRect();
        return b.top + b.height / 2 < ev.clientY;
      }).length;
      setDrag({ id, to });
      // Near the top or bottom of the panel: scroll, so a long list can be reached.
      if (panel) {
        const b = panel.getBoundingClientRect();
        if (ev.clientY < b.top + 32) panel.scrollTop -= 14;
        else if (ev.clientY > b.bottom - 32) panel.scrollTop += 14;
      }
    };
    const end = (keep: boolean) => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", drop);
      window.removeEventListener("pointercancel", putBack);
      window.removeEventListener("blur", putBack);
      release();
      putBackDrag.current = null;
      setDrag(null);
      if (keep && to !== from) moveItemTo(id, to);
    };
    const drop = () => end(true);
    const putBack = () => end(false);
    const release = holdEscape(putBack);
    putBackDrag.current = putBack;
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", drop);
    window.addEventListener("pointercancel", putBack);
    window.addEventListener("blur", putBack);
  };
  /** The rows as shown: while dragging, the dragged one sits where it would land. */
  const shown = drag
    ? (() => {
        const rest = layout.items.filter((it) => it.id !== drag.id);
        rest.splice(drag.to, 0, layout.items.find((it) => it.id === drag.id)!);
        return rest;
      })()
    : layout.items;

  /** Select from the list without the list jumping: selecting opens that item's section above
   *  it, so scroll by as much as the row moved (and a double-click lands on the same row).
   *  Shift or Ctrl+click adds it to (or takes it from) the selection; a group is picked whole. */
  const selectInPlace = (id: string) => {
    const row = list.current?.querySelector<HTMLElement>(`[data-row="${id}"]`);
    const panel = row?.closest<HTMLElement>(".info-panel");
    const before = row?.getBoundingClientRect().top;
    if (clickMods.current) pickItem(id, true);
    else {
      const g = layout.items.find((it) => it.id === id)?.group;
      const members = g ? layout.items.filter((it) => it.group === g).map((it) => it.id) : [];
      setSelection(id, members.filter((m) => m !== id));
    }
    if (!row || !panel || before === undefined) return;
    // Hold the row still for a few frames while the panel settles.
    let frames = 8;
    const hold = () => {
      panel.scrollTop += row.getBoundingClientRect().top - before;
      if (--frames > 0) requestAnimationFrame(hold);
    };
    requestAnimationFrame(hold);
  };

  /** Change an item's thread: with several selected (and this one among them), all of them. */
  const pickFor = (it: LayoutItem, i: number) => {
    const stops = stopsOf(i);
    if (isObject(it) || isText(it) || selected.size > 1) return setPicking({ kind: "item", id: it.id });
    if (stops.length) setPicking({ kind: "stops", stops, title: itemLabel(it, i) });
  };
  const itemThread = (it: LayoutItem, i: number): Thread | null => stopsOf(i)[0]?.thread ?? (isObject(it) || isText(it) ? (it.threads?.[0] ?? it.thread) : null);

  const pickerCurrent = (): Thread | undefined => {
    if (!picking) return undefined;
    if (picking.kind === "item") {
      const i = layout.items.findIndex((it) => it.id === picking.id);
      return i >= 0 ? (itemThread(layout.items[i], i) ?? undefined) : undefined;
    }
    if (picking.kind === "stops") return picking.stops[0].thread;
    return picking.thread;
  };
  const onPicked = (t: Thread) => {
    if (!picking) return;
    if (picking.kind === "item") {
      const it = layout.items.find((x) => x.id === picking.id);
      if (!it) return;
      if (selected.size > 1 && selected.has(it.id)) setItemsThread([...selected], t);
      else if (isObject(it)) setObjectThread(it.id, t);
      else if (isText(it)) setText(it.id, { thread: t, threads: [] });
      else recolorSources(stopsOf(layout.items.indexOf(it)).flatMap((c) => c.sources), t);
    } else if (picking.kind === "stops") recolorSources(picking.stops.flatMap((c) => c.sources), t);
    else if (picking.kind === "palette") recolorBlocks(picking.blocks.map((block) => ({ block, thread: t })));
    else {
      const l = currentLayout();
      if (l?.knockdown) void commit({ ...l, knockdown: { ...l.knockdown, thread: t } });
    }
  };

  const colorOptions = [
    { id: "colors.merge", checked: layout.merge_colors },
    { id: "colors.sort", checked: layout.color_sort },
    ...(hasRecolors(layout) ? [{ id: "colors.reset" }] : []),
    { id: "threads.charts" },
  ];

  return (
    <Section
      id="order"
      sel={sel}
      shared
      defaultOpen
      title="Order & colors"
      badge={layout.items.length || undefined}
      summary={
        <span className="swatch-strip" aria-hidden>
          {palette.slice(0, 12).map((x, k) => (
            <span key={k} style={{ background: x.thread.color }} />
          ))}
        </span>
      }
      actions={
        <>
          <button onClick={() => setMatching(true)} disabled={!engine || !design} title="Find the closest of your threads (or a brand's) for every color">
            {hasMine ? "Match to mine…" : "Match…"}
          </button>
          <Menu label="Color options" items={colorOptions} />
        </>
      }
    >
      {palette.length > 0 && (
        <div className="palette" role="group" aria-label="Palette">
          <span className="palette-label">Palette</span>
          {palette.map((x) => (
            <button
              key={threadKey(x.thread)}
              className="palette-swatch"
              style={{ background: x.thread.color }}
              disabled={!engine}
              title={`${[x.thread.brand, x.thread.catalog, x.thread.name].filter(Boolean).join(" ") || x.thread.color} · used ${x.blocks.length}× · click to change it everywhere`}
              aria-label={`Change ${x.thread.name || x.thread.color} everywhere`}
              onClick={() => setPicking({ kind: "palette", blocks: x.blocks, thread: x.thread })}
            />
          ))}
        </div>
      )}
      {layout.merge_colors || layout.color_sort ? (
        <p className="hint order-note">{layout.color_sort ? "Sort colors is on: the machine sews same colors together, so its order can differ from this list." : "Same colors next to each other are sewn as one."}</p>
      ) : null}
      <ColorSets />
      <ol className={`design-list${drag ? " reordering" : ""}`} ref={list}>
        {added.map((a) => (
          <li key={`added-${a.block}`} className={`added-row${a.block === currentBlock ? " sewing" : ""}`}>
            <span className="grip" aria-hidden />
            <span className="swatch small" style={{ background: a.thread.color }} />
            <span className="name">
              {a.what === "basting" ? "Basting box" : "Knockdown"}
              <small>{a.what === "basting" ? " · sewn first; remove it afterwards" : " · use a thread that matches the fabric"}</small>
            </span>
            {a.what === "knockdown" && (
              <button className="rename-btn" aria-label="Change the knockdown thread" title="Change thread" disabled={!engine} onClick={() => setPicking({ kind: "knockdown", thread: a.thread })}>
                ✎
              </button>
            )}
          </li>
        ))}
        {shown.map((it, k) => {
          const i = layout.items.indexOf(it);
          const stops = stopsOf(i);
          const t = itemThread(it, i);
          const several = !isObject(it) && !isText(it) && stops.length > 1;
          const isSel = selected.has(it.id);
          const sewingHere = stops.some((c) => c.block === currentBlock);
          const name = design?.items?.[i]?.name ?? itemLabel(it, i);
          return (
            <Fragment key={it.id}>
              <li
                data-row={it.id}
                className={[isSel ? "current" : "", sewingHere ? "sewing" : "", drag?.id === it.id ? "dragging" : ""].join(" ").trim() || undefined}
                onClickCapture={(e) => (clickMods.current = e.shiftKey || e.ctrlKey || e.metaKey)}
                onContextMenu={(e) => {
                  if ((e.target as Element).closest("input")) return; // renaming: the text's own menu
                  clickMods.current = false; // a right-click picks the row alone (not with an old Shift+click)
                  if (!isSel) selectInPlace(it.id);
                  const now = useStore.getState();
                  openContextMenu(e, itemMenu(it, now.extraIds.length > 0), now.extraIds.length ? `${now.extraIds.length + 1} selected` : name);
                }}
              >
                <span className="grip" onPointerDown={(e) => startDrag(e, it.id)} title="Drag up or down to change the sewing order" aria-hidden>
                  ⠿
                </span>
                <button
                  className="swatch small"
                  style={{ background: several ? `linear-gradient(90deg, ${stops.slice(0, 4).map((c) => c.thread.color).join(", ")})` : (t?.color ?? "transparent") }}
                  title={several ? `${stops.length} colors (listed below)` : t ? `${t.name || t.color}: click to change` : undefined}
                  aria-label={several ? `${stops.length} colors` : "Change thread"}
                  disabled={!engine || several || !t}
                  onClick={() => pickFor(it, i)}
                >
                  {isText(it) ? "A" : ""}
                </button>
                <RenameField id={it.id} className="name" prefix={`${k + 1}. `} name={name} onClick={() => selectInPlace(it.id)} />
                {it.group && <span className="group-tag" title="In a group: selects and moves with the others">▣</span>}
                <button
                  className="rename-btn"
                  aria-label="Change thread"
                  title={several ? "Change each color below" : isSel && selected.size > 1 ? `Change the thread of all ${selected.size} selected` : "Change this step's thread"}
                  disabled={!engine || several || !t}
                  onClick={() => pickFor(it, i)}
                >
                  ✎
                </button>
                <button
                  className={`pin${it.locked ? " on" : ""}`}
                  aria-pressed={!!it.locked}
                  aria-label={it.locked ? "Unpin" : "Pin in place"}
                  title={it.locked ? "Pinned: can't be dragged. Click to unpin." : "Pin in place, so it can't be moved by accident"}
                  onClick={() => setItemPinned(it.id, !it.locked)}
                >
                  📌
                </button>
                <button aria-label="Sew earlier" title="Sew earlier" disabled={i === 0} onClick={() => reorderItem(it.id, -1)}>
                  ↑
                </button>
                <button aria-label="Sew later" title="Sew later" disabled={i === layout.items.length - 1} onClick={() => reorderItem(it.id, 1)}>
                  ↓
                </button>
              </li>
              {several &&
                !drag &&
                stops.map((c) => {
                  const sub = [c.thread.brand, c.thread.catalog].filter(Boolean).join(" ");
                  const onlyMine = (design?.blocks[c.block].sources ?? []).every((src) => src.item === i);
                  return (
                    <li
                      key={`${it.id}-${c.block}`}
                      className={`color-row${c.block === currentBlock ? " sewing" : ""}${isSel ? " current" : ""}`}
                      onContextMenu={(e) =>
                        openContextMenu(
                          e,
                          [
                            { label: "Change this color…", run: () => setPicking({ kind: "stops", stops: [c], title: name }), enabled: !!engine },
                            ...(c.was ? [{ label: `Back to ${c.was.name || c.was.color}`, run: () => recolorSources(c.sources, null), enabled: !!engine }] : []),
                            { label: "Remove this color's stitches", run: () => deleteColorBlock(c.block), enabled: !!engine && onlyMine && (design?.blocks.length ?? 0) > 1, hint: "Ctrl+Z undoes it" },
                            "separator",
                            { label: hasMine ? "Match all to my threads…" : "Match all threads…", run: () => setMatching(true), enabled: !!engine },
                            ...colorOptions,
                          ],
                          `Color ${c.block + 1}: ${c.thread.name || c.thread.color}`,
                        )
                      }
                    >
                      <button className="swatch small" style={{ background: c.thread.color }} disabled={!engine} aria-label={`Change color ${c.block + 1}`} title="Click to change" onClick={() => setPicking({ kind: "stops", stops: [c], title: name })} />
                      <span className="num">{c.block + 1}</span>
                      <span className="tname">
                        {c.thread.name || c.thread.color}
                        {sub && <small>{sub}</small>}
                        {c.was && <small className="was">was {c.was.name || c.was.color}</small>}
                      </span>
                      <button className="rename-btn" disabled={!engine} aria-label={`Change color ${c.block + 1}`} title="Change thread" onClick={() => setPicking({ kind: "stops", stops: [c], title: name })}>
                        ✎
                      </button>
                      <button
                        className="rename-btn"
                        onClick={() => deleteColorBlock(c.block)}
                        disabled={!engine || !onlyMine || (design?.blocks.length ?? 0) < 2}
                        aria-label={`Remove color ${c.block + 1}`}
                        title="Remove this color's stitches (Ctrl+Z to undo)"
                      >
                        🗑
                      </button>
                    </li>
                  );
                })}
            </Fragment>
          );
        })}
      </ol>
      <ThreadPicker
        index={picking ? -1 : null}
        onClose={() => setPicking(null)}
        current={pickerCurrent()}
        onPick={onPicked}
        {...(picking?.kind === "stops" && picking.stops.length === 1 && picking.stops[0].was
          ? { onReset: () => recolorSources(picking.stops[0].sources, null), resetLabel: picking.stops[0].was.name || picking.stops[0].was.color }
          : {})}
      />
      <MatchAllDialog open={matching} onClose={() => setMatching(false)} />
    </Section>
  );
}

/** The pictures underneath the design, to trace over: one list, and the selected picture's
 *  settings (see-through, real size) right under its row. */
function PicturesSection({ sel }: { sel: SelKind }) {
  const images = useStore(selectImages);
  const selectedId = useStore((s) => s.selectedId);
  const select = useStore((s) => s.select);
  if (!images.length) return null;
  const current = images.find((im) => im.id === selectedId);
  const summary = current ? `${Math.round((1 - current.opacity) * 100)}% see-through${current.locked ? " · pinned" : ""}` : undefined;
  return (
    <Section id="pictures" sel={sel} defaultOpen={!!current} title="Pictures" badge={images.length} summary={summary}>
      <ul className="design-list">
        {images.map((im) => (
          <Fragment key={im.id}>
          <li
            className={im.id === selectedId ? "current" : undefined}
            onContextMenu={(e) => {
              select(im.id);
              openContextMenu(
                e,
                [...pictureMenu(), "separator", { label: im.visible ? "Hide this picture" : "Show this picture", run: () => setPicture(im.id, { visible: !im.visible }) }],
                im.name,
              );
            }}
          >
            <button className="name" onClick={() => select(im.id === selectedId ? null : im.id)}>
              🖼 {im.name}
            </button>
            <button
              className={`pin${im.locked ? " on" : ""}`}
              aria-pressed={im.locked}
              title={im.locked ? "Pinned to the board: clicks go through it. Click to unpin." : "Pin to the board, so it can't be moved by accident"}
              aria-label={im.locked ? "Unpin" : "Pin to the board"}
              onClick={() => setPicture(im.id, { locked: !im.locked })}
            >
              📌
            </button>
            <button title={im.visible ? "Hide" : "Show"} aria-label={im.visible ? "Hide" : "Show"} onClick={() => setPicture(im.id, { visible: !im.visible })}>
              {im.visible ? "👁" : "◌"}
            </button>
          </li>
          {im.id === selectedId && (
            <li className="picture-settings-row">
              <PictureSettings img={im} />
            </li>
          )}
          </Fragment>
        ))}
      </ul>
    </Section>
  );
}

/** The design as a whole: size, stitches, colors, fit in the hoop, and the fabric. */
function DesignSection({ sel }: { sel: SelKind }) {
  const design = useStore((s) => s.design);
  const layout = useStore(selectLayout);
  const hoop = useStore(selectHoop);
  const units = useStore((s) => s.units);
  const preview = useStore((s) => s.preview);
  const setPreview = useStore((s) => s.setPreview);
  const machine = useStore(selectMachine);
  if (!layout) return null;
  const fit = design && hoop ? hoopFit(design.info, hoop) : null;
  const est = design && design.info.stitches > 0 ? estimate(design, machine) : null;
  return (
    <Section
      id="design"
      sel={sel}
      defaultOpen={sel === "none"}
      title="Design"
      badge={fit && fit !== "fits" ? "!" : undefined}
      summary={design ? `${fmtLen(design.info.width_mm, units)} × ${fmtLen(design.info.height_mm, units)} · ${design.info.stitches.toLocaleString()} stitches` : "Nothing stitched yet"}
    >
      {design ? (
        <>
          {fit && hoop && <p className={`fit fit-${fit}`}>{FIT_TEXT[fit](hoop.name)}</p>}
          <dl>
            <div>
              <dt>Size</dt>
              <dd>
                {fmtLen(design.info.width_mm, units)} × {fmtLen(design.info.height_mm, units)}
              </dd>
            </div>
            <div>
              <dt>Stitches</dt>
              <dd>{design.info.stitches.toLocaleString()}</dd>
            </div>
            <div>
              <dt>Colors</dt>
              <dd>{design.info.colors}</dd>
            </div>
            {est && (
              <>
                <div title={`At ${est.speedSpm} stitches a minute, the machine's top speed. Long stitches slow it down, so allow a little more. Thread changes are extra.`}>
                  <dt>Sewing time</dt>
                  <dd>
                    {fmtMinutes(est.minutes)}
                    {est.threadChanges > 0 && <small> + {est.threadChanges} thread {est.threadChanges === 1 ? "change" : "changes"}</small>}
                  </dd>
                </div>
                <div title="Top thread, counting about 1 mm per stitch for going into the fabric. The bobbin uses about a third as much.">
                  <dt>Thread</dt>
                  <dd>
                    {fmtThread(est.topMeters, units)}
                    <small> · bobbin {fmtThread(est.bobbinMeters, units)}</small>
                  </dd>
                </div>
              </>
            )}
          </dl>
        </>
      ) : (
        <p className="hint">
          Pick a tool on the left (Line, Satin or Fill) and click on the canvas to draw. Add a picture to trace with{" "}
          <kbd>{formatShortcut(command("file.picture").shortcut)}</kbd>.
        </p>
      )}
      <FabricPicker />
      <label className="check" title="Moves between shapes in one thread run under stitching that's sewn later, where they can: fewer jumps and trims to snip">
        <input type="checkbox" checked={!!layout.travel_under} onChange={() => toggleTravelUnder()} /> Fewer jumps & trims (hide moves under later stitching)
      </label>
      <div className="btn-row">
        <Cmd id="layout.optimizeJumps" label="Optimize jumps" />
        <Cmd id="layout.shortestOrder" label="Sew in the shortest order" />
      </div>
      <Sub id="design-preview" title="Preview on" summary={GARMENTS.find((g) => g.id === preview.garment)?.label}>
        <Row label="Garment">
          <select value={preview.garment} onChange={(e) => setPreview({ garment: e.target.value as Garment })} aria-label="Preview on">
            {GARMENTS.map((g) => (
              <option key={g.id} value={g.id}>
                {g.label}
              </option>
            ))}
          </select>
        </Row>
        <Row label="Fabric color">
          <input type="color" value={preview.color} onChange={(e) => setPreview({ color: e.target.value })} aria-label="Fabric color" />
        </Row>
        <p className="hint">Just a picture behind the design, to see how it looks: nothing is stitched.</p>
      </Sub>
      {design && est && (
        <Sub id="design-thread" title="Thread used" summary={fmtThread(est.topMeters, units)}>
          <ul className="thread-use">
            {est.perThread.map((t) => {
              const th = design.threads[t.thread];
              return (
                <li key={t.thread}>
                  <span className="swatch small" style={{ background: th?.color }} />
                  <span className="name">{th ? th.name || th.color : `Thread ${t.thread + 1}`}</span>
                  <span className="amount">{fmtThread(t.meters, units)}</span>
                </li>
              );
            })}
          </ul>
          <p className="hint">Estimates, to check you have enough on the spool. Real use depends on the fabric and tension.</p>
        </Sub>
      )}
      {design && (
        <Sub id="design-details" title="File details" summary={design.format.toUpperCase()}>
          <dl>
            {(
              [
                ["File type", design.format.toUpperCase()],
                ["Color changes", String(design.info.color_changes)],
                ["Stops", String(design.info.stops)],
                ["Trims", String(design.info.trims)],
                ["Jumps", String(design.info.jumps)],
              ] as const
            ).map(([k, v]) => (
              <div key={k}>
                <dt>{k}</dt>
                <dd>{v}</dd>
              </div>
            ))}
          </dl>
        </Sub>
      )}
    </Section>
  );
}

/** Saved sets of colors (colorways): save the colors as they are, switch between sets. */
function ColorSets() {
  const layout = useStore(selectLayout);
  const [name, setName] = useState("");
  const sets = layout?.colorways ?? [];
  return (
    <Sub id="color-sets" title="Color sets" summary={sets.length ? `${sets.length} saved` : undefined}>
      <p className="hint">Save these colors as a set, try others, and switch back in one click (pink version, blue version…).</p>
      {sets.length > 0 && (
        <ul className="color-sets">
          {sets.map((c) => (
            <li key={c.name}>
              <span className="swatch-strip" aria-hidden>
                {Object.values(c.items)
                  .slice(0, 8)
                  .map((v, i) => (
                    <span key={i} style={{ background: (v.threads?.[0] ?? v.thread)?.color ?? "transparent" }} />
                  ))}
              </span>
              <span className="name">{c.name}</span>
              <button onClick={() => void applyColorway(c.name)}>Use</button>
              <button aria-label={`Delete ${c.name}`} title="Delete this set" onClick={() => void deleteColorway(c.name)}>
                🗑
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="btn-row">
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Name, e.g. Pink" aria-label="Color set name" onKeyDown={(e) => e.key === "Enter" && name.trim() && (void saveColorway(name), setName(""))} />
        <button disabled={!name.trim()} onClick={() => (void saveColorway(name), setName(""))}>
          Save colors
        </button>
      </div>
    </Sub>
  );
}

/** Stitching LUDD adds that belongs to no shape: the basting box (sewn first) and knockdown
 *  (sewn first, or straight after the basting box). Null for a design's own colors. */
export function addedStitching(layout: Layout, b: { sources?: unknown[] }, index: number): "basting" | "knockdown" | null {
  if (b.sources?.length) return null;
  if (layout.basting?.enabled && index === 0) return "basting";
  if (layout.knockdown?.enabled) return "knockdown";
  return layout.basting?.enabled ? "basting" : null;
}

/** How long a click waits to see if it's a double-click. */
const DOUBLE_CLICK_MS = 250;

/** A name you can change: double-click it (or press F2). Enter keeps it, Esc puts it back. */
function RenameField({
  id,
  name,
  className,
  prefix,
  onClick,
  listen,
}: {
  id: string;
  name: string;
  className?: string;
  prefix?: string;
  onClick?: () => void;
  /** Start editing when a "ludd:rename" event names this (F2 sends the selected item's id). */
  listen?: string;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(name);
  const cancelled = useRef(false);
  // A click waits a moment in case it's the first half of a double-click (which renames
  // instead), so the panel doesn't change under the second click.
  const clickTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  useEffect(() => () => clearTimeout(clickTimer.current), []);
  useEffect(() => {
    const onRename = (e: Event) => {
      if (listen && (e as CustomEvent).detail === listen) {
        setDraft(name);
        setEditing(true);
      }
    };
    window.addEventListener("ludd:rename", onRename);
    return () => window.removeEventListener("ludd:rename", onRename);
  }, [listen, name]);
  if (!editing)
    return (
      <span
        className={`rename ${className ?? ""}`}
        title={`${name}: ${onClick ? "click to select, " : ""}double-click (or F2) to rename`}
        role={onClick ? "button" : undefined}
        tabIndex={onClick ? 0 : undefined}
        onClick={
          onClick
            ? (e) => {
                clearTimeout(clickTimer.current);
                if (e.detail > 1) return; // the second click of a double-click
                clickTimer.current = setTimeout(onClick, DOUBLE_CLICK_MS);
              }
            : undefined
        }
        onKeyDown={onClick ? (e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), onClick()) : undefined}
        onDoubleClick={(e) => {
          e.stopPropagation();
          clearTimeout(clickTimer.current);
          setDraft(name);
          setEditing(true);
        }}
      >
        {prefix}
        {name}
      </span>
    );
  return (
    <input
      className="rename-input"
      autoFocus
      value={draft}
      maxLength={80}
      aria-label="Name"
      onFocus={(e) => e.target.select()}
      onChange={(e) => setDraft(e.target.value)}
      onKeyDown={(e) => {
        if (e.key === "Enter") (e.target as HTMLInputElement).blur();
        if (e.key === "Escape" && !heldCount()) {
          cancelled.current = true;
          (e.target as HTMLInputElement).blur();
        }
      }}
      onBlur={() => {
        if (!cancelled.current && draft.trim() !== name) renameThing(id, draft);
        cancelled.current = false;
        setEditing(false);
      }}
    />
  );
}

/** Small icon buttons for the header, each a command (so it shows its shortcut). */
function Quick({ id, label, icon }: { id: string; label?: string; icon: string }) {
  const c = command(id);
  return (
    <button className="quick" onClick={c.run} disabled={!(c.enabled?.() ?? true)} title={`${label ?? c.title} (${formatShortcut(c.shortcut)})`} aria-label={label ?? c.title}>
      {icon}
    </button>
  );
}

/** What's selected, always in view at the top: its name, and what you do to it most. */
function Inspector({ sel, name, kind, pinned, img }: { sel: SelKind; name: string; kind: string; pinned?: boolean; img?: RefImage }) {
  const layout = useStore(selectLayout);
  const selectedId = useStore((s) => s.selectedId);
  const extraIds = useStore((s) => s.extraIds);
  useStore((s) => s.history);
  if (sel === "none") return null;
  if (sel === "multi" && layout) {
    const ids = [selectedId, ...extraIds];
    const group = layout.items.find((x) => x.id === ids[0])?.group;
    const grouped = !!group && ids.every((id) => layout.items.find((x) => x.id === id)?.group === group);
    return (
      <div className="inspector">
        <div className="inspector-name">
          <strong>
            {ids.length} selected{grouped ? " (a group)" : ""}
          </strong>
          <small className="multi-note">They move, turn, resize, mirror, copy, recolor and delete together. Shift+click adds or removes one.</small>
        </div>
        <div className="inspector-actions">
          {grouped ? <Quick id="arrange.ungroup" icon="⬚" label="Ungroup" /> : <Quick id="arrange.group" icon="▣" label="Group" />}
          <Quick id="object.thread" icon="🧵" label="Thread" />
          <Quick id="arrange.rotateCw" icon="⟳" />
          <Quick id="arrange.mirrorX" icon="⇋" />
          <Quick id="arrange.duplicate" icon="⧉" />
          <Menu
            label="More actions"
            items={[
              { id: "arrange.repeat" },
              { id: "arrange.mirrorY" },
              { id: "arrange.rotateCcw" },
              "separator",
              { id: "object.offset", label: "Outline / offset around them…" },
              { id: "object.merge", label: "Merge into one shape" },
              { id: "object.cutOut", label: "Cut the shapes on top out of the fill" },
              { id: "text.onLine", label: "Put the text on the line" },
              "separator",
              { id: "arrange.delete" },
            ]}
          />
        </div>
      </div>
    );
  }
  if (img) {
    return (
      <div className="inspector">
        <div className="inspector-name">
          <strong>
            <RenameField id={img.id} name={img.name} className="inspector-title" listen={img.id} />
          </strong>
          <small>Picture{img.locked ? " · pinned" : ""}</small>
        </div>
        <div className="inspector-actions">
          <button className="quick" aria-pressed={img.locked} aria-label={img.locked ? "Unpin" : "Pin to the board"} onClick={() => setPicture(img.id, { locked: !img.locked })} title={img.locked ? "Pinned to the board: click to unpin (Ctrl+L)" : "Pin to the board (Ctrl+L)"}>
            📌
          </button>
          <button className="quick" onClick={() => setPicture(img.id, { visible: !img.visible })} title={img.visible ? "Hide" : "Show"} aria-label={img.visible ? "Hide" : "Show"}>
            {img.visible ? "👁" : "◌"}
          </button>
          <Menu label="More actions" items={[{ id: "arrange.delete", label: "Remove picture" }]} />
        </div>
      </div>
    );
  }
  return (
    <div className="inspector">
      <div className="inspector-name">
        <strong>{selectedId ? <RenameField id={selectedId} name={name} className="inspector-title" listen={selectedId} /> : name}</strong>
        <small>
          {kind}
          {pinned ? " · 📌 pinned" : ""}
        </small>
      </div>
      <div className="inspector-actions">
        <Quick id="arrange.rotateCcw" icon="⟲" />
        <Quick id="arrange.rotateCw" icon="⟳" />
        <Quick id="arrange.mirrorX" icon="⇋" />
        <Quick id="arrange.duplicate" icon="⧉" />
        <Menu
          label="More actions"
          items={[
            ...(sel === "file" ? [] : [{ id: "object.thread" }]),
            ...(sel === "text" ? [{ id: "text.edit" }, { id: "text.toShapes" }] : []),
            { id: "arrange.centre" },
            { id: "arrange.first" },
            { id: "arrange.last" },
            "separator",
            { id: "arrange.repeat" },
            { id: "arrange.mirrorY" },
            { id: "arrange.pin", label: pinned ? "Unpin" : "Pin in place", checked: !!pinned },
            { id: "arrange.rename", label: "Rename…" },
            "separator",
            { id: "object.offset", label: "Outline / offset…" },
            { id: "tool.knife", label: "Knife: cut in two" },
            { id: "object.hole", label: "Cut a hole (draw round it)" },
            { id: "edit.stitches", label: "Edit stitches" },
            "separator",
            { id: "arrange.delete" },
          ]}
        />
      </div>
    </div>
  );
}

export function InfoPanel() {
  const design = useStore((s) => s.design);
  const layout = useStore(selectLayout);
  const images = useStore(selectImages);
  const selectedId = useStore((s) => s.selectedId);
  const extra = useStore((s) => s.extraIds.length);
  if (!layout) return null;

  const picture = images.find((im) => im.id === selectedId);
  const selIndex = layout.items.findIndex((it) => it.id === selectedId);
  const selItem = selIndex >= 0 ? layout.items[selIndex] : null;
  const selInfo = selItem ? design?.items?.[selIndex] : undefined;
  const sel: SelKind = extra
    ? "multi"
    : picture
      ? "picture"
      : !selItem
        ? "none"
        : isObject(selItem)
          ? selItem.kind
          : isText(selItem)
            ? "text"
            : "file";
  const kindName = sel === "text" ? "Lettering" : sel === "file" ? "Stitch file" : selItem && isObject(selItem) ? KIND_TITLE[selItem.kind] : "";

  return (
    <aside className="info-panel">
      <div className="panel-title">
        <h2 title={design?.path}>{design?.name ?? (layout.title || "New design")}</h2>
      </div>
      <Inspector sel={sel} name={selInfo?.name ?? picture?.name ?? ""} kind={kindName} pinned={!!selItem?.locked} img={picture} />
      <AdvisorPanel />

      {picture && <PicturesSection sel={sel} />}
      {sel !== "multi" &&
        selItem &&
        selInfo &&
        (isObject(selItem) ? (
          <ObjectSections item={selItem} info={selInfo} sel={sel} />
        ) : isText(selItem) ? (
          <SelectedText item={selItem} info={selInfo} sel={sel} />
        ) : (
          <FileSections item={selItem as FileItem} info={selInfo} sel={sel} />
        ))}

      <DesignSection sel={sel} />
      <OrderSection sel={sel} />
      <Checks sel={sel} />
      {!picture && <PicturesSection sel={sel} />}
    </aside>
  );
}
