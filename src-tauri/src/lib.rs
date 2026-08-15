use std::collections::VecDeque;
use std::sync::atomic::AtomicBool;
use std::sync::Mutex;

use serde::{Deserialize, Serialize};
use tauri::{Manager, RunEvent, WindowEvent};
use tauri_plugin_shell::process::CommandChild;

mod sidecar;

/// Port i token wypisane przez sidecar w linii `READY {...}`.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct BackendInfo {
    pub port: u16,
    pub token: String,
}

#[derive(Default)]
pub struct SidecarState {
    pub info: Mutex<Option<BackendInfo>>,
    pub child: Mutex<Option<CommandChild>>,
    pub shutting_down: AtomicBool,
    pub failed: AtomicBool,
    pub stderr: Mutex<VecDeque<String>>,
}

#[tauri::command]
fn get_backend_info(state: tauri::State<'_, SidecarState>) -> Option<BackendInfo> {
    state.info.lock().unwrap().clone()
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(SidecarState::default())
        .invoke_handler(tauri::generate_handler![get_backend_info])
        .setup(|app| {
            sidecar::start(app.handle());
            Ok(())
        })
        .on_window_event(|window, event| {
            if matches!(event, WindowEvent::Destroyed) {
                sidecar::kill(window.app_handle());
            }
        })
        .build(tauri::generate_context!())
        .expect("nie udało się zbudować aplikacji Tauri")
        .run(|app, event| {
            if matches!(event, RunEvent::ExitRequested { .. } | RunEvent::Exit) {
                sidecar::kill(app);
            }
        });
}
