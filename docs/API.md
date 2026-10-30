# Hợp đồng API v2

Đường dẫn dưới `/api`. Auth trả `user` và `csrf` và đặt cookie HttpOnly.
Request ghi đã xác thực gửi `X-CSRF-Token`; thay đổi dữ liệu học gửi thêm
`X-Revision`. Schema đầy đủ ở `/docs` và `/openapi.json`.

## Khởi động và tài khoản

- `POST /auth/register`: email, password, name.
- `POST /auth/login`: email, password.
- `GET /auth/me`; `POST /auth/logout` (204).
- `GET /catalogue`: nguồn, số từ, giấy phép, giới hạn; public.
- `GET /workspace`: version 2, revision, view, settings, stats, session, limits,
  catalogue. Không có mảng toàn bộ từ.
- `PUT /preferences`: count 0/10/20, quizType reading/meaning, view.

## Từ

- `GET /words?q=&status=all&offset=0&limit=50`: items, total, offset, limit,
  revision; limit tối đa 100. Status: all/review/known/new/learning.
- `POST /words`, `PUT /words/{id}`: kanji, reading, meaning, note tùy chọn.
- `DELETE /words/{id}`.
- `PATCH /words/{id}/review`: `{"marked_for_review":true}`.
- `POST /words/import/preview`: `{"words":[...]}`, có CSRF nhưng không có revision;
  trả added, duplicates, capacity_remaining và samples, không ghi dữ liệu.
- `POST /words/import`: cùng body, có revision, nhập nguyên tử và bỏ trùng.
- `GET /words/export`: mảng nội dung từ. Frontend bọc cùng attribution khi tải JSON.

Word response có progress.reading/meaning, tổng seen/correct, known,
marked_for_review và needs_review. Từ đã vững vẫn có thể được đánh dấu ôn thủ công.

## Học

`POST /study/sessions`: mode flash/quiz, scope all/wrong, count, quizType,
view, restart (mặc định false). Mặc định tiếp tục phiên tạm dừng phù hợp;
restart true tạo phiên mới. `POST /study/sessions/{id}/resume` tiếp tục phiên cụ thể.

`POST /study/actions` nhận một trong bốn loại, mỗi loại có session_id và index:

```json
{"session_id":"UUID","index":0,"action":"reveal"}
```

```json
{"session_id":"UUID","index":0,"action":"flash_answer","correct":true}
```

```json
{"session_id":"UUID","index":0,"action":"quiz_answer","choice":"きおく"}
```

```json
{"session_id":"UUID","index":0,"action":"next"}
```

Flashcard tự sang câu sau đánh giá; quiz dùng next. Server chấm quiz và kiểm tra
trạng thái. Trường không thuộc schema bị từ chối. Gửi lại câu đã chấm không tăng điểm.

Session response: id, mode, scope, quizType, status, index, total, correct,
answered_count, answered, current_result, revealed, choice, options, current_word.
Không có toàn bộ IDs/câu trả lời.

- `GET /study/history?offset=0&limit=20`: cả phiên hoàn thành và tạm dừng.
- `GET /study/sessions/{id}/answers?offset=0&limit=50`: bản chụp câu trả lời,
  chỉ chủ tài khoản được đọc.

## Phản hồi và lỗi

Mutation trả revision, view, settings, stats, session và delta updated_words,
deleted_ids, imported, duplicates. Transaction function scope hoàn tất trước
response thành công; helper không commit. Rate limit dùng transaction riêng.

Lỗi có detail/code: duplicate_word, capacity_exceeded, revision_conflict,
session_conflict, already_answered, invalid_choice... Chỉ xung đột revision/phiên
cần đồng bộ lại. Không tự phát lại request ghi sau mất mạng/xung đột.

## Thay đổi từ v1

Workspace/mutation không còn words. wrong đổi thành marked_for_review và tiến
độ kỹ năng riêng. Query status=wrong đổi thành status=review. Action answer đổi
thành flash_answer hoặc quiz_answer. Frontend đi kèm đã chuyển sang hợp đồng mới.
