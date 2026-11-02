# Kotoba 2 — Học từ vựng JLPT N2

FastAPI + PostgreSQL; frontend HTML/CSS/JavaScript ES modules, không cần build.
Bộ từ khởi đầu có **1.617 mục**: 36 từ ban đầu và 1.581 từ Kanji N2 bổ sung.

## Chạy trực tiếp trên Windows

Cần Python 3.12+, PostgreSQL và [uv](https://docs.astral.sh/uv/). Chỉ tạo `.env`
nếu chưa có; giữ cấu hình kết nối đang sử dụng:

```powershell
Copy-Item .env.example .env
# Sửa DATABASE_URL và APP_ORIGIN trong .env.
uv sync --frozen
uv run alembic upgrade head
uv run uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir backend
```

Nếu môi trường ảo đã có:

```powershell
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir backend
```

Mở **http://127.0.0.1:8000**; Swagger tại **/docs**, OpenAPI tại **/openapi.json**,
kiểm tra kết nối DB tại **/api/health**. `APP_ORIGIN` phải khớp địa chỉ truy cập,
bao gồm giao thức/cổng. Không dùng `file://` hoặc Live Server. Không có tài khoản
mặc định; đăng ký để tạo sổ từ riêng.

Có thể thay uv bằng venv và `python -m pip install -r requirements.txt`.

## PostgreSQL trên Aiven

Backend và Alembic cùng đọc `DATABASE_URL` từ `.env`; không cần đổi model hay
API. Dùng URI của service Aiven, đổi tiền tố thành `postgresql+psycopg://` để
khớp driver đã cài trong project và giữ `sslmode=require`:

```dotenv
DATABASE_URL=postgresql+psycopg://avnadmin:URL_ENCODED_PASSWORD@HOST:PORT/defaultdb?sslmode=require
```

Thay host, port, database, tài khoản và mật khẩu bằng thông tin service thực tế.
URL-encode mật khẩu có ký tự đặc biệt khi tự ghép URL. `sslmode=require` mã hóa
kết nối TLS; để xác minh chứng chỉ, Aiven hỗ trợ `verify-ca`/`verify-full` cùng
CA certificate ([tài liệu Aiven](https://aiven.io/docs/products/postgresql/howto/list-code-samples)).

Chạy trực tiếp: dùng lệnh `alembic upgrade head` và khởi động Uvicorn ở trên.
Migration tạo/cập nhật schema trên database được trỏ tới; dữ liệu từ database
local không tự chuyển sang Aiven. Sau khi khởi động, mở
<http://127.0.0.1:8000/api/health>; kết quả mong đợi là
`{"status":"ok","database":"ok"}`.

## Docker Compose

Cần Docker Desktop. Compose mặc định truyền `DATABASE_URL` từ `.env` vào API,
phù hợp với Aiven và không khởi tạo PostgreSQL local:

```powershell
docker compose up --build -d
docker compose logs -f api
```

API tự chạy migration trên database trong `DATABASE_URL` khi khởi động. Nếu đổi
`.env` khi container đang chạy, chạy lại `docker compose up --build -d api` để
áp dụng cấu hình mới. API bind loopback. Với HTTPS, đặt
`COOKIE_SECURE=true` và `APP_ORIGIN` theo tên miền thực tế.

Địa chỉ mặc định là **http://127.0.0.1:8000**. Đặt
`APP_ORIGIN=http://127.0.0.1:8000` trong `.env` để đăng ký/đăng nhập từ địa chỉ này.
Sau khi đổi `.env`, cần tạo lại container để cập nhật biến môi trường;
`docker compose restart` không nạp lại các giá trị này:

```powershell
docker compose up --build -d --force-recreate api
```

Nếu muốn dùng PostgreSQL local, đặt `POSTGRES_PASSWORD` trong `.env` và thêm
file cấu hình local (file này đổi URL của API sang service `db`):

```powershell
docker compose -f compose.yaml -f compose.local.yaml up --build -d
```

Database local vẫn dùng volume `postgres_data` như trước và không mở cổng ra
ngoài. Chuyển sang Aiven không xóa volume hoặc tự chuyển dữ liệu local.

## Quy tắc học

- Từ chuẩn ở `vocabulary`; mỗi tài khoản giữ sổ từ, sửa riêng, ghi chú và tiến độ.
  Sửa từ của mình không sửa nội dung của người khác.
- Dấu `marked_for_review` độc lập với mức ghi nhớ. Bỏ dấu không làm từ trở thành
  đã nhớ. Cách đọc và nghĩa có tiến độ, chuỗi đúng và lịch ôn riêng.
- **Đã vững hai kỹ năng**: ít nhất 2 câu đúng liên tiếp ở mỗi kỹ năng. Một câu sai
  chỉ đặt lại chuỗi của kỹ năng đó.
- Trả lời sai được ôn lại ngay và có mốc ôn sau 10 phút. Chuỗi đúng dùng khoảng
  1, 3, 7, 14, 30 ngày. Đây là lịch cố định, chưa phải mô hình ghi nhớ cá nhân hóa.
- Đổi Kanji/cách đọc đặt lại tiến độ từ. Đổi nghĩa đặt lại tiến độ nghĩa; sửa ghi
  chú giữ tiến độ. Lịch sử giữ bản chụp nội dung tại lúc trả lời.
- Đổi chế độ tạm dừng phiên cũ; quay lại cùng cấu hình tiếp tục phiên phù hợp.
  **Bắt đầu phiên mới** chủ động tạo lại phiên; lịch sử có nút tiếp tục phiên tạm dừng.
- Đổi nội dung đề hoặc xóa từ làm phiên liên quan chưa hoàn thành chuyển sang
  invalidated. Các câu trả lời và phiên hoàn thành vẫn được giữ.

## Cấu trúc

```text
backend/
  routes/           HTTP auth, workspace, words, study; response_model
  services/         Nghiệp vụ tài khoản, từ và trạng thái phiên
  repositories.py   Quyền sở hữu, lọc/tìm kiếm/phân trang SQL
  presenters.py     Dựng phản hồi có kiểu; không commit
  models.py         Từ chuẩn, sổ từ cá nhân, tiến độ, phiên và câu trả lời
  schemas.py        Request/response; action phân biệt theo loại
  db.py             Transaction function scope, hoàn tất trước response
  security.py       Cookie, CSRF, khóa tài khoản và revision
  middleware.py     Giới hạn body ASGI, origin, security headers
  constants.py      Giới hạn và quy tắc học chung
  catalogue.py      Bộ từ, ID ổn định, nguồn và giấy phép
  seed.py           Thêm từ thiếu, tôn trọng sửa riêng và giới hạn
  migrations/       Schema và chuyển dữ liệu có phiên bản
  data/             Nguồn cố định, bản dịch và giấy phép
dist/
  bootstrap.js      Xác thực/khởi động
  api.js            HTTP, CSRF, revision và mã lỗi
  state.js          State đã xác nhận, delta, ngăn ghi lặp
  app.js            Điều hướng, kết nối module
  study-view.js     Flashcard/quiz và thống kê
  word-library.js   Phân trang, debounce, bỏ tìm kiếm cũ
  word-editor.js    Thêm/sửa/xóa và dấu ôn
  import-export.js  Preview ở server, xuất kèm giấy phép
  history.js        Lịch sử và tiếp tục phiên
  core.js           Hàm thuần kiểm tra/phân tích nhập; không chấm điểm
tests/              Kiểm thử ES modules trực tiếp, không eval mã app
tests/e2e/          Playwright
scripts/            Dựng dữ liệu, HTTP smoke, server test, đối chiếu migration
```

## API v2

Workspace khởi động không tải toàn bộ từ. `GET /api/words` lọc và phân trang
SQL, mặc định 50, tối đa 100 từ/trang. Thao tác học trả phiên hiện tại, thống kê,
revision và từ vừa đổi; không gửi lại 1.617 từ, toàn bộ ID hoặc lịch sử.

Cookie HttpOnly/SameSite, mật khẩu Argon2. Request ghi có `X-CSRF-Token`; thay
đổi dữ liệu học có `X-Revision`. Lỗi có mã riêng; chỉ xung đột revision/phiên mới
cần đồng bộ, không tự phát lại thao tác ghi. Câu trả lời có khóa duy nhất
`(session_id, position)`. Rate limit dùng transaction riêng để tính cả lượt thất bại.

Action mới: `reveal`, `flash_answer`, `quiz_answer`, `next`. Dấu ôn mới:
`marked_for_review`; query lọc dùng `status=review`. Chi tiết và khác v1:
[docs/API.md](docs/API.md).

## Nâng cấp dữ liệu

Dừng v1 và sao lưu trước `alembic upgrade head`. Migration `0002` giữ Word ID,
từ/ghi chú riêng, tổng lượt học/đúng, tài khoản, cookie và phiên đang hoạt động.
Tiến độ kỹ năng được dựng từ lịch sử còn lưu; flashcard cũ quy về cách đọc.
Không tự suy đoán phần tiến độ thiếu lịch sử. Sau nâng cấp dùng API/frontend v2
và tải lại bằng **Ctrl+F5**. Kiểm chứng/khôi phục: [docs/MIGRATION.md](docs/MIGRATION.md).

## Bộ từ và nhập/xuất

[Nguồn, bản commit và giấy phép](backend/data/NOTICE.md) hiển thị tại
`/vocabulary-credits.html`. Các mục bổ sung chuyển thể từ OpenJLPT theo CC BY-SA
4.0; nghĩa tiếng Việt do AI biên soạn, chưa qua giáo viên rà soát. Cấp N2 là phân
loại cộng đồng; từ bổ sung chưa có câu ví dụ.

```powershell
uv run python -m backend.seed --all-users
uv run python -m backend.seed --all-users --apply
uv run python scripts/build_n2_seed.py --check
```

Lệnh đầu xem trước, lệnh thứ hai thêm từ thiếu, không ghi đè sửa riêng/tiến độ,
không vượt 2.000 từ. Dùng `--user-id UUID` thay `--all-users` để giới hạn tài khoản.
Với Docker: `docker compose exec api .venv/bin/python -m backend.seed --all-users --apply`.

Hộp thoại nhận CSV/TSV/TXT/JSON và đối chiếu từ trùng tại DB. JSON tải về gồm
`words` và `attribution`, nhập lại được. Bản localStorage cũ chỉ được đọc theo
thao tác chủ động, không bị xóa; chuyển từ/ghi chú, không chuyển tiến độ. Dữ liệu
ở origin khác như Sites cũ cần xuất JSON từ địa chỉ cũ trước.

## Kiểm thử và định dạng

Node.js 24 LTS chỉ cần cho công cụ phát triển:

```powershell
uv sync --frozen
npm ci
uv run pytest -q
npm test
uv run ruff format --check backend scripts
npm run format:check
```

Pytest mặc định dùng SQLite trong bộ nhớ. PostgreSQL dùng database thử nghiệm
riêng; mỗi test tạo/dọn schema ngẫu nhiên, gồm cả upgrade/downgrade và khóa ghi:

```powershell
$env:TEST_DATABASE_URL='postgresql+psycopg://user:password@localhost:5432/kotoba_test'
uv run pytest -q
```

Kiểm thử trình duyệt:

```powershell
$env:KOTOBA_E2E_DATABASE_URL=$env:TEST_DATABASE_URL
npx playwright install chromium
npm run test:e2e
```

Playwright tự khởi động server/schema test ở cổng 8010, không tái sử dụng server
8000. Nếu uv không ở PATH, đặt `KOTOBA_E2E_COMMAND` thành lệnh Python phù hợp.
CI cài Chromium và chạy bộ kiểm thử trước build Docker.

Kiểm tra HTTP và lấy mẫu kích thước response/độ trễ bằng hai terminal:

```powershell
uv run python -m scripts.e2e_server
uv run python scripts/smoke.py
```

Server cần `KOTOBA_E2E_DATABASE_URL`. Smoke chỉ chấp nhận marker test và tạo tài
khoản dùng một lần. Mẫu một client/10 flashcard không thay thế load test nhiều
người dùng. Ctrl+C server để dọn schema.

## Vận hành

Đo số truy vấn, thời gian API và benchmark trên dữ liệu test:
[docs/PERFORMANCE.md](docs/PERFORMANCE.md). Bật `PERFORMANCE_METRICS=true` trong
`.env` và tạo lại container để xem `Server-Timing`/`X-SQL-Queries` cùng log API.

Giữ `.env` ngoài Git. Chỉ tin proxy headers từ proxy giới hạn rõ. Auth mặc định
20 lần/IP/15 phút; cấu hình client IP tin cậy nếu đứng sau reverse proxy.
Sao lưu bằng `pg_dump -Fc`, khôi phục thử vào DB riêng. Với Compose, dump vào
container rồi `docker compose cp` để tránh redirection dữ liệu nhị phân trong PowerShell.

Email khôi phục mật khẩu, quản trị nội dung và lớp học chưa nằm trong phiên bản
này. `.openai/hosting.json` giữ định danh Sites cũ; backend Python cần máy chủ
hoặc container hỗ trợ Python/PostgreSQL.
