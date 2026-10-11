import { Kind, type Design } from "./types";

/** Records per drawable chunk: scrubbing only redraws the one chunk under the playhead. */
export const CHUNK_RECORDS = 2000;

export type Chunk = { thread: number; block: number; start: number; end: number };

/** Split color blocks into chunks of at most `size` records. */
export function chunkBlocks(design: Design, size = CHUNK_RECORDS): Chunk[] {
  const chunks: Chunk[] = [];
  design.blocks.forEach((b, block) => {
    for (let s = b.start; s < b.end; s += size) {
      chunks.push({ thread: b.thread, block, start: s, end: Math.min(s + size, b.end) });
    }
  });
  return chunks;
}

/** Record index of every stitch, in sewing order. Stitch n (1-based) is records[stitchRecords[n-1]]. */
export function stitchRecordIndex(design: Design): Int32Array {
  const kinds = design.records.kind;
  const out = new Int32Array(design.info.stitches);
  let n = 0;
  for (let i = 0; i < kinds.length && n < out.length; i++) {
    if (kinds[i] === Kind.Stitch) out[n++] = i;
  }
  return n === out.length ? out : out.slice(0, n);
}

/** How many records are visible when `stitches` stitches have been sewn. */
export function visibleRecords(stitchIdx: Int32Array, stitches: number, totalRecords: number): number {
  if (stitches <= 0) return 0;
  if (stitches >= stitchIdx.length) return totalRecords;
  return stitchIdx[stitches - 1] + 1;
}

/** Index of the color block containing record `r` (or the last block sewn before it). */
export function blockAt(design: Design, r: number): number {
  const blocks = design.blocks;
  let lo = 0;
  let hi = blocks.length - 1;
  let ans = 0;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (blocks[mid].start <= r) {
      ans = mid;
      lo = mid + 1;
    } else hi = mid - 1;
  }
  return ans;
}

/** Stitch count at which each color block starts, for jumping between colors. */
export function blockStartStitches(design: Design, stitchIdx: Int32Array): number[] {
  return design.blocks.map((b) => {
    let lo = 0;
    let hi = stitchIdx.length;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (stitchIdx[mid] < b.start) lo = mid + 1;
      else hi = mid;
    }
    return lo;
  });
}
