# LUDD user guide

LUDD is free embroidery software. Open designs and change them, draw your own, add lettering, and
save them for your machine. It works offline, with no account and no sign-in. Everything below is
also in the app: press **F1** for Help.

## Install

Download LUDD from the [Releases page](https://github.com/jvanekel-pixel/ludd/releases/latest).
Pick the file for your computer:

| Your computer | Download | Then |
| --- | --- | --- |
| Windows 10 or 11 | `LUDD_1.0.0_x64-setup.exe` | Open it. No administrator password is needed. |
| Mac with Apple chip (M1 or later) | `LUDD_1.0.0_aarch64.dmg` | Open it and drag LUDD into Applications. |
| Mac with Intel chip | `LUDD_1.0.0_x64.dmg` | Open it and drag LUDD into Applications. |
| Linux | `LUDD_1.0.0_amd64.AppImage` (or the `.deb`) | Make the AppImage executable and open it. |

**"Windows protected your PC".** LUDD is new and not yet code-signed, so Windows may show a
blue box the first time. Click **More info**, then **Run anyway**. You only do this once.

**Mac: "LUDD can't be opened because Apple cannot check it".** Open **System Settings → Privacy
& Security**, scroll down, and click **Open Anyway** next to LUDD. Or right-click LUDD in
Applications, choose **Open**, then **Open** again. You only do this once.

**Updates.** LUDD tells you when a new version is out (you can turn this off in Settings). Click
**Install and restart**; your work is offered back afterwards if you hadn't saved it.

## Your first design, in ten minutes

1. **Pick your machine.** The first time LUDD opens it asks which machine you have; this sets the
   hoop on screen and the file type it saves. You can change it later in Settings (⚙).
2. **Open a sample.** Click *Or try one of the sample designs* and open **Flower.ludd**. The grid
   squares are inches; the box is your hoop.
3. **Watch it sew.** Press **Space** to play the stitching from the start; the slider at the bottom
   steps through it.
4. **Change a color.** In the thread list on the right, click the pencil next to a color and pick
   another thread. **Match…** finds the closest of your own spools (add them in ⋯ → My threads).
5. **Resize it.** Click the flower, then drag a corner handle. Shapes drawn in LUDD keep the right
   density at any size.
6. **Save it for the machine.** Click **Save for machine** (Ctrl+E). LUDD says whether it fits
   your hoop and lists anything to check. Save the file (PES for Brother, JEF for Janome) to a USB
   stick, put the stick in your machine and choose the design there.
7. **Keep the project.** **Save** (Ctrl+S) keeps a LUDD project (`.ludd`) you can change later.
   Pictures you traced and designs you placed are kept inside it.

## Drawing your own

Choose a tool on the left: **Line** (L), **Satin** (C), **Fill** (F) or **Text** (Shift+T). As in
Embrilliance, a click places a **curve** point, **Ctrl+click** a straight point and **Shift+click** a
sharp corner; **Enter** or right-click finishes, **Esc** lets go. To trace a picture,
add it with **Ctrl+I**, then draw over it: Trace Assist shows the next point and **Tab** takes it.

Select a shape to change its stitch type, density, angle and thread. More settings are under
**More options**; they start on sensible automatic values.

## Before you stitch

- **Stitching on** (top of the panel): choose the fabric. LUDD adjusts the stitching and tells you
  which stabilizer to use.
- **Checks**: LUDD lists anything that may stitch badly (too much thread in one place, long loose
  stitches, shapes that almost touch) with why it matters and what to do. **Show me** jumps there.
- **Too big for the hoop?** Save for machine offers to split it into hoopings with alignment marks.
- **Jump threads** on machines that only cut at color changes (like the Brother PE550D): tick
  *Have the machine cut jump threads* in Save for machine.

## Help and the optional AI

Press **F1** for Help: search the guide by typing a question; it works offline. LUDD has an
optional AI add-on (off by default) for stitch suggestions and answers in plain words; see
Settings → AI. Nothing is sent anywhere unless you turn it on, and AI suggestions only change your
design when you accept them.

## Your files and privacy

- No account, no sign-in, no tracking. LUDD only goes online to check for updates (if you let it)
  and, if you turn it on, for the AI add-on.
- Projects are `.ludd` files: zip files with your design, pictures and settings inside, in an open
  format.
- Your threads, settings and crash-recovery copy are kept in your user folder
  (Windows: `%APPDATA%\Ludd`).

## Problems?

- **The status bar says "Engine disconnected".** Close LUDD and open it again. If it keeps
  happening, reinstall it from the Releases page.
- **The machine won't show the design.** Check the file type (PES for Brother, JEF for Janome),
  that the design fits the hoop, and that the file is in the top folder of the USB stick.
- **Something else?** [Open an issue](https://github.com/jvanekel-pixel/ludd/issues) with what you
  did and what happened (a screenshot helps).

## Uninstall

Windows: Settings → Apps → LUDD → Uninstall. Mac: drag LUDD from Applications to the Bin. Your
projects stay wherever you saved them.
