"""LLM local isolé dans un sous-processus (évite un segfault native de tuer l’UI)."""

from __future__ import annotations

import multiprocessing as mp
import os
import queue
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _worker_loop(model_path: str, n_ctx: int, jobs: mp.Queue, results: mp.Queue) -> None:
    """Charge le GGUF une fois, répond aux jobs {id, prompt, max_tokens}."""
    try:
        from llama_cpp import Llama

        llm = Llama(
            model_path=model_path,
            n_ctx=n_ctx,
            n_gpu_layers=0,  # CPU : plus stable sur macOS que Metal
            verbose=False,
        )
        results.put({"type": "ready"})
    except Exception as exc:  # noqa: BLE001
        results.put({"type": "error", "error": str(exc)})
        return

    while True:
        job = jobs.get()
        if job is None or job.get("type") == "stop":
            break
        jid = job.get("id")
        prompt = job.get("prompt", "")
        max_tokens = int(job.get("max_tokens", 60))
        try:
            out = llm(
                prompt,
                max_tokens=max_tokens,
                temperature=0.0,
                stop=["<|im_end|>", "<|im_start|>"],
            )
            text = (out["choices"][0]["text"] or "").strip()
            results.put({"type": "ok", "id": jid, "text": text})
        except Exception as exc:  # noqa: BLE001
            results.put({"type": "ok", "id": jid, "text": "", "error": str(exc)})


@dataclass
class LlmBridge:
    model_path: Path
    n_ctx: int = 2048
    _proc: mp.Process | None = None
    _jobs: Any = None
    _results: Any = None
    _lock: threading.Lock = None  # type: ignore[assignment]
    _pending: dict[str, str] = None  # type: ignore[assignment]
    _ready: bool = False
    _error: str = ""
    _req_id: int = 0

    def __post_init__(self) -> None:
        self._lock = threading.Lock()
        self._pending = {}

    @property
    def disponible(self) -> bool:
        return self._ready and self._proc is not None and self._proc.is_alive()

    @property
    def statut(self) -> str:
        if self._error:
            return f"erreur : {self._error}"
        if self.disponible:
            return "actif (local)"
        if self._proc is not None and self._proc.is_alive():
            return "chargement…"
        return "indisponible"

    def start(self) -> None:
        if not self.model_path.exists():
            self._error = f"GGUF manquant : {self.model_path.name}"
            self._ready = False
            return
        self._stop_silent()
        ctx = mp.get_context("spawn")
        self._jobs = ctx.Queue()
        self._results = ctx.Queue()
        self._proc = ctx.Process(
            target=_worker_loop,
            args=(str(self.model_path), self.n_ctx, self._jobs, self._results),
            daemon=True,
        )
        self._proc.start()
        # Attente ready (chargement modèle)
        deadline = time.time() + 120
        while time.time() < deadline:
            try:
                msg = self._results.get(timeout=1.0)
            except queue.Empty:
                if self._proc is None or not self._proc.is_alive():
                    self._error = "processus LLM arrêté au démarrage"
                    self._ready = False
                    return
                continue
            if msg.get("type") == "ready":
                self._ready = True
                self._error = ""
                return
            if msg.get("type") == "error":
                self._error = str(msg.get("error", "chargement impossible"))
                self._ready = False
                return
        self._error = "délai dépassé au chargement du LLM"
        self._ready = False

    def _stop_silent(self) -> None:
        if self._jobs is not None:
            try:
                self._jobs.put({"type": "stop"})
            except Exception:
                pass
        if self._proc is not None and self._proc.is_alive():
            self._proc.join(timeout=2)
            if self._proc.is_alive():
                self._proc.terminate()
        self._proc = None
        self._ready = False

    def _drain(self) -> None:
        if self._results is None:
            return
        while True:
            try:
                msg = self._results.get_nowait()
            except queue.Empty:
                break
            if msg.get("type") == "ok" and "id" in msg:
                self._pending[str(msg["id"])] = str(msg.get("text") or "")

    def generate(self, prompt: str, *, max_tokens: int = 60, timeout: float = 45.0) -> str:
        """Inférence synchronisée ; redémarre le worker s’il est mort."""
        with self._lock:
            if not self.disponible:
                self.start()
            if not self.disponible or self._jobs is None:
                return ""
            self._req_id += 1
            jid = str(self._req_id)
            try:
                self._jobs.put(
                    {"id": jid, "prompt": prompt, "max_tokens": max_tokens}
                )
            except Exception:
                self._ready = False
                return ""
            deadline = time.time() + timeout
            while time.time() < deadline:
                self._drain()
                if jid in self._pending:
                    return self._pending.pop(jid)
                if self._proc is None or not self._proc.is_alive():
                    self._ready = False
                    self._error = "processus LLM interrompu (segfault isolé)"
                    return ""
                time.sleep(0.05)
            return ""


_bridge: LlmBridge | None = None
_bridge_lock = threading.Lock()


def get_llm_bridge(model_path: Path, *, force: bool = False) -> LlmBridge:
    global _bridge
    with _bridge_lock:
        if _bridge is None or force:
            _bridge = LlmBridge(model_path=model_path)
            _bridge.start()
        return _bridge


def llm_obligatoire() -> bool:
    """Par défaut le LLM est requis pour la démo (utilité IA)."""
    return os.environ.get("CISIA_LLM", "1").strip() != "0"
