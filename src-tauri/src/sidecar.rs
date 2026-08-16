use std::io::{Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::sync::atomic::Ordering;
use std::time::Duration;

use serde::Serialize;
use tauri::{AppHandle, Emitter, Manager};
use tauri_plugin_shell::process::CommandEvent;
use tauri_plugin_shell::ShellExt;

use crate::{BackendInfo, SidecarState};

const READY_TIMEOUT_SECS: u64 = 15;
const HEARTBEAT_INTERVAL_SECS: u64 = 20;
const HEARTBEAT_MAX_FAILURES: u32 = 3;
const STDERR_KEEP_LINES: usize = 200;

#[derive(Clone, Serialize)]
struct BackendFailure {
    message: String,
    stderr: Vec<String>,
}

pub fn start(app: &AppHandle) {
    // Tryb deweloperski: backend odpalony ręcznie (uvicorn na stałym porcie),
    // żeby dało się debugować Pythona bez przebudowy binarki PyInstallera.
    if std::env::var("TUTOR_DEV_BACKEND").as_deref() == Ok("1") {
        let info = BackendInfo {
            port: 8756,
            token: "dev".into(),
        };
        *app.state::<SidecarState>().info.lock().unwrap() = Some(info.clone());
        let _ = app.emit("backend-ready", &info);
        return;
    }
    if let Err(message) = spawn(app) {
        fail(app, message);
    }
}

fn spawn(app: &AppHandle) -> Result<(), String> {
    let data_dir = app
        .path()
        .app_data_dir()
        .map_err(|e| format!("Nie można ustalić katalogu danych aplikacji: {e}"))?;
    std::fs::create_dir_all(&data_dir)
        .map_err(|e| format!("Nie można utworzyć katalogu danych aplikacji: {e}"))?;
    let db_path = data_dir.join("pylearn.db");

    let command = app
        .shell()
        .sidecar("tutor-sidecar")
        .map_err(|e| format!("Nie znaleziono binarki sidecara: {e}"))?
        // Aplikacja z Findera startuje z cwd "/", które dziedziczą dzieci
        // (w tym claude CLI) — jawny katalog roboczy we własnych danych
        // aplikacji ogranicza prompty TCC macOS o dostęp do katalogów.
        .current_dir(data_dir.clone())
        .env("TUTOR_DB_PATH", db_path.to_string_lossy().to_string());
    let (mut rx, child) = command
        .spawn()
        .map_err(|e| format!("Nie udało się uruchomić sidecara: {e}"))?;
    *app.state::<SidecarState>().child.lock().unwrap() = Some(child);

    let reader_app = app.clone();
    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            handle_event(&reader_app, event);
        }
    });

    let timeout_app = app.clone();
    tauri::async_runtime::spawn(async move {
        tokio::time::sleep(Duration::from_secs(READY_TIMEOUT_SECS)).await;
        let state = timeout_app.state::<SidecarState>();
        let ready = state.info.lock().unwrap().is_some();
        if !ready && !state.shutting_down.load(Ordering::SeqCst) {
            fail(
                &timeout_app,
                format!("Backend nie zgłosił gotowości w ciągu {READY_TIMEOUT_SECS} s."),
            );
        }
    });

    Ok(())
}

fn handle_event(app: &AppHandle, event: CommandEvent) {
    let state = app.state::<SidecarState>();
    match event {
        CommandEvent::Stdout(bytes) => {
            let line = String::from_utf8_lossy(&bytes);
            if let Some(json) = line.trim().strip_prefix("READY ") {
                match serde_json::from_str::<BackendInfo>(json) {
                    Ok(info) => on_ready(app, info),
                    Err(e) => fail(app, format!("Sidecar zgłosił niepoprawną linię READY: {e}")),
                }
            }
        }
        CommandEvent::Stderr(bytes) => {
            push_stderr(&state, String::from_utf8_lossy(&bytes).trim_end().to_string());
        }
        CommandEvent::Error(message) => {
            push_stderr(&state, format!("[błąd procesu] {message}"));
        }
        CommandEvent::Terminated(payload) => {
            if state.shutting_down.load(Ordering::SeqCst) {
                return;
            }
            let code = payload
                .code
                .map_or_else(|| "brak kodu".to_string(), |c| c.to_string());
            let was_ready = state.info.lock().unwrap().is_some();
            let message = if was_ready {
                format!("Backend niespodziewanie zakończył pracę (kod wyjścia: {code}).")
            } else {
                format!("Sidecar zakończył się przed zgłoszeniem gotowości (kod wyjścia: {code}).")
            };
            fail(app, message);
        }
        _ => {}
    }
}

