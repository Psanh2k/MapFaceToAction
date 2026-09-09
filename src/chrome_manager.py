"""Chrome/Chromium プロセスの検出と終了。"""

from __future__ import annotations

import os
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

    def _is_chrome_process(self, proc: psutil.Process) -> bool:
        """プロセスが対象 Chrome か判定する（現在ユーザーのみ）。"""
        allowed = [n.lower() for n in self._config.chrome_process_names]
        try:
            if proc.uids().real != self._current_user:
                return False

            name = proc.name().lower()
            if name in allowed:
                return True

            # 実行ファイル名でも判定（google-chrome ラッパー等）
            exe_basename = os.path.basename(proc.exe()).lower()
            if exe_basename in allowed:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return False
        return False

    def _get_chrome_processes(self) -> List[psutil.Process]:
        """対象 Chrome プロセス一覧を返す。"""
        processes: List[psutil.Process] = []
        for proc in psutil.process_iter(["pid", "name", "uids"]):
            if self._is_chrome_process(proc):
                processes.append(proc)
        return processes

    def is_running(self) -> bool:
        """Chrome が実行中か。"""
        running = len(self._get_chrome_processes()) > 0
        self._logger.debug("Chrome running: %s", running)
        return running

    def terminate(self) -> bool:
        """SIGTERM で Chrome を終了する。"""
        processes = self._get_chrome_processes()
        if not processes:
            self._logger.info("Chrome is not running")
            return True

        self._logger.info("Chrome detected (%d processes)", len(processes))
        self._logger.info("Attempting graceful termination (SIGTERM)")

        for proc in processes:
            try:
                proc.send_signal(signal.SIGTERM)
                self._logger.debug("Sent SIGTERM to PID %d (%s)", proc.pid, proc.name())
            except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
                self._logger.warning("Failed to SIGTERM PID %d: %s", proc.pid, exc)

        return self._wait_for_exit()

    def force_kill(self) -> bool:
        """SIGKILL で Chrome を強制終了する。"""
        processes = self._get_chrome_processes()
        if not processes:
            return True

        self._logger.warning("Force killing Chrome (%d processes)", len(processes))

        for proc in processes:
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
