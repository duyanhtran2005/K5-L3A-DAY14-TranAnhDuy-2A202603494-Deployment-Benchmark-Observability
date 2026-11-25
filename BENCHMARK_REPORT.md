# Báo cáo Benchmark và Observability · Day 14

- Họ tên và MSSV: Trần Anh Duy - 2A202603494
- Ngày chạy: 25/11/2026
- Môi trường: Windows với Ubuntu trên WSL2 (x86_64), Python 3.12.3, Docker Desktop và Docker Compose v2.36.0-desktop.1.

Dùng số liệu từ file JSON, CSV và ảnh chụp của các lần chạy lab.

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng |
|---|---:|---|
| p95 latency của `POST /ask` | ≤ 500 ms | Mục tiêu là ít nhất 95% request hoàn tất trong 500 ms. p95 phản ánh độ trễ của nhóm request chậm mà giá trị trung bình có thể che khuất. |
| Tỷ lệ lỗi của `POST /ask` | ≤ 2% | Với 300 request, ngưỡng này tương đương tối đa 6 request lỗi. Cùng một ngưỡng được áp dụng cho cả bốn mức concurrency. |
| Accuracy trên golden dataset sau khi sửa knowledge base | 100% (23/23), không regression | Bộ eval cố định cho phép xác nhận hai câu sai đã được sửa và cả 21 câu đúng ở baseline vẫn đạt. |

Hai ngưỡng hiệu năng được kiểm tra bằng `load_test.py`. Ngưỡng chất lượng được kiểm tra bằng `run_eval.py --min-accuracy 1.0 --baseline reports/eval_v2.json`.

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency và latency (agent v2)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Tỷ lệ lỗi | SLO |
|---|---:|---:|---:|---:|---:|---|
| 1 | 4,46 | 196,2 | 225,8 | 1700,3 | 1,67% | PASS |
| 10 | 34,42 | 192,5 | 227,1 | 1713,1 | 1,00% | PASS |
| 50 | 120,27 | 199,3 | 259,3 | 1714,6 | 1,00% | PASS |
| 100 | 47,73 | 654,1 | 3963,4 | 4419,3 | 0,33% | FAIL |

Mỗi lượt gửi 300 request. Ngưỡng SLO là p95 ≤ 500 ms và tỷ lệ lỗi ≤ 2%.

Thông lượng tăng từ 4,46 lên 120,27 RPS khi concurrency tăng từ 1 lên 50. Khi tải tăng từ 50 lên 100, thông lượng giảm còn 47,73 RPS và cả p50 lẫn p95 đều tăng. Kết quả cho thấy hệ thống xử lý kém hiệu quả hơn ở mức tải 100 trong lần đo này. Cần số liệu tài nguyên hoặc tracing để xác định nút thắt cụ thể.

### 2.2 Tail latency

| `MOCK_SLOW_RATE` | Trung bình (ms) | p95 (ms) | p99 (ms) |
|---|---:|---:|---:|
| 0 | 187,9 | 218,2 | 223,4 |
| 0.03 (mặc định) | 227,5 | 225,8 | 1701,3 |
| 0.1 | 312,8 | 1685,4 | 1714,6 |

Khi `MOCK_SLOW_RATE` tăng từ 0 lên 0.03, latency trung bình tăng 39,6 ms, còn p99 tăng từ 223,4 ms lên 1701,3 ms. Ở mức 0.1, p95 tăng lên 1685,4 ms và vượt ngưỡng SLO 500 ms, dù trung bình chỉ là 312,8 ms. p99 phát hiện nhóm request chậm ngay ở mức 0.03. p95 phản ánh rõ ảnh hưởng khi nhóm request chậm chiếm tỷ lệ lớn hơn.

### Ghi chú Exercise 7.1 · Metrics

| Loại | Metric quan sát được | Ý nghĩa |
|---|---|---|
| Counter | `http_requests_total` | Đếm số request HTTP theo method, route và mã trạng thái. |
| Gauge | `agent_in_flight_requests` | Số request đang xử lý tại thời điểm đọc metric. |
| Histogram | `agent_question_length_chars` | Phân bố độ dài câu hỏi theo ký tự. Sau một request, `agent_question_length_chars_count` bằng `1.0`. |

