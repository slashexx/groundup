// Learn more about Tauri commands at https://tauri.app/develop/calling-rust/
#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust!", name)
}

/// Write an export to a path the operator has just chosen in the save dialog.
///
/// `tauri-plugin-dialog` returns a path and nothing else, so without a writer here the
/// export would end at a filename. This is a command rather than `tauri-plugin-fs`
/// because the only path it ever writes is one a human picked by hand a moment earlier:
/// the fs plugin would add a scope declaration and a second permission surface to
/// re-authorise exactly that.
#[tauri::command]
fn write_export(path: String, contents: String) -> Result<(), String> {
    std::fs::write(&path, contents).map_err(|e| format!("could not write {path}: {e}"))
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![greet, write_export])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
