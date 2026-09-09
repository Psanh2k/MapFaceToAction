"""Chrome/Chromium プロセスの検出と終了。"""

from __future__ import annotations

import os
import signal
import time
from typing import List, Optional

import psutil

from src.config import Config
from src.logger import setup_logger


class ChromeManager:
    """Chrome プロセスの検出・終了を管理する。"""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._logger = setup_logger(level=config.log_level)
        self._current_user = os.getuid()

    def _get_cmdline(self, proc: psutil.Process) -> List[str]:
        """プロセスのコマンドラインを取得する。"""
        try:
            return proc.cmdline()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return []

    def _is_chrome_process(self, proc: psutil.Process) -> bool:
        """プロセスが対象 Chrome か判定する（現在ユーザーのみ）。"""
        allowed = [n.lower() for n in self._config.chrome_process_names]
        try:
            if proc.uids().real != self._current_user:
                return False

            name = proc.name().lower()
            if name in allowed:
                return True

            exe_basename = os.path.basename(proc.exe()).lower()
            if exe_basename in allowed:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return False
        return False

    def _is_chrome_subprocess(self, proc: psutil.Process) -> bool:
        """renderer/zygote 等の Chrome 子プロセスか。"""
        for arg in self._get_cmdline(proc):
            if arg.startswith("--type="):
                return True
        return False

    def _get_chrome_processes(self) -> List[psutil.Process]:
        """対象 Chrome プロセス一覧（全プロセス）。"""
        processes: List[psutil.Process] = []
        for proc in psutil.process_iter(["pid", "name", "uids"]):
            if self._is_chrome_process(proc):
                processes.append(proc)
        return processes

    def _get_terminate_targets(self) -> List[psutil.Process]:
        """終了対象 Chrome プロセス（サービストリガー時のみ使用）。"""
        processes = self._get_chrome_processes()
        if self._config.chrome_kill_scope == "all":
            return processes

        # main_only: メインプロセスのみ SIGTERM（子プロセスへ個別 kill しない）
        main_processes = [p for p in processes if not self._is_chrome_subprocess(p)]
        return main_processes

    def is_running(self) -> bool:
        """Chrome が実行中か（メインプロセス基準）。"""
        targets = self._get_terminate_targets()
        running = len(targets) > 0
        self._logger.debug("Chrome running: %s (main processes: %d)", running, len(targets))
        return running

    def terminate(self) -> bool:
        """SIGTERM で Chrome を終了する（サービストリガー専用）。"""
        targets = self._get_terminate_targets()
        if not targets:
            self._logger.info("Chrome is not running")
            return True

        self._logger.info(
            "Service trigger: terminating Chrome (%d main process(es), scope=%s)",
            len(targets),
            self._config.chrome_kill_scope,
        )
        self._logger.info("Attempting graceful termination (SIGTERM)")

        for proc in targets:
            try:
                cmdline = " ".join(self._get_cmdline(proc)[:3])
                proc.send_signal(signal.SIGTERM)
                self._logger.debug(
                    "Sent SIGTERM to PID %d (%s) %s",
                    proc.pid,
                    proc.name(),
                    cmdline,
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
                self._logger.warning("Failed to SIGTERM PID %d: %s", proc.pid, exc)

        return self._wait_for_exit()

    def force_kill(self) -> bool:
        """SIGKILL で Chrome を強制終了する。"""
        targets = self._get_terminate_targets()
        if not targets:
            return True

        self._logger.warning(
            "Force killing Chrome (%d process(es))", len(targets)
        )

        for proc in targets:
            try:
                proc.send_signal(signal.SIGKILL)
                self._logger.debug("Sent SIGKILL to PID %d", proc.pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
                self._logger.warning("Failed to SIGKILL PID %d: %s", proc.pid, exc)

        return self._wait_for_exit(timeout=3)

    def terminate_gracefully(self) -> bool:
        """SIGTERM → 待機 → 必要なら SIGKILL。"""
        if not self.is_running():
            self._logger.info("Chrome is not running, nothing to terminate")
            return True

        if not self.terminate():
            self._logger.warning("Chrome did not exit after SIGTERM, using SIGKILL")
            return self.force_kill()

        self._logger.info("Chrome terminated successfully")
        return True

    def _wait_for_exit(self, timeout: Optional[int] = None) -> bool:
        """プロセス終了を待つ。"""
        wait_timeout = timeout or self._config.chrome_terminate_timeout
        deadline = time.monotonic() + wait_timeout

        while time.monotonic() < deadline:
            if not self.is_running():
                return True
            time.sleep(0.2)

        return not self.is_running()