fn on_ready(app: &AppHandle, info: BackendInfo) {
    *app.state::<SidecarState>().info.lock().unwrap() = Some(info.clone());
    let _ = app.emit("backend-ready", &info);
    start_heartbeat(app.clone(), info);
}

/// Odpytuje /health co 20 s: karmi watchdoga Pythona (który kończy proces po 60 s
/// ciszy, gdyby powłoka zniknęła bez sprzątania) i wykrywa padnięty backend.
fn start_heartbeat(app: AppHandle, info: BackendInfo) {
    std::thread::spawn(move || {
        let mut failures: u32 = 0;
        loop {
            std::thread::sleep(Duration::from_secs(HEARTBEAT_INTERVAL_SECS));
            if app.state::<SidecarState>().shutting_down.load(Ordering::SeqCst) {
                return;
            }
            failures = if health_check(info.port, &info.token) {
                0
            } else {
                failures + 1
            };
            if failures >= HEARTBEAT_MAX_FAILURES {
                fail(&app, "Backend przestał odpowiadać na /health.".to_string());
                return;
            }
        }
    });
}

// Minimalny klient HTTP na gołym TcpStream — jedno żądanie GET co 20 s na loopbacku
// nie uzasadnia wciągania pełnego klienta HTTP do zależności.
fn health_check(port: u16, token: &str) -> bool {
    let addr = SocketAddr::from(([127, 0, 0, 1], port));
    let Ok(mut stream) = TcpStream::connect_timeout(&addr, Duration::from_secs(3)) else {
        return false;
    };
    let _ = stream.set_read_timeout(Some(Duration::from_secs(3)));
    let _ = stream.set_write_timeout(Some(Duration::from_secs(3)));
    let request = format!(
        "GET /health HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nX-Session-Token: {token}\r\nConnection: close\r\n\r\n"
    );
    if stream.write_all(request.as_bytes()).is_err() {
        return false;
    }
    let mut response = String::new();
    let _ = stream.read_to_string(&mut response);
    response.starts_with("HTTP/1.1 200")
}

fn push_stderr(state: &SidecarState, line: String) {
    if line.is_empty() {
        return;
    }
    let mut buffer = state.stderr.lock().unwrap();
    if buffer.len() >= STDERR_KEEP_LINES {
        buffer.pop_front();
    }
    buffer.push_back(line);
}

fn fail(app: &AppHandle, message: String) {
    let state = app.state::<SidecarState>();
    // Pierwszy błąd wygrywa — kolejne nie nadpisują ekranu diagnostycznego.
    if state.failed.swap(true, Ordering::SeqCst) {
        return;
    }
    let stderr: Vec<String> = state.stderr.lock().unwrap().iter().cloned().collect();
    let _ = app.emit("backend-failed", &BackendFailure { message, stderr });
}

pub fn kill(app: &AppHandle) {
    let state = app.state::<SidecarState>();
    state.shutting_down.store(true, Ordering::SeqCst);
    let child = state.child.lock().unwrap().take();
    if let Some(child) = child {
        // Bootloader PyInstallera (--onefile) przekazuje dziecku SIGTERM, ale nie
        // SIGKILL — najpierw czyste zejście całego drzewa, potem SIGKILL jako backstop.
        #[cfg(unix)]
        {
            let _ = std::process::Command::new("kill")
                .args(["-TERM", &child.pid().to_string()])
                .status();
            std::thread::sleep(Duration::from_millis(400));
        }
        let _ = child.kill();
    }
}
