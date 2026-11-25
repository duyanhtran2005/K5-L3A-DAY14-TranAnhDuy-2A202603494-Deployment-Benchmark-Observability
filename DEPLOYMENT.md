# Thông tin triển khai

## URL public

[https://day14-agent-ve2j.onrender.com](https://day14-agent-ve2j.onrender.com)

## Nền tảng

Render. Blueprint `06-lab-complete/render.yaml` tạo web service Docker `day14-agent` và dịch vụ Key Value `day14-cache`. Bản triển khai đã kiểm tra dùng commit `f5036b4`.

## Lệnh kiểm tra

### Health và readiness

```bash
BASE='https://day14-agent-ve2j.onrender.com'

curl -sS -o /dev/null -w '/health: %{http_code}\n' "$BASE/health"
curl -sS -o /dev/null -w '/ready: %{http_code}\n' "$BASE/ready"
```

### API `POST /ask` có và không có key

```bash
BODY='{"question":"Hello"}'

curl -sS -o /dev/null -w '/ask thiếu key: %{http_code}\n' "$BASE/ask" \
  -H 'Content-Type: application/json' -d "$BODY"
```

Chạy riêng dòng dưới đây, dán giá trị `AGENT_API_KEY` từ Render khi terminal nhắc và nhấn Enter.

```bash
IFS= read -r -s -p 'Dán API key rồi nhấn Enter: ' DAY14_RENDER_KEY
```

```bash
printf '\n'
curl -sS -o /dev/null -w '/ask có key: %{http_code}\n' "$BASE/ask" \
  -H 'Content-Type: application/json' \
  -H "X-API-Key: $DAY14_RENDER_KEY" \
  -d "$BODY"
unset DAY14_RENDER_KEY
```

Kết quả thực tế:

| Phép kiểm tra | HTTP |
|---|---:|
| `GET /health` | 200 |
| `GET /ready` | 200 |
| `POST /ask` thiếu key | 401 |
| `POST /ask` có key hợp lệ | 200 |

## Biến môi trường đã đặt

| Biến | Cách thiết lập |
|---|---|
| `ENVIRONMENT` | Blueprint đặt thành `production`. |
| `PORT` | Render cung cấp khi chạy service. Dockerfile đọc biến này để chọn cổng lắng nghe. |
| `AGENT_API_KEY` | Render tự sinh bằng `generateValue: true`. |
| `REDIS_URL` | Blueprint lấy chuỗi kết nối nội bộ của `day14-cache` qua `fromService`. |

## Ảnh minh chứng

- [Dashboard triển khai](screenshots/dashboard.png)
- [Service đang chạy](screenshots/running.png)
- [Kết quả kiểm tra HTTP](screenshots/test.png)