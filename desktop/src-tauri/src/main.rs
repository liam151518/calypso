//! Calypso desktop sidecar host.
//!
//! Spawns the Python `app.server` Flask backend as a child process when the
//! Tauri runtime signals `Ready`, and tears it down on `Exit`. The webview
//! in `tauri.conf.json` is pointed at the SPA in `web/dist/`. Tauri
//! intercepts the navigation and serves the bundle, which then talks to
//! the sidecar via http://localhost:<port>/api/*.
//!
//! Builds: `cargo tauri build` from `desktop/`.

use std::process::{Child, Command};
use std::sync::Mutex;
use tauri::{Manager, RunEvent};

#[cfg(target_os = "windows")]
const SIDECAR_NAME: &str = "calypso-sidecar.exe";
#[cfg(not(target_os = "windows"))]
const SIDECAR_NAME: &str = "calypso-sidecar";

const DEFAULT_PORT: u16 = 51730;

struct Sidecar(Mutex<Option<Child>>);

fn spawn_sidecar(app: &tauri::AppHandle) -> std::io::Result<Child> {
    let port: u16 = std::env::var("CALYPSO_DESKTOP_PORT")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(DEFAULT_PORT);
    let mut cmd = Command::new(SIDECAR_NAME);
    cmd.env("CALYPSO_HOST", "127.0.0.1");
    cmd.env("CALYPSO_PORT", port.to_string());
    // Force unbuffered Python output so logs stream to stdout.
    cmd.env("PYTHONUNBUFFERED", "1");
    // Suppress any GUI file-pickers the sidecar might show.
    cmd.env("CALYPSO_DESKTOP", "1");
    cmd.stdout(std::process::Stdio::piped());
    cmd.stderr(std::process::Stdio::piped());
    let child = cmd.spawn()?;
    // Notify the frontend of the chosen port so it can build API URLs.
    let _ = app.emit_all("calypso://ready", port);
    Ok(child)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .manage(Sidecar(Mutex::new(None)))
        .setup(|app| {
            let handle = app.handle().clone();
            // Spawn on Ready: simplest pattern that survives the front-end
            // taking its time to load.
            let sidecar = spawn_sidecar(&handle)?;
            *app.state::<Sidecar>().0.lock().unwrap() = Some(sidecar);
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error building Calypso desktop")
        .run(|_app, event| {
            if let RunEvent::ExitRequested { .. } | RunEvent::Exit = event {
                if let Some(state) = _app.try_state::<Sidecar>() {
                    if let Ok(mut guard) = state.0.lock() {
                        if let Some(mut child) = guard.take() {
                            let _ = child.kill();
                            let _ = child.wait();
                        }
                    }
                }
            }
        });
}
