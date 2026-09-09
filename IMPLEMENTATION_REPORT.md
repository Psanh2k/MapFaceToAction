# BÁO CÁO TRIỂN KHAI – Face Chrome Killer

**Ngày:** 2026-09-09  
**Môi trường:** Ubuntu 24.04 LTS, Python 3.12.3, Linux 6.17.0-22-generic

---

## 1. Kết quả kiểm tra môi trường (Phase 1)

| Hạng mục | Kết quả |
|----------|---------|
| OS | Ubuntu 24.04 LTS (noble) |
| Python | 3.12.3 |
| Webcam | Không có `/dev/video*` trên máy hiện tại |
| Chrome | Google Chrome 149.0.7827.155 tại `/usr/bin/google-chrome`, process `chrome` |
| systemd user | Khả dụng (systemd 255) |

**Lưu ý:** Máy dev không có webcam vật lý. Module camera xử lý graceful retry; cần webcam thật để test đăng ký/nhận diện mặt.

---

## 2. Files đã tạo

```
MapFaceToAction/
├── main.py
├── register.py
├── install.sh
├── uninstall.sh
├── requirements.txt
├── .env.example
├── .env
├── .gitignore
├── README.md
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── logger.py
│   ├── camera.py
│   ├── face_recognition_service.py
│   ├── chrome_manager.py
│   └── state_machine.py
├── tests/
│   ├── conftest.py
│   ├── test_config.py
│   ├── test_camera.py
│   ├── test_face_recognition.py
│   ├── test_chrome_manager.py
│   └── test_state_machine.py
├── systemd/face-chrome-killer.service
├── data/.gitkeep
└── logs/.gitkeep
```

---

## 3. Dependencies đã cài

| Package | Version |
|---------|---------|
| opencv-python | 5.0.0.93 |
| face-recognition | 1.3.0 |
| dlib | 20.0.1 |
| numpy | 2.5.3 |
| python-dotenv | 1.2.3 |
| psutil | 7.2.2 |
| pytest | 9.1.1 |
| setuptools | 80.10.2 (<81, cần cho pkg_resources) |

**Vấn đề đã xử lý:** `setuptools>=81` loại bỏ `pkg_resources`, khiến `face_recognition_models` lỗi. Đã pin `setuptools<81.0.0` trong `requirements.txt`.

---

## 4. Thay đổi hệ thống

- Tạo virtualenv: `.venv/`
- Cài systemd user service: `~/.config/systemd/user/face-chrome-killer.service`
- Service đã enable và verify (active/running, retry camera khi không có thiết bị)
- Service đã stop sau khi verify

---

## 5. Lệnh chạy

```bash
# Cài đặt
./install.sh

# Đăng ký khuôn mặt (cần webcam)
source .venv/bin/activate
python register.py

# Test DRY_RUN (không kill Chrome)
DRY_RUN=true python main.py

# Test camera
python main.py --test-camera

# Test Chrome detection
python main.py --test-chrome

# Production
# Sửa .env: DRY_RUN=false
systemctl --user enable --now face-chrome-killer.service

# Unit tests
pytest
```

---

## 6. Cách hoạt động – Đăng ký khuôn mặt

1. `register.py` mở webcam, hiển thị preview OpenCV
2. Thu 15 mẫu (cấu hình `REGISTRATION_SAMPLE_COUNT`)
3. Validate: đúng 1 mặt, đủ lớn, nhất quán giữa các mẫu
4. Tính trung bình embedding → lưu `data/face_encoding.pkl` (chmod 600)
5. **Không** lưu video/ảnh gốc

---

## 7. Cách hoạt động – Kill Chrome

1. `main.py` đọc frame @ ~10 FPS, nhận diện mỗi 300ms
2. State machine: NO_FACE → FACE_DETECTED → MATCHING → TRIGGERED
3. Cần match liên tục `REQUIRED_MATCH_SECONDS` (mặc định 2s)
4. Nhiều mặt → reset timer
5. Khi trigger: `ChromeManager.is_running()` → SIGTERM → chờ 5s → SIGKILL nếu cần
6. Chỉ kill process của user hiện tại, tên khớp config
7. `DRY_RUN=true` → chỉ log "Would terminate Chrome"
8. Cooldown 30s sau trigger

---

## 8. Kết quả test

### Unit tests (pytest)

```
27 passed, 1 warning in 1.77s
```

| Test | Mô tả | Kết quả |
|------|-------|---------|
| Test 1 | No face → no trigger | PASS |
| Test 2 | Unknown face → no trigger | PASS |
| Test 3 | Brief match → no trigger | PASS |
| Test 4 | Continuous match → trigger | PASS |
| Test 5 | Two faces → no trigger | PASS |
| Test 6 | Chrome not running → no error | PASS |
| Test 7 | Cooldown prevents retrigger | PASS |
| Test 8 | Camera unavailable → retry | PASS |
| Test 9 | DRY_RUN → no kill | PASS |

### Manual / integration

| Kiểm tra | Kết quả |
|----------|---------|
| Chrome detection | PASS – phát hiện Chrome đang chạy |
| DRY_RUN mode | PASS – log "Would terminate", không kill |
| Camera test | FAIL expected – không có thiết bị, retry graceful |
| Main loop integration | PASS – load encoding, retry camera |
| systemd service | PASS – active, log journalctl OK |

---

## 9. Definition of Done

| Mục | Trạng thái |
|-----|-----------|
| Webcam works | ⚠️ Code OK, chưa test với webcam thật |
| Face registration works | ⚠️ Code OK, cần webcam |
| Face encoding persisted | ✅ |
| Registered face recognized | ✅ (unit test) |
| Unknown face rejected | ✅ |
| Multiple faces no trigger | ✅ |
| Continuous matching required | ✅ |
| Chrome process detected | ✅ |
| Chrome terminated gracefully | ✅ (code + test mock; chưa kill thật) |
| DRY_RUN works | ✅ |
| Camera failure handled | ✅ |
| Chrome-not-running handled | ✅ |
| CPU usage reasonable | ✅ (5-10 FPS, resize 0.25x) |
| Unit tests pass | ✅ 27/27 |
| systemd user service works | ✅ |
| Service auto restarts | ✅ (Restart=on-failure) |
| README complete | ✅ |
| No video stored | ✅ |
| No network | ✅ |
| No root required | ✅ |

---

## 10. Hạn chế đã biết

1. **Không có webcam trên máy dev** – không thể test end-to-end đăng ký/nhận diện thực tế
2. **dlib build chậm** (~6 phút) – cần `cmake build-essential libopenblas-dev`
3. **setuptools pin** – phải giữ `<81` cho đến khi `face_recognition_models` cập nhật
4. **OpenCV 5.x** – hoạt động OK nhưng có warning khi không có camera

---

## 11. Cải tiến đề xuất

1. Thêm backend nhận diện thay thế (MediaPipe, InsightFace) để giảm phụ thuộc dlib
2. Hỗ trợ `config.yaml` ngoài `.env`
3. GUI system tray thay vì chỉ chạy nền
4. Multi-user profile (nhiều face encoding)
5. Notification desktop khi trigger thay vì im lặng

---

_Báo cáo triển khai hoàn tất theo plan face-chrome-killer.md_
