# Đo và tối ưu hiệu năng

Backend giữ transaction và kiểm tra revision trước khi xác nhận ghi thành công.
Các thay đổi này không cần migration hoặc thay đổi dữ liệu đang dùng trên Aiven.

## Những phần đã tối ưu

- Xác thực đọc phiên đăng nhập và tài khoản bằng một truy vấn join.
- Từ và phiên học đã đọc được giữ trong SQLAlchemy Session của request;
  presenter tái sử dụng chúng. Đọc một từ tải cả hai tiến độ kỹ năng bằng join,
  trong khi danh sách phân trang vẫn dùng selectin để tránh nhân số hàng.
- Số câu trả lời và kết quả câu hiện tại được lấy cùng một truy vấn aggregate;
  service chuyển kết quả đã cập nhật cho presenter sau khi chấm điểm.
- Frontend yêu cầu response gọn cho reveal/next, tránh tính lại thống kê khi
  thao tác chưa thay đổi tiến độ. Các client cũ vẫn nhận response đầy đủ.
- Thống kê cung cấp mốc đến hạn và khoảng chờ tương đối. UI tự tải lại khi hết
  hạn, kể cả khi revision không đổi hoặc đồng hồ trình duyệt khác đồng hồ server.
- Một request bootstrap thay thế catalogue → auth/me → workspace khi tải trang.
  Đăng nhập/đăng ký thành công tiếp tục khởi động UI mà không tải lại toàn trang.
- Focus gần nhau dùng lại trạng thái trong tối đa 15 giây; thông báo thay đổi
  từ tab khác và thời điểm đến hạn bỏ qua khoảng chờ này. Xung đột revision vẫn
  được đồng bộ lại trước thao tác tiếp theo, không tự phát lại request ghi.
- Sửa/đánh dấu một từ đang hiển thị trên danh sách không lọc được cập nhật từ
  delta. Thêm/xóa/nhập từ, tìm kiếm và bộ lọc vẫn tải lại trang từ server.

## Bật phép đo trong Docker

Đặt `PERFORMANCE_METRICS=true` trong `.env`, đảm bảo shell không ghi đè bằng giá trị
khác, rồi chạy:

```powershell
docker compose up --build -d --force-recreate api
docker compose logs -f api
```

Mỗi API có `Server-Timing: app;dur=..., db;dur=...` và `X-SQL-Queries`.
Có thể xem các header trong DevTools → Network. Log chỉ gồm route template,
method, status, thời gian và số truy vấn; không ghi SQL, tham số hay thông tin
tài khoản. Phép đo mặc định tắt.

`app` đo đến lúc gửi response headers, bao gồm transaction function scope.
`db` là thời gian thực thi qua cursor, gồm chờ mạng cho các câu SQL được đếm.
Thời gian lấy kết nối từ pool, pre-ping và commit/rollback không nhất thiết
phát ra cursor event nên không được tính riêng trong `db`/`X-SQL-Queries`;
chúng vẫn ảnh hưởng tới `app`. Các số đo này không phải số packet mạng.

## Benchmark lặp lại trên dữ liệu test

Chỉ dùng database test PostgreSQL riêng. Server E2E tạo schema ngẫu nhiên và dọn
schema khi dừng bình thường. Không tự lấy `DATABASE_URL` của ứng dụng làm test target.

Terminal thứ nhất:

```powershell
$env:KOTOBA_E2E_DATABASE_URL='postgresql+psycopg://user:password@localhost:5432/kotoba_test'
uv run python -m scripts.e2e_server
```

Terminal thứ hai:

```powershell
uv run python -m scripts.benchmark --samples 20 --output .runtime/benchmark.json
```

Benchmark chỉ chạy khi server có marker `{"isolated":true}`; nó tạo tài khoản
test rồi đo identity, workspace, bootstrap, danh sách, đăng nhập và thao tác học.
Output gồm median/p95 HTTP, app, SQL, số truy vấn và kích thước response.
Đăng ký và bắt đầu mỗi chế độ là một mẫu đầu tiên; không xem p95 của các mẫu
đơn lẻ đó là phân phối độ trễ. Đăng nhập giới hạn ở tối đa 3 mẫu.
Đây là một client tuần tự, không phải load test nhiều người dùng.

Để chạy Playwright với server test đã mở sẵn, đặt
`KOTOBA_E2E_EXTERNAL_SERVER=1` cùng `KOTOBA_E2E_DATABASE_URL` trước `npm run test:e2e`.
Test vẫn kiểm tra marker trước khi tạo tài khoản. Mặc định Playwright tự quản lý server.

Khi so sánh trước/sau, dùng cùng máy, vùng database, bộ dữ liệu và số mẫu.
Đo riêng kết nối đầu tiên và các request sau khi pool đã được sử dụng.
Nếu dùng server test trong Docker, cung cấp cùng marker và bật phép đo;
không thêm marker này vào server production để chạy benchmark ghi dữ liệu.

## Kiểm chứng ban đầu

So sánh cùng một client TestClient, SQLite trong bộ nhớ, 1.617 từ/tài khoản,
5 mẫu mỗi action, trước và sau thay đổi:

- Identity: 2 → 1 câu SQL; workspace chưa có phiên: 3 → 2.
- Danh sách 50 từ: 5 → 4; bắt đầu flashcard: 13 → 9.
- Reveal: 15 → 7; trả lời flashcard: 18 → 12.
- Trả lời quiz: 18 → 11; next: 19 → 10.

Các số trên là số câu SQL, không phải mức tăng tốc đã đo trên Docker/Aiven.
Response gọn được dùng ở client mới; benchmark trước thay đổi dùng response đầy đủ.
Kịch bản giữ nguyên luồng học và dữ liệu đầu vào.

EXPLAIN (ANALYZE, BUFFERS) trên PostgreSQL 18 local, một tài khoản với 1.617 từ
và 3.234 hàng tiến độ: thống kê khoảng 8,6 ms; từng SELECT cho trang 50 từ
khoảng 0,1–0,3 ms sau ANALYZE. Đăng ký đã gom insert thành 4 câu lệnh trên
PostgreSQL. Chưa thêm index hoặc đổi cơ chế insert vì số đo này chưa cho thấy
chúng là nút thắt. Cần đo lại với dữ liệu và tải thực tế trước quyết định tiếp.

Chạy lại pytest với `TEST_DATABASE_URL` để kiểm tra migration và khóa ghi đồng
thời trên PostgreSQL; kiểm thử frontend gồm response delta, hạn thống kê,
khởi động, lỗi mạng và cập nhật danh sách không tải lại.
