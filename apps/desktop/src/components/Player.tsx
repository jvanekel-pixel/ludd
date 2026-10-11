import { useEffect } from "react";
import { command } from "../actions";
import { formatShortcut } from "../commands";
import { MACHINE_SPEED, PLAYER_SPEEDS, useStore } from "../store";

export const speedIndex = (v: number) => {
  let best = 0;
  PLAYER_SPEEDS.forEach((s, i) => Math.abs(Math.log(s / v)) < Math.abs(Math.log(PLAYER_SPEEDS[best] / v)) && (best = i));
  return best;
};

const speedText = (v: number) => (v === MACHINE_SPEED ? "machine speed" : `${v.toLocaleString()} stitches/s`);

/** Advances the playhead while playing. */
function usePlayback() {
  const playing = useStore((s) => s.playing);
  useEffect(() => {
    if (!playing) return;
    let raf = 0;
    let last = performance.now();
    let carry = 0;
    const tick = (now: number) => {
      const s = useStore.getState();
      carry += ((now - last) / 1000) * s.speed;
      last = now;
      const whole = Math.floor(carry);
      carry -= whole;
      if (whole) s.setPlayhead(s.playhead + whole);
      if (useStore.getState().playhead >= s.stitchIdx.length) {
        s.setPlaying(false);
        return;
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing]);
}

export function Player() {
  usePlayback();
  const total = useStore((s) => s.stitchIdx.length);
  const playhead = useStore((s) => s.playhead);
  const playing = useStore((s) => s.playing);
  const speed = useStore((s) => s.speed);
  const blockStarts = useStore((s) => s.blockStarts);
  const { setPlayhead, setPlaying, setSpeed } = useStore.getState();
  const tip = (id: string) => `${command(id).title} (${formatShortcut(command(id).shortcut)})`;

  return (
    <div className="player">
      <button onClick={() => command("player.start").run()} title={tip("player.start")} aria-label="Go to start">
        ⏮
      </button>
      <button onClick={() => command("player.prevColor").run()} title={tip("player.prevColor")} aria-label="Previous color">
        ◀▮
      </button>
      <button
        className="play"
        onClick={() => setPlaying(!playing)}
        title={tip("player.toggle")}
        aria-label={playing ? "Pause" : "Play"}
      >
        {playing ? "❚❚" : "▶"}
      </button>
      <button onClick={() => command("player.nextColor").run()} title={tip("player.nextColor")} aria-label="Next color">
        ▮▶
      </button>
      <button onClick={() => command("player.end").run()} title={tip("player.end")} aria-label="Show whole design">
        ⏭
      </button>
      <div className="scrubber">
        <input
          type="range"
          min={0}
          max={total}
          value={playhead}
          onChange={(e) => {
            setPlaying(false);
            setPlayhead(Number(e.target.value));
          }}
          aria-label="Stitch position"
        />
        <div className="ticks" aria-hidden>
          {total > 0 &&
            blockStarts.slice(1).map((s) => <span key={s} style={{ left: `${(s / total) * 100}%` }} />)}
        </div>
      </div>
      <span className="count">
        {playhead.toLocaleString()} / {total.toLocaleString()}
      </span>
      <label className="speed" title={`Speed: ${tip("player.slower")} slower, ${tip("player.faster")} faster`}>
        <span aria-hidden>🐢</span>
        <input
          type="range"
          min={0}
          max={PLAYER_SPEEDS.length - 1}
          step={1}
          value={speedIndex(speed)}
          onChange={(e) => setSpeed(PLAYER_SPEEDS[Number(e.target.value)])}
          aria-label="Stitch-out speed"
          aria-valuetext={speedText(speed)}
        />
        <span aria-hidden>🐇</span>
        <span className="speed-value">{speedText(speed)}</span>
      </label>
    </div>
  );
}
