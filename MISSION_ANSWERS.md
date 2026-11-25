# Day 14 Lab · Câu trả lời bài tập

## Part 1 · Localhost và production

### Exercise 1.1 · Các anti-pattern trong bản develop

1. API key và thông tin kết nối database được ghi trực tiếp trong `app.py`. Nếu dùng thông tin thật, người có quyền đọc repo cũng có thể đọc các giá trị đó.
2. Hàm `/ask` dùng `print()` để ghi cả nội dung câu hỏi và API key. Nếu dùng key thật, key sẽ xuất hiện trong log của ứng dụng.
3. Uvicorn dùng cổng cố định `8000`. Nền tảng triển khai không thể đổi cổng qua biến môi trường `PORT`.
4. Server chỉ lắng nghe trên `localhost`. Nếu chạy trong container, service khác không thể truy cập agent qua mạng container.
5. `reload=True` được bật cố định. Đây là chế độ tiện cho lúc sửa code, có thể khởi động lại tiến trình khi file thay đổi.
6. Không có endpoint `/health` để nền tảng kiểm tra agent còn phản hồi.

### Exercise 1.2 · Chạy bản develop
Bản develop chạy trên cổng `8000`. Lệnh `POST /ask` với `question=Hello` trên URL trả HTTP `200` cùng câu trả lời từ mock LLM.

```text
{"answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic."}
HTTP 200
```

### Exercise 1.3 · So sánh hai phiên bản

| Hạng mục | Develop | Production | Vì sao quan trọng? |
|---|---|---|---|
| Cấu hình | Host, port và một số giá trị được ghi trực tiếp trong code. | `config.py` đọc cấu hình từ biến môi trường, gồm `HOST`, `PORT`, `DEBUG` và các API key. | Có thể dùng cùng mã nguồn ở local và trên cloud, rồi đặt cấu hình phù hợp cho từng môi trường. |
| Health check | Không có `/health` hoặc `/ready`. | `/health` báo process còn phản hồi. `/ready` kiểm tra cờ sẵn sàng của app. | Nền tảng có thể kiểm tra agent còn sống và quyết định khi nào nên chuyển request tới agent. |
| Logging | Dùng `print()` và in cả câu hỏi lẫn API key. | Dùng module `logging` với định dạng JSON. Log request ghi độ dài câu hỏi thay vì ghi nguyên câu hỏi hay key. | Có thể tìm và lọc sự kiện theo trường mà không đưa key vào log. |
| Graceful shutdown | App không khai báo logic dọn dẹp khi tắt. | Uvicorn xử lý việc dừng server. FastAPI `lifespan` đặt lại cờ readiness và ghi log khi shutdown. | App có chỗ dọn tài nguyên khi dừng hoặc khi nền tảng thay phiên bản. |

## Part 2 · Docker

### Exercise 2.1 · Dockerfile cơ bản

1. Base image là `python:3.11`.
2. Thư mục làm việc trong container là `/app`.
3. Dockerfile copy `requirements.txt` và cài dependencies trước khi copy mã nguồn. Nếu chỉ sửa mã nguồn, Docker có thể dùng lại layer cài dependencies.
4. `ENTRYPOINT` xác định chương trình được chạy khi container khởi động. `CMD` cung cấp lệnh mặc định hoặc đối số mặc định cho `ENTRYPOINT`. Có thể ghi đè `CMD` bằng đối số sau tên image trong `docker run`.

### Exercise 2.2 · Build và chạy container

Image `my-agent:develop` được build từ gốc repo. Sau khi container chạy, `POST /ask` với tham số `question` trên URL trả về:

```text
{"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}
HTTP 200
```

### Exercise 2.3 · Multi-stage build và kích thước image

- Stage `builder` dùng `python:3.11-slim`, cài `gcc`, `libpq-dev` và cài các gói Python vào `/root/.local`.
- Stage `runtime` dùng `python:3.11-slim`, copy các gói Python đã cài và mã nguồn, rồi chạy ứng dụng bằng user `appuser`.
- Bản develop: 426,32 MB.
- Bản production: 57,41 MB.
- Tỷ lệ giảm: 86,53%, tính từ số byte do `docker image inspect` trả về.

Image production nhỏ hơn nhờ base image `slim` và chỉ copy các gói Python đã cài từ stage `builder`. Các công cụ build như `gcc` không đi vào image cuối.

### Exercise 2.4 · Docker Compose và Nginx

```text
Client → 127.0.0.1:18080 → Nginx :80 → Agent :8000
                                           ├─ Redis :6379
                                           └─ Qdrant :6333
```

Nginx nhận HTTP từ máy host và chuyển request tới agent qua mạng nội bộ của Compose. Redis và Qdrant là hai dịch vụ được khai báo làm phụ thuộc của agent. Endpoint `/ask` trong bài này trả lời bằng mock LLM.