Middleware dùng mẫu route như `/ask` và gom đường dẫn không khớp vào `unmatched`. Nếu dùng URL thực làm label, mỗi đường dẫn khác nhau có thể tạo thêm time series, làm tăng bộ nhớ và khối lượng xử lý của Prometheus.

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 sau khi sửa knowledge base |
|---|---:|---:|---:|
| Accuracy | 4,35% (1/23) | 91,30% (21/23) | 100% (23/23) |
| Số token trung bình mỗi câu | 57,3 | 108,8 | 112,8 |
| Tổng chi phí (USD) | 0,000406 | 0,000758 | 0,000783 |
| Chi phí mỗi câu đúng (USD) | 0,00040635 | 0,00003607 | 0,00003406 |
| Quality gate | FAIL (ngưỡng 80%) | PASS (ngưỡng 80%) | PASS (ngưỡng 100%) |

| ID câu v2 trả lời sai | Keyword bị thiếu | Nội dung đã sửa |
|---|---|---|
| `security-02` | `token`, `hết hạn`, `chữ ký` | Bổ sung tài liệu phân biệt JWT có chữ ký và thời hạn với API key dạng chuỗi bí mật. |
| `scaling-03` | `cpu`, `memory`, `custom metrics` | Bổ sung tài liệu về các chỉ số Kubernetes HPA dùng để điều chỉnh số pod. |

V2 dùng thêm bước retrieval. Số token trung bình tăng từ 57,3 lên 108,8 và p95 trong lượt eval tăng từ 192,2 lên 221,8 ms. Chi phí mỗi câu đúng giảm từ 0,00040635 xuống 0,00003607 USD vì số câu đúng tăng từ 1 lên 21. Sau khi bổ sung hai mục vào knowledge base, v2 đạt 23/23 và giữ nguyên kết quả của cả 21 câu đã đúng. p95 của lượt eval cuối là 227,8 ms. Các giá trị latency ở đây mô tả lượt eval 23 câu. Kết luận về SLO hiệu năng dựa trên load test ở mục 2.

Trong CI, chạy `run_eval.py` với `--min-accuracy 0.85` và `--baseline` trỏ tới báo cáo của phiên bản đã duyệt. Script trả exit code `1` nếu accuracy dưới 85% hoặc có câu từ đúng thành sai. Đặt job này làm kiểm tra bắt buộc trước khi merge. Lượt xác nhận cuối của lab dùng ngưỡng 100% và đã đạt.

## 4. Observability stack (production)

### 4.1 Ảnh minh chứng

- [Dashboard Grafana có tải](screenshots/grafana-dashboard.png)
- [Trace chậm trong Jaeger](screenshots/jaeger-slow-trace.png)
- [Trace lỗi trong Jaeger, có event `exception`](screenshots/jaeger-error-trace.png)
- [Hai alert cùng firing trong Prometheus](screenshots/prometheus-alert-firing.png)

Tại thời điểm chụp Grafana, `POST /ask` có 33,4 req/s, tỷ lệ lỗi 0,82% và p95 là 293,53 ms. Dashboard ghi nhận ba instance hoạt động.

Tại mốc 18:02:20 trong cùng lượt chạy ba instance, Prometheus ghi nhận latency trung bình 233,21 ms và p95 là 293,89 ms. p95 cao hơn trung bình khoảng 60,68 ms, cho thấy một phần request có độ trễ cao hơn mức trung bình. Ba instance lần lượt xử lý 22,09, 22,06 và 22,13 req/s, cho thấy Nginx chia tải gần đều tại mốc đo này.

Tốc độ token đầu vào khoảng 4.882 token/s, cao hơn đầu ra khoảng 2.597 token/s. Agent v2 đưa cả câu hỏi và ngữ cảnh truy xuất vào prompt. Khi gọi `/metrics` qua Nginx, kết quả là HTTP `404`. Prometheus scrape endpoint này trực tiếp trên mạng Compose.

### 4.2 Thí nghiệm gây lỗi có kiểm soát

