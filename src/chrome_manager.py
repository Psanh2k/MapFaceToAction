"""Chrome/Chromium プロセスの検出と終了。"""

from __future__ import annotations

import os
import re
import shutil
import signal
import subprocess
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

    def _chrome_class_match(self, wm_class: str) -> bool:
        """ウィンドウクラスが Chrome 対象か。"""
        wm_lower = wm_class.lower()
        for name in self._config.chrome_window_classes:
            if name.lower() in wm_lower:
                return True
        return "chrome" in wm_lower or "chromium" in wm_lower

    def _parse_gdbus_int_output(self, stdout: str) -> int:
        """gdbus 出力から int 値を抽出する。"""
        match = re.search(r"int32\s+(-?\d+)|\((-?\d+),", stdout)
        if not match:
            return 0
        return int(match.group(1) or match.group(2))

    def _parse_gdbus_eval_success(self, stdout: str) -> bool:
        """Shell.Eval の success フラグを解析する。"""
        return stdout.strip().startswith("(true,")

    def _minimize_extension_dir(self) -> str:
        """ユーザー拡張のインストール先。"""
        return os.path.expanduser(
            "~/.local/share/gnome-shell/extensions/"
            "face-chrome-killer-minimize@mapface"
        )

    def is_minimize_extension_installed(self) -> bool:
        """GNOME 拡張ファイルがディスク上にあるか。"""
        ext_dir = self._minimize_extension_dir()
        return (
            os.path.isfile(os.path.join(ext_dir, "extension.js"))
            and os.path.isfile(os.path.join(ext_dir, "metadata.json"))
        )

    def is_minimize_extension_registered(self) -> bool:
        """GNOME Shell が拡張を認識しているか。"""
        if shutil.which("gnome-extensions") is None:
            return False
        try:
            result = subprocess.run(
                ["gnome-extensions", "list"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if result.returncode != 0:
                return False
            return "face-chrome-killer-minimize@mapface" in result.stdout.splitlines()
        except subprocess.TimeoutExpired:
            return False

    def is_minimize_extension_available(self) -> bool:
        """GNOME 拡張 D-Bus が利用可能か（最小化は実行しない）。"""
        try:
            result = subprocess.run(
                [
                    "gdbus", "introspect", "--session",
                    "--dest", "org.gnome.Shell",
                    "--object-path", "/org/mapface/ChromeMinimize",
                    "--recurse",
                ],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            return (
                result.returncode == 0
                and "MinimizeChrome" in result.stdout
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def get_minimize_extension_status(self) -> str:
        """最小化拡張の状態を人間向け文字列で返す。"""
        if not self.is_minimize_extension_installed():
            return "not_installed"
        if not self.is_minimize_extension_registered():
            return "installed_not_loaded"
        if not self.is_minimize_extension_available():
            return "registered_not_active"
        return "ready"

    def _minimize_via_extension(self) -> bool:
        """GNOME Shell 拡張 D-Bus 経由で Chrome を最小化。"""
        try:
            result = subprocess.run(
                [
                    "gdbus", "call", "--session",
                    "--dest", "org.gnome.Shell",
                    "--object-path", "/org/mapface/ChromeMinimize",
                    "--method", "org.mapface.ChromeMinimize.MinimizeChrome",
                ],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if result.returncode != 0:
                self._logger.debug(
                    "Extension minimize unavailable: %s",
                    result.stderr.strip(),
                )
                return False

            count = self._parse_gdbus_int_output(result.stdout)
            if count > 0:
                self._logger.debug("Minimized %d Chrome window(s) via extension", count)
                return True

            self._logger.debug("Extension minimize returned 0 windows")
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            self._logger.debug("Extension D-Bus call failed: %s", exc)
        return False

    def _minimize_via_gnome_shell(self) -> bool:
        """GNOME Shell Eval（GNOME 46 では通常無効）。"""
        class_checks = " || ".join(
            f"cls.indexOf('{name.lower()}') >= 0"
            for name in self._config.chrome_window_classes
        )
        script = (
            "global.get_window_actors().forEach(function (w) {"
            "  var mw = w.meta_window;"
            "  if (!mw) return;"
            "  var cls = (mw.get_wm_class() || '').toLowerCase();"
            f"  if ({class_checks}) {{ mw.minimize(); }}"
            "});"
            "1;"
        )
        try:
            result = subprocess.run(
                [
                    "gdbus", "call", "--session",
                    "--dest", "org.gnome.Shell",
                    "--object-path", "/org/gnome/Shell",
                    "--method", "org.gnome.Shell.Eval",
                    script,
                ],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if result.returncode == 0 and self._parse_gdbus_eval_success(result.stdout):
                return True
            self._logger.debug(
                "Shell.Eval minimize failed: %s",
                result.stdout.strip() or result.stderr.strip(),
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            self._logger.debug("gdbus not available: %s", exc)
        return False

    def _minimize_via_xdotool(self) -> bool:
        """X11 上で xdotool により Chrome を最小化。"""
        if shutil.which("xdotool") is None:
            return False

        minimized = False
        for class_name in self._config.chrome_window_classes:
            try:
                result = subprocess.run(
                    [
                        "xdotool", "search", "--class", class_name,
                        "windowminimize",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                if result.returncode == 0 and result.stdout.strip():
                    minimized = True
            except subprocess.TimeoutExpired:
                self._logger.warning("xdotool timeout for class %s", class_name)
        return minimized

    def _minimize_via_wmctrl(self) -> bool:
        """wmctrl で Chrome ウィンドウを hidden/minimize。"""
        if shutil.which("wmctrl") is None:
            return False

        try:
            result = subprocess.run(
                ["wmctrl", "-lx"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if result.returncode != 0:
                return False

            minimized = False
            for line in result.stdout.splitlines():
                parts = line.split(None, 4)
                if len(parts) < 5:
                    continue
                window_id, wm_class = parts[0], parts[2]
                if not self._chrome_class_match(wm_class):
                    continue
                hide = subprocess.run(
                    ["wmctrl", "-i", "-r", window_id, "-b", "add,hidden"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                if hide.returncode == 0:
                    minimized = True
            return minimized
        except subprocess.TimeoutExpired:
            self._logger.warning("wmctrl timeout")
            return False

    def minimize(self) -> bool:
        """Chrome ウィンドウを最小化する（動体検知トリガー専用）。"""
        if not self.is_running():
            self._logger.info("Chrome is not running, skipping minimize")
            return True

        self._logger.info("Minimizing Chrome windows")

        backends = (
            ("gnome_extension", self._minimize_via_extension),
            ("gnome_shell", self._minimize_via_gnome_shell),
            ("xdotool", self._minimize_via_xdotool),
            ("wmctrl", self._minimize_via_wmctrl),
        )
        for backend_name, minimize_fn in backends:
            if minimize_fn():
                self._logger.info("Chrome minimized via %s", backend_name)
                return True

        status = self.get_minimize_extension_status()
        if status == "not_installed":
            self._logger.warning(
                "Could not minimize Chrome (Wayland). "
                "Run: ./scripts/install-extension.sh then log out/in. "
                "Test: python main.py --test-chrome-minimize"
            )
        elif status == "installed_not_loaded":
            self._logger.warning(
                "GNOME extension is installed but not loaded. "
                "Log out and log back in (or reboot), then retry. "
                "Verify: gnome-extensions list --enabled | grep face-chrome-killer-minimize"
            )
        elif status == "registered_not_active":
            self._logger.warning(
                "GNOME extension is registered but D-Bus API is unavailable. "
                "Enable it: gnome-extensions enable face-chrome-killer-minimize@mapface "
                "then log out/in."
            )
        else:
            self._logger.warning(
                "Could not minimize Chrome. "
                "Ensure Chrome windows are open and retry."
            )
        return False
