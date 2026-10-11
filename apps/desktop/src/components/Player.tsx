import { useEffect } from "react";
import { command } from "../actions";
import { formatShortcut } from "../commands";
import { PLAYER_SPEEDS, useStore } from "../store";

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
      <select
        value={speed}
        onChange={(e) => setSpeed(Number(e.target.value))}
        aria-label="Playback speed"
        title={`Playback speed (${formatShortcut("[")} / ${formatShortcut("]")})`}
      >
        {PLAYER_SPEEDS.map((v) => (
          <option key={v} value={v}>
            {v.toLocaleString()} st/s
          </option>
        ))}
      </select>
    </div>
  );
}