Lần khởi động đầu, Docker Desktop không mở được cổng host `80`. Sau khi dùng cấu hình Compose tạm để ánh xạ `127.0.0.1:18080` tới cổng `80` của Nginx, cả bốn container đều báo `Healthy`.

Sau khi stack báo `Healthy`, hai request được gửi qua Nginx tại `127.0.0.1:18080`.

| Request | HTTP | Kết quả |
|---|---:|---|
| `GET /health` | 200 | JSON có `status: ok` và `version: 2.0.0`. |
| `POST /ask` với câu hỏi `Explain microservices` | 200 | JSON có trường `answer` chứa phản hồi của mock LLM. |

## Part 3 · Triển khai trên cloud

### Exercise 3.2 · Triển khai trên Render

- URL public: [day14-agent-ve2j.onrender.com](https://day14-agent-ve2j.onrender.com)
- Blueprint: `06-lab-complete/render.yaml`
- Kết quả: `/health` và `/ready` trả `200`. `POST /ask` trả `401` khi thiếu key và `200` khi có key hợp lệ.
- Minh chứng: [Dashboard](screenshots/dashboard.png), [service đang chạy](screenshots/running.png) và [kết quả kiểm tra](screenshots/test.png).

### So sánh `railway.toml` và `render.yaml`

| Hạng mục | Railway | Render |
|---|---|---|
| Khai báo build và khởi động | File mẫu dùng `[build]` để chọn Nixpacks và `[deploy]` để khai báo lệnh Uvicorn đọc `$PORT`. | File mẫu liệt kê các service trong `services`. Web service dùng Python runtime với `buildCommand` và `startCommand`. Blueprint Part 6 dùng Dockerfile để build và dùng `CMD` trong image để khởi động. |
| Health check và biến môi trường | File mẫu đặt `healthcheckPath = "/health"` và hướng dẫn cấu hình biến môi trường qua dashboard hoặc CLI. | Blueprint đặt `healthCheckPath: /health`, sinh `AGENT_API_KEY` và lấy `REDIS_URL` từ dịch vụ Key Value thông qua `fromService`. |

### Exercise 3.3 · Pipeline CI/CD trên Cloud Run

1. `cloudbuild.yaml` cài dependencies và chạy `pytest`.
2. Sau khi bước kiểm thử đạt, pipeline build Docker image với hai tag `$COMMIT_SHA` và `latest`, rồi push cả hai tag lên registry.
3. Pipeline deploy image theo `$COMMIT_SHA` lên Cloud Run ở `asia-southeast1`, đặt môi trường `production` và lấy secret từ Secret Manager.
4. `service.yaml` mô tả cấu hình service, gồm cổng `8000`, autoscaling từ 1 đến 10 instance, liveness probe `/health` và startup probe `/ready`.

## Part 4 · Bảo mật API

### Exercise 4.1–4.3 · API key, JWT và rate limit

Ở bản develop, `verify_api_key()` đọc header `X-API-Key` và đối chiếu với `AGENT_API_KEY`. Để đổi key, cập nhật biến môi trường khi khởi động lại service, rồi cập nhật key ở client.

Kết quả kiểm tra `POST /ask` ở bản develop:

```text
Thiếu key: HTTP/1.1 401 Unauthorized
Sai key:   HTTP/1.1 403 Forbidden
Đúng key:  HTTP/1.1 200 OK
```

Ở bản production, `POST /auth/token` xác thực tài khoản demo và cấp JWT có chữ ký HS256, chứa tên tài khoản, vai trò và thời điểm hết hạn. Token có hiệu lực 60 phút. `POST /ask` nhận token qua header `Authorization: Bearer <token>` và kiểm tra chữ ký cùng thời hạn trước khi xử lý yêu cầu.

Rate limiter dùng cửa sổ trượt 60 giây. Mỗi tài khoản có một hàng đợi timestamp trong bộ nhớ. Timestamp nằm ngoài cửa sổ bị loại trước khi đếm. Tài khoản thường có giới hạn 10 request/phút, còn vai trò `admin` dùng giới hạn 100 request/phút.

Kết quả chạy 20 request với JWT của tài khoản `student`:

```text
Request 01–10: HTTP 200
Request 11–20: HTTP 429

HTTP/1.1 429 Too Many Requests
x-ratelimit-limit: 10
x-ratelimit-remaining: 0
retry-after: 59

{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}
```

### Exercise 4.4 · Cost guard

Rate limit kiểm soát số lượt gọi trong một khoảng thời gian. Cost guard kiểm soát tổng chi phí, vì hai request có thể dùng số token khác nhau. Bản mẫu Part 4 ước lượng chi phí từ số token đầu vào và đầu ra. Chi phí được ghi sau khi mock LLM trả lời. Khi tài khoản chạm ngân sách 1 USD/ngày, request mới trả `402`.

Với ngân sách 10 USD/tháng cho mỗi tài khoản theo đề bài, có thể lưu chi phí trong Redis bằng khóa `budget:{user_id}:{YYYY-MM}`. Tháng mới sử dụng khóa mới. Bước kiểm tra số tiền còn lại và giữ trước chi phí ước tính cần thực hiện nguyên tử để hai worker không cùng sử dụng phần ngân sách còn lại. Sau khi LLM trả lời, cập nhật chênh lệch theo chi phí thực tế.

## Part 5 · Scaling và reliability

### Exercise 5.1 · Health và readiness

`GET /health` kiểm tra tiến trình còn phản hồi. `GET /ready` kiểm tra agent đã khởi tạo xong và sẵn sàng xử lý request. Sau khi bản develop khởi động, `/health` trả HTTP `200` với `status: ok`, còn `/ready` trả HTTP `200` với `ready: true`.

### Exercise 5.2 · Graceful shutdown

Một request `POST /ask?question=hello` được gửi trước khi tiến trình nhận SIGTERM 0,5 giây. Log cho thấy Uvicorn bắt đầu shutdown, request đang xử lý vẫn trả `200`, sau đó ứng dụng hoàn tất bước dọn dẹp và tiến trình kết thúc.

```text
INFO: Shutting down
POST /ask đang xử lý: HTTP 200
INFO: Waiting for application shutdown.
INFO: Application shutdown complete.
INFO: Finished server process [22433]
```

### Exercise 5.3 · Stateless design

Lịch sử hội thoại được lưu trong Redis theo `session_id`. Khi Nginx chuyển request tiếp theo sang một instance khác, instance đó đọc được lịch sử của cùng session từ Redis. Mỗi instance có bộ nhớ riêng, nên lưu lịch sử trong RAM sẽ khiến phiên hội thoại bị thiếu dữ liệu khi request đổi instance.

### Exercise 5.4–5.5 · Load balancing và kiểm tra stateless

Docker Compose chạy ba instance agent phía sau Nginx. `python test_stateless.py` gửi năm câu hỏi qua `POST /chat` trên cổng `8080` với cùng một session, sau đó đọc lại lịch sử.

```text
Total requests: 5
Instances used: {'instance-53472b', 'instance-51b92f', 'instance-87524f'}
Total messages: 10
```

Ba instance đều tham gia xử lý. Lịch sử vẫn có đủ năm câu hỏi và năm câu trả lời. Kết quả xác nhận các instance dùng chung lịch sử trong Redis.

## Part 6 · Kết quả kiểm tra production readiness

Script `check_production_ready.py` được chạy đầy đủ trong Ubuntu trên WSL2 với Docker. Image đo được 63 MB. `docker stop` hoàn tất trong 1,6 giây với mã thoát `0`.

```text
  📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ✅ Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 12/12 tiêu chí đạt · 42/42 checks passed
  🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
```

## AI log

| Phần | Câu hỏi gửi AI | Hỗ trợ nhận được | Cách kiểm tra |
|---|---|---|---|
| Part 1 | Cách so sánh bản develop và production | Gợi ý đọc code và gọi API mẫu. | Chạy bản develop và kiểm tra phản hồi HTTP. |
| Part 2 | Cách build, đo image và xử lý lỗi cổng | Hướng dẫn dùng Docker và đổi cổng Nginx khi chạy local. | Đo kích thước hai image và kiểm tra API qua Nginx. |
| Part 3 | Cách triển khai và kiểm tra agent trên cloud | Hướng dẫn cấu hình Render và giải thích pipeline Cloud Run. | Triển khai trên Render và kiểm tra bốn trường hợp HTTP. |
| Part 4 | Cách kiểm tra xác thực và giới hạn sử dụng | Giải thích API key, JWT, rate limit và cost guard. | Gửi request thử và đối chiếu mã HTTP. |
| Part 5 | Cách kiểm tra shutdown và chạy nhiều instance | Hướng dẫn thử SIGTERM và kiểm tra lịch sử hội thoại. | Xác nhận request hoàn tất khi tắt app và lịch sử được giữ qua nhiều instance. |
| Part 6 | Cách hoàn thiện agent và xử lý lỗi khi chấm | Gợi ý triển khai các TODO, hỗ trợ gỡ lỗi, commit và push. | Áp dụng từng bước và chạy script chấm đầy đủ, đạt `PASS 12/12`. |
| Part 7 | Cách đo tải, chạy eval và thu thập minh chứng | Hướng dẫn chạy benchmark, bổ sung knowledge base và xử lý lỗi stack observability. | Đối chiếu số liệu với JSON và CSV, xác nhận eval đạt `23/23` và lưu ảnh minh chứng. |