// The engine sidecar is spawned and driven from the UI through the shell plugin;
// the Rust side hosts the window, native file dialogs and updates.

/// The file LUDD was opened with (double-clicking a .ludd project), if any.
#[tauri::command]
fn launch_file() -> Option<String> {
    std::env::args()
        .skip(1)
        .find(|a| !a.starts_with('-') && std::path::Path::new(a).is_file())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_process::init())
        .invoke_handler(tauri::generate_handler![launch_file])
        .run(tauri::generate_context!())
        .expect("error while running LUDD");
}
