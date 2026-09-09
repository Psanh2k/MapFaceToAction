"""Chrome マネージャーのテスト。"""

from unittest.mock import MagicMock, patch

from src.config import Config
from src.chrome_manager import ChromeManager


def test_is_running_detects_chrome():
    """Chrome プロセス検出テスト。"""
    config = Config()
    manager = ChromeManager(config)

    mock_proc = MagicMock()
    mock_proc.uids.return_value.real = manager._current_user
    mock_proc.name.return_value = "chrome"
    mock_proc.exe.return_value = "/opt/google/chrome/chrome"

    mock_proc.cmdline.return_value = ["/opt/google/chrome/chrome"]

    with patch.object(manager, "_get_terminate_targets", return_value=[mock_proc]):
        assert manager.is_running() is True


def test_is_running_no_chrome():
    """Chrome 未実行時の検出テスト。"""
    config = Config()
    manager = ChromeManager(config)

    with patch.object(manager, "_get_chrome_processes", return_value=[]):
        assert manager.is_running() is False


def test_terminate_when_not_running():
    """Test 6: Chrome 未実行 → エラーなし。"""
    config = Config()
    manager = ChromeManager(config)

    with patch.object(manager, "_get_terminate_targets", return_value=[]):
        result = manager.terminate()
        assert result is True


def test_dry_run_no_kill():
    """Test 9: DRY_RUN 時は Chrome を kill しない（main.py 側で制御）。"""
    config = Config()
    config.dry_run = True
    manager = ChromeManager(config)

    with patch.object(manager, "_get_terminate_targets", return_value=[]):
        assert manager.is_running() is False


def test_subprocess_not_in_main_only_targets():
    """renderer 等の子プロセスは main_only では kill 対象外。"""
    config = Config()
    config.chrome_kill_scope = "main_only"
    manager = ChromeManager(config)

    main_proc = MagicMock()
    main_proc.uids.return_value.real = manager._current_user
    main_proc.name.return_value = "chrome"
    main_proc.exe.return_value = "/opt/google/chrome/chrome"
    main_proc.cmdline.return_value = ["/opt/google/chrome/chrome"]

    renderer_proc = MagicMock()
    renderer_proc.uids.return_value.real = manager._current_user
    renderer_proc.name.return_value = "chrome"
    renderer_proc.exe.return_value = "/opt/google/chrome/chrome"
    renderer_proc.cmdline.return_value = [
        "/opt/google/chrome/chrome",
        "--type=renderer",
    ]

    assert manager._is_chrome_subprocess(renderer_proc) is True
    assert manager._is_chrome_subprocess(main_proc) is False

    with patch.object(
        manager,
        "_get_chrome_processes",
        return_value=[main_proc, renderer_proc],
    ):
        targets = manager._get_terminate_targets()
        assert targets == [main_proc]


def test_does_not_match_other_user():
    """他ユーザーの Chrome プロセスは対象外。"""
    config = Config()
    manager = ChromeManager(config)

    mock_proc = MagicMock()
    mock_proc.uids.return_value.real = 99999
    mock_proc.name.return_value = "chrome"

    assert manager._is_chrome_process(mock_proc) is False


def test_does_not_match_chromedriver():
    """chromedriver は対象外。"""
    config = Config()
    manager = ChromeManager(config)

    mock_proc = MagicMock()
    mock_proc.uids.return_value.real = manager._current_user
    mock_proc.name.return_value = "chromedriver"
    mock_proc.exe.return_value = "/usr/bin/chromedriver"

    assert manager._is_chrome_process(mock_proc) is False
