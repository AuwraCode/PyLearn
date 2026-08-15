import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

export interface BackendInfo {
  port: number;
  token: string;
}

export interface BackendFailure {
  message: string;
  stderr: string[];
}

interface BackendHandlers {
  onReady: (info: BackendInfo) => void;
  onFailed: (failure: BackendFailure) => void;
}

/**
 * Nasłuchuje handshake'u sidecara. Kolejność jest istotna: najpierw rejestracja
 * nasłuchu, potem odpytanie o stan — gdyby zdarzenie `backend-ready` padło
 * zanim WebView zdążył nasłuchiwać, dopytanie `get_backend_info` je nadrabia.
 */
export function subscribeBackend(handlers: BackendHandlers): () => void {
  let disposed = false;
  const unlistens: Array<() => void> = [];

  void (async () => {
    const onReady = await listen<BackendInfo>("backend-ready", (event) =>
      handlers.onReady(event.payload),
    );
    if (disposed) {
      onReady();
      return;
    }
    unlistens.push(onReady);

    const onFailed = await listen<BackendFailure>("backend-failed", (event) =>
      handlers.onFailed(event.payload),
    );
    if (disposed) {
      onFailed();
      return;
    }
    unlistens.push(onFailed);

    const info = await invoke<BackendInfo | null>("get_backend_info");
    if (info && !disposed) handlers.onReady(info);
  })();

  return () => {
    disposed = true;
    for (const unlisten of unlistens) unlisten();
  };
}
