# Face Chrome Killer

Linux デスクトップ向けバックグラウンドアプリ。Webカメラで登録済みユーザーの顔を検出し、一定時間連続で一致した場合に Google Chrome / Chromium を終了します。

## 機能

- Webカメラからの顔検出・認識
- 登録済みユーザーのみトリガー
- 連続マッチ検証（誤検知防止）
- 複数顔検出時はトリガーしない
- Chrome の SIGTERM → SIGKILL による graceful 終了
- DRY_RUN モード（テスト用）
- systemd ユーザーサービス対応

## 必要条件

- Ubuntu Linux (24.04 LTS 推奨)
- Python 3.10+
- Webcam (`/dev/video0`)
- Google Chrome または Chromium

### ネイティブ依存（dlib ビルド用）

```bash
sudo apt install cmake build-essential libopenblas-dev
```

## インストール

```bash
git clone <repo-url>
cd MapFaceToAction
./install.sh
```

## 顔登録

```bash
source .venv/bin/activate
python register.py
```

カメラプレビューが表示されます。顔をカメラに向け、15サンプルが自動収集されるまで待ちます。`Q` でキャンセル。

登録後 `data/face_encoding.pkl` にエンコーディングが保存されます（顔画像は保存しません）。

## テスト

### DRY_RUN モード（Chrome を kill しない）

```bash
DRY_RUN=true python main.py
```

### カメラテスト

```bash
python main.py --test-camera
```

### Chrome プロセス検出テスト

```bash
python main.py --test-chrome
```

実際に Chrome を終了するテスト（注意）:

```bash
DRY_RUN=false python main.py --test-chrome --force-chrome-kill
```

## 本番起動

`.env` で `DRY_RUN=false` に設定後:

```bash
systemctl --user enable --now face-chrome-killer.service
```

## ステータス確認

```bash
systemctl --user status face-chrome-killer.service
```

## ログ確認

```bash
journalctl --user -u face-chrome-killer.service -f
```

アプリログファイル: `logs/face_chrome_killer.log`

## 停止

```bash
systemctl --user stop face-chrome-killer.service
```

## 無効化

```bash
systemctl --user disable face-chrome-killer.service
```

## アンインストール

```bash
./uninstall.sh
```

顔データ (`data/face_encoding.pkl`) は自動削除されません。

## 設定 (.env)

| 変数 | デフォルト | 説明 |
|------|-----------|------|
| `CAMERA_INDEX` | 0 | カメラデバイス番号 |
| `CAMERA_WIDTH` | 640 | キャプチャ幅 |
| `CAMERA_HEIGHT` | 480 | キャプチャ高さ |
| `CAMERA_FPS` | 10 | キャプチャ FPS |
| `FACE_MATCH_THRESHOLD` | 0.50 | 顔一致しきい値（距離） |
| `REQUIRED_MATCH_SECONDS` | 2 | トリガーに必要な連続マッチ秒数 |
| `REQUIRE_SINGLE_FACE` | true | 単一顔のみトリガー |
| `RECOGNITION_INTERVAL_MS` | 300 | 認識実行間隔 (ms) |
| `CHROME_PROCESS_NAMES` | google-chrome,chrome,... | 対象プロセス名 |
| `CHROME_TERMINATE_TIMEOUT` | 5 | SIGTERM 待機秒数 |
| `TRIGGER_COOLDOWN_SECONDS` | 30 | トリガー後クールダウン |
| `DRY_RUN` | true | true=Chrome を kill しない |
| `LOG_LEVEL` | INFO | ログレベル |

## 手動 QA チェックリスト

### カメラ

- [ ] カメラが開く
- [ ] カメラが正しく閉じる
- [ ] カメラ切断が処理される
- [ ] 誤ったカメラ index が処理される

### 認識

- [ ] 登録済み顔が検出される
- [ ] 未知の顔が拒否される
- [ ] 複数顔が拒否される
- [ ] 一時的な顔検出ではトリガーしない
- [ ] 連続マッチで正しくトリガーする

### Chrome

- [ ] 実行中の Chrome が検出される
- [ ] Chrome が graceful に終了する
- [ ] 必要時に force kill が動作する
- [ ] Chromium が設定でサポートされる
- [ ] 他ユーザーのブラウザプロセスは kill されない

### サービス

- [ ] サービスが起動する
- [ ] クラッシュ後に再起動する
- [ ] ログイン後に実行される
- [ ] ログが確認できる
- [ ] サービスが正常に停止できる

## プライバシー

- カメラ映像はネットワークに送信されません
- 通常動作中に映像は保存されません
- 顔エンコーディング（数値ベクトル）のみローカル保存
- `data/` と `.env` は `.gitignore` 対象

## プロジェクト構成

```
├── main.py                  # メイン監視プロセス
├── register.py              # 顔登録
├── src/
│   ├── camera.py            # カメラ管理
│   ├── face_recognition_service.py
│   ├── chrome_manager.py    # Chrome プロセス管理
│   ├── state_machine.py     # 状態遷移
│   ├── config.py            # 設定
│   └── logger.py            # ログ
├── tests/                   # ユニットテスト
├── systemd/                 # systemd サービス定義
├── data/                    # 顔エンコーディング（gitignore）
└── logs/                    # アプリログ
```

## ユニットテスト

```bash
source .venv/bin/activate
pytest
```