| Mục | Thay đổi | Alert firing | Thời gian từ lúc tạo lại agent đến khi firing | Panel phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` | Khoảng 74 giây | Error rate |
| B | `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` | Khoảng 139 giây | Latency p95 |
| C | `LLM_MODEL=mock-llm-large` | Chưa chạy | — | — |
| D | `docker pause` một instance | Chưa chạy | — | — |
| E | `AGENT_VERSION=v1` | Chưa chạy trong lượt thử alert | — | — |

A và B được áp dụng cùng lúc trên ba instance. Thời gian được tính từ mốc Docker tạo lại agent đến mẫu `firing` đầu tiên trong Prometheus. Cảnh báo tỷ lệ lỗi yêu cầu tỷ lệ `5xx` vượt 5% liên tục trong 1 phút. Cảnh báo latency yêu cầu p95 vượt 1 giây liên tục trong 2 phút. Lệnh `promtool test rules` trả `SUCCESS`.

Khi chuyển sang v1, request vẫn có thể trả `200` và latency vẫn trong ngưỡng dù câu trả lời kém chính xác hơn. Có thể phát hiện lỗi chất lượng bằng cách chạy eval trên golden dataset, so sánh với baseline và theo dõi tỷ lệ câu đúng theo từng nhóm.

### 4.3 Phân tích trace

- `trace_id` của request chậm: `de54dd4943afaf60e41abd03d68d6c52`.
- Tổng thời gian xử lý theo log HTTP: 1.720,6 ms.
- Bước gọi `chat mock-llm-small` mất 1.695,6 ms theo log agent, khoảng 98,5% tổng thời gian. Span retrieval trong Jaeger mất khoảng 22,5 ms.

```json
{"ts":"2026-11-25T11:01:53.363579+00:00","level":"INFO","service":"observable-agent","instance":"dc0f2ae2143e","event":"llm_call","trace_id":"de54dd4943afaf60e41abd03d68d6c52","span_id":"2e88f7f255645e70","request_id":"9e336590becf","model":"mock-llm-small","agent_version":"v2","input_tokens":95,"output_tokens":55,"cost_usd":4.7e-05,"llm_ms":1695.6}
```

Trace lỗi `02cac53a119fe74aa7ef5517f9219c16` kéo dài 88,0 ms và trả HTTP `503`. Span `chat mock-llm-small` có event `exception` với thông báo `Upstream LLM error: 503 Service Unavailable (mock)`.

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---:|---:|---:|---:|---:|
| 1 | 70,94 | 190 | 250 | 1700 | 71/7876 (0,90%) |
| 3 | 70,68 | 190 | 240 | 1700 | 52/7770 (0,67%) |

Khi tăng từ một lên ba instance, p95 giảm 10 ms, p99 vẫn ở 1700 ms và thông lượng gần như giữ nguyên. Với cùng kịch bản 100 user, lượt đo này chưa cho thấy mức tăng thông lượng rõ rệt. Trace chậm dành khoảng 98,5% thời gian cho bước gọi mock LLM, phù hợp với việc p99 vẫn ở mức 1,7 giây sau khi scale.

## 6. Kết luận

1. **Percentile giúp nhận ra nhóm request chậm.** Khi `MOCK_SLOW_RATE` tăng từ 0 lên 0.03, latency trung bình tăng 39,6 ms, còn p99 tăng từ 223,4 lên 1701,3 ms. Trong lượt đo theo concurrency, mức 50 đạt SLO với 120,27 RPS và p95 259,3 ms. Ở mức 100, p95 tăng lên 3963,4 ms và vi phạm SLO.
2. **Chi phí trên mỗi câu đúng cho thấy hiệu quả của retrieval.** Sau khi bổ sung tài liệu về JWT và Kubernetes HPA, v2 đạt 23/23, cải thiện hai câu và có 0 regression. Chi phí mỗi câu đúng giảm từ 0,00040635 USD ở v1 xuống 0,00003406 USD ở v2 sau khi sửa.
3. **Metrics, traces và logs giúp xác định nguyên nhân theo từng bước.** Dashboard cho thấy độ trễ và tỷ lệ lỗi dưới tải. Trace chậm và log cùng `trace_id` cho thấy bước gọi mock LLM chiếm khoảng 98,5% thời gian của request đó. Trong thử nghiệm gây lỗi, hai alert về tỷ lệ lỗi và p95 cùng firing sau khoảng 74 và 139 giây tính từ lúc Docker tạo lại agent.

Nếu triển khai thực tế, cần đo thêm tỷ lệ `502`, `503` và `504` tại Nginx để phát hiện lỗi mà agent có thể không ghi nhận được. Một lượt eval định kỳ trên bộ câu hỏi đại diện cũng giúp phát hiện chất lượng câu trả lời giảm trong khi latency và mã HTTP vẫn trong ngưỡng.
