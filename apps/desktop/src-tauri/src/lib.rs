// The engine sidecar is spawned and driven from the UI through the shell plugin;
// the Rust side hosts the window, native file dialogs and updates.

use std::sync::Mutex;

use tauri::menu::{Menu, MenuItem, MenuItemKind};
use tauri::{AppHandle, Emitter, Manager, Runtime, State};

/// The file in a command line (double-clicking a .ludd project), if any. The first argument is
/// the program itself.
fn file_arg<I: IntoIterator<Item = String>>(args: I) -> Option<String> {
    args.into_iter()
        .skip(1)
        .find(|a| !a.starts_with('-') && std::path::Path::new(a).is_file())
}

/// This process's command line. `args_os`, because `std::env::args` panics on a file name that
/// isn't valid Unicode (QA: such a name just isn't opened).
fn command_line() -> Vec<String> {
    std::env::args_os()
        .map(|a| a.to_string_lossy().into_owned())
        .collect()
}

/// A file the system asked LUDD to open (macOS sends a double-clicked file as an event, not on
/// the command line). Kept until the window asks for it; once it has, later files go straight
/// to the window.
#[derive(Default)]
struct OpenRequests {
    pending: Option<String>,
    window_ready: bool,
}

impl OpenRequests {
    /// The window asks what to open at start: a file the system already sent, if any.
    fn take(&mut self) -> Option<String> {
        self.window_ready = true;
        self.pending.take()
    }

    /// The system asks to open `file`. Returns it when the window is ready to open it now;
    /// otherwise it is kept for `take`.
    fn offer(&mut self, file: String) -> Option<String> {
        if self.window_ready {
            Some(file)
        } else {
            self.pending = Some(file);
            None
        }
    }
}

/// The file LUDD was opened with, if any.
#[tauri::command]
fn launch_file(opened: State<'_, Mutex<OpenRequests>>) -> Option<String> {
    let from_system = opened.lock().ok().and_then(|mut o| o.take());
    from_system.or_else(|| file_arg(command_line()))
}

/// The licences of the software LUDD bundles (THIRD-PARTY-NOTICES.txt, shipped as a resource),
/// for Settings > About. Only this one file is read.
#[tauri::command]
fn third_party_notices<R: Runtime>(app: AppHandle<R>) -> Result<String, String> {
    let path = app
        .path()
        .resolve(
            "THIRD-PARTY-NOTICES.txt",
            tauri::path::BaseDirectory::Resource,
        )
        .map_err(|e| e.to_string())?;
    std::fs::read_to_string(&path)
        .map_err(|_| "The licence list isn't in this copy of LUDD.".to_string())
}

/// Bring the window forward and have it open `file`.
fn open_in_window<R: Runtime>(app: &AppHandle<R>, file: String) {
    if let Some(w) = app.get_webview_window("main") {
        let _ = w.unminimize();
        let _ = w.set_focus();
    }
    let _ = app.emit("ludd:open-file", file);
}

/// The system asked to open `file` (macOS Finder).
#[cfg_attr(not(target_os = "macos"), allow(dead_code))]
fn system_open<R: Runtime>(app: &AppHandle<R>, file: String) {
    let now = app
        .state::<Mutex<OpenRequests>>()
        .lock()
        .ok()
        .and_then(|mut o| o.offer(file));
    if let Some(file) = now {
        open_in_window(app, file);
    }
}

const QUIT_ID: &str = "ludd-quit";

/// macOS: the standard Quit (Cmd+Q) ends the app without asking about unsaved changes. Replace
/// it with one that closes the window the normal way, so "Save your changes first?" is asked.
#[cfg_attr(not(target_os = "macos"), allow(dead_code))]
fn with_asking_quit<R: Runtime>(app: &AppHandle<R>, menu: Menu<R>) -> tauri::Result<Menu<R>> {
    if let Some(MenuItemKind::Submenu(app_menu)) = menu.items()?.into_iter().next() {
        let items = app_menu.items()?;
        if let Some(last) = items.len().checked_sub(1) {
            // The app menu ends with the standard Quit.
            if matches!(items[last], MenuItemKind::Predefined(_)) {
                app_menu.remove_at(last)?;
                let text = format!("Quit {}", app.package_info().name);
                app_menu.append(&MenuItem::with_id(app, QUIT_ID, text, true, Some("CmdOrCtrl+Q"))?)?;
            }
        }
    }
    Ok(menu)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let builder = tauri::Builder::default()
        // One LUDD at a time: launching it again (double-clicking a project while it's open)
        // brings the open window forward and opens the file there. A second copy would start a
        // second engine and mistake the first window's autosave for a crash.
        .plugin(tauri_plugin_single_instance::init(|app, args, _cwd| {
            match file_arg(args) {
                Some(file) => open_in_window(app, file),
                None => {
                    if let Some(w) = app.get_webview_window("main") {
                        let _ = w.unminimize();
                        let _ = w.set_focus();
                    }
                }
            }
        }))
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_process::init())
        .manage(Mutex::new(OpenRequests::default()))
        .on_menu_event(|app, event| {
            if event.id().0 == QUIT_ID {
                match app.get_webview_window("main") {
                    // Closing asks about unsaved changes first, then LUDD quits.
                    Some(w) => {
                        let _ = w.close();
                    }
                    None => app.exit(0),
                }
            }
        })
        .invoke_handler(tauri::generate_handler![launch_file, third_party_notices]);

    #[cfg(target_os = "macos")]
    let builder = builder.menu(|app| with_asking_quit(app, Menu::default(app)?));

    builder
        .build(tauri::generate_context!())
        .expect("error while running LUDD")
        .run(|_app, _event| {
            // macOS hands a double-clicked .ludd to the app as an event, not on the command line.
            #[cfg(target_os = "macos")]
            if let tauri::RunEvent::Opened { urls } = _event {
                if let Some(path) = urls.iter().find_map(|u| u.to_file_path().ok()) {
                    system_open(_app, path.to_string_lossy().into_owned());
                }
            }
        });
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_file_sent_before_the_window_is_ready_waits_for_it() {
        let mut o = OpenRequests::default();
        assert_eq!(o.offer("a.ludd".into()), None);
        assert_eq!(o.take(), Some("a.ludd".into()));
        // Asked once: later files go straight to the window, and aren't opened twice.
        assert_eq!(o.offer("b.ludd".into()), Some("b.ludd".into()));
        assert_eq!(o.take(), None);
    }

    #[test]
    fn the_command_line_file_skips_the_program_and_options() {
        let me = std::env::current_exe().unwrap().to_string_lossy().into_owned();
        let args = vec![me.clone(), "--flag".into(), "missing.ludd".into(), me.clone()];
        assert_eq!(file_arg(args), Some(me.clone()));
        assert_eq!(file_arg(vec![me]), None);
    }
}
