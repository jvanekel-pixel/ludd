# LUDD user guide

LUDD is free embroidery software. Open designs and change them, draw your own, add lettering, and
save them for your machine. It works offline, with no account and no sign-in. Everything below is
also in the app: press **F1** for Help.

## Install

Download LUDD from the [Releases page](https://github.com/jvanekel-pixel/ludd/releases/latest).
Pick the file for your computer:

| Your computer | Download | Then |
| --- | --- | --- |
| Windows 10 or 11 (64-bit) | `LUDD_<version>_x64-setup.exe` | Open it. No administrator password is needed. |
| Mac with Apple chip (M1 or later) | `LUDD_<version>_aarch64.dmg` | Open it and drag LUDD into Applications. |
| Mac with Intel chip | `LUDD_<version>_x64.dmg` | Open it and drag LUDD into Applications. |
| Linux | `LUDD_<version>_amd64.AppImage` (or the `.deb`) | Make the AppImage executable and open it. |

`<version>` is the version number, such as 1.0.1. LUDD needs Windows 10 or 11 (64-bit), macOS 14
Sonoma or newer, or Linux with glibc 2.35 or newer (Ubuntu 22.04 and later). AI tracing isn't
available on Intel Macs.

**"Windows protected your PC".** LUDD is new and not yet code-signed, so Windows may show a
blue box the first time. Click **More info**, then **Run anyway**. You only do this once.

**Mac: "LUDD can't be opened because Apple cannot check it".** Open **System Settings → Privacy
& Security**, scroll down, and click **Open Anyway** next to LUDD. Or right-click LUDD in
Applications, choose **Open**, then **Open** again. You only do this once.

**Updates.** LUDD tells you when a new version is out (untick this on the welcome card or in
Settings; it never checks before you've answered). Click
**Install and restart**; your work is offered back afterwards if you hadn't saved it.

## Your first design, in ten minutes

1. **Pick your machine.** The first time LUDD opens it asks which machine you have; this sets the
   hoop on screen and the file type it saves. You can change it later in Settings (⚙).
2. **Open a sample.** Click *Or try one of the sample designs* and open **Flower.ludd**. The grid
   squares are inches; the box is your hoop.
3. **Watch it sew.** Press **Space** to play the stitching from the start; the slider at the bottom
   steps through it.
4. **Change a color.** In **Order & colors** on the right, click a step's color square (or its
   pencil) and pick another thread. **Match…** finds the closest of your own spools (add them in ⋯ → My threads &
   charts).
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
add it with **Ctrl+I**, then pick **Auto-trace** (Shift+A) and click inside a shape: LUDD outlines it for you (Tab for another guess, Enter to use it).

Select a shape to change its stitch type, density, angle and thread in its section of the panel.
More settings are folded inside it, under **Underlay** and **Advanced stitch settings**; they start
on sensible automatic values. The [manual](USER-MANUAL.md) explains every setting.

## Before you stitch

- **Stitching on** (in the panel's **Design** section; click empty fabric to see it): choose the
  fabric. LUDD adjusts the stitching and tells you which stabilizer to use.
- **Check before stitching**: LUDD lists anything that may stitch badly (too much thread in one place, long loose
  stitches, shapes that almost touch) with why it matters and what to do. **Show me** jumps there.
- **Too big for the hoop?** Save for machine offers to make it a little smaller (if it's only just
  too big) or to split it into hoopings with alignment marks.
- **Jump threads** on machines that only cut at color changes (like the Brother PE550D): tick
  *Have the machine cut jump threads* in Save for machine.

## Help and the optional AI

Press **F1** for Help: search the guide by typing a question; it works offline. LUDD has an
optional AI add-on (off by default) for stitch suggestions and answers in plain words; see
**AI add-on (optional)** in Settings. **AI tracing (optional)**, also in Settings, is a small model
that makes Auto-trace better at photos; it runs on your computer. Nothing is sent anywhere unless you turn it on, and AI suggestions only change your
design when you accept them.

## Your files and privacy

- No account, no sign-in, no tracking. LUDD only goes online to check for updates (if you let it),
  to download the AI tracing model (only when you ask) and, if you turn it on, for the AI add-on.
- Projects are `.ludd` files: zip files with your design, pictures and settings inside, in an open
  format.
- Your threads, settings, stitch fonts and crash-recovery copy are kept in your user folder
  (Windows: `%APPDATA%\Ludd`), with private copies of the pictures and designs you add (deleted
  after 90 days unused).
- The licences of the software LUDD includes: Settings → About → **Licences…**.

## Problems?

**A PES file loads off-centre on my Brother machine.** PES files saved by LUDD before 13 October 2026
were placed off-centre. Save the design for the machine again with the current LUDD.

- **The status bar says "Engine disconnected".** LUDD restarts it by itself; if it can't, click
  **Restart engine** in the status bar (your work stays on screen; save it). If it keeps
  happening, reinstall LUDD from the Releases page.
- **The machine won't show the design.** Check the file type (PES for Brother, JEF for Janome),
  that the design fits the hoop, and that the file is in the top folder of the USB stick.
- **Something else?** [Open an issue](https://github.com/jvanekel-pixel/ludd/issues) with what you
  did and what happened (a screenshot helps).

## Uninstall

Windows: Settings → Apps → LUDD → Uninstall. Mac: drag LUDD from Applications to the Bin. Your
projects stay wherever you saved them.
