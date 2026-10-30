# Nâng cấp v1 → v2

1. Dừng API v1 để tránh ghi đồng thời khi đổi schema.
2. Sao lưu PostgreSQL bằng pg_dump -Fc và giữ mã nguồn v1.
3. Kiểm tra DATABASE_URL đúng đích nâng cấp.
4. Có thể chạy `python scripts/verify_refactor.py --capture` khi DB ở revision
   0001. Snapshot nằm trong .runtime, chứa dữ liệu riêng, không commit/chia sẻ.

## Migration 0002

- Tạo vocabulary dùng chung; chỉ bỏ bản sao nghĩa/ghi chú khi khớp chính xác
  nội dung chuẩn. Chỉnh sửa cá nhân được giữ trong override.
- Giữ Word ID, chủ sở hữu, nội dung, dấu ôn và tổng lượt học/đúng.
- Tạo tiến độ reading/meaning từ lịch sử còn có. Không giả định phần lịch sử
  thiếu; tổng cũ giữ nguyên. Flashcard cũ quy về reading theo giao diện cũ.
- Chuyển câu trả lời JSONB sang study_answers, giữ snapshot nghĩa/cách đọc.
- Giữ thứ tự từ, vị trí, lựa chọn, điểm, tài khoản và cookie đăng nhập.
- Phiên thiếu từ hợp lệ chuyển invalidated; lịch sử vẫn được giữ. Nếu không có
  thời điểm từng câu cũ, dùng thời điểm tạo phiên để khởi tạo lịch ôn.

```powershell
uv run alembic upgrade head
uv run alembic check
uv run python scripts/verify_refactor.py
```

Khởi động API v2 và Ctrl+F5 trình duyệt. Không dùng frontend/API v1 với schema v2.

## Kiểm chứng và phục hồi

`backend/tests/test_migrations.py` tạo schema PostgreSQL tạm, nạp dữ liệu v1 có
sửa riêng, kiểm tra upgrade, downgrade, upgrade lần nữa và schema drift. Test
không sửa các bản ghi ứng dụng đang dùng.

Downgrade dựng lại nội dung đầy đủ và mảng câu trả lời v1, giữ tổng bộ đếm. V1
không biểu diễn tiến độ hai kỹ năng và trạng thái nhiều phiên tạm dừng. Chỉ hạ
phiên bản khi đã dừng v2, có backup và có mã nguồn v1 để chạy lại.

Nếu cần quay về nguyên trạng trước nâng cấp, khôi phục dump vào DB riêng và
kiểm tra trước khi chuyển kết nối. Không restore đè khi đang có người dùng ghi.
