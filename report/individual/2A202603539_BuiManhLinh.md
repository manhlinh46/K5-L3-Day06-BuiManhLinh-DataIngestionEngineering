# Báo cáo cá nhân — Day 6
**Data Ingestion Engineering**

## Dữ liệu và pipeline

- **Chủ đề, nguồn/quyền, số trang và quy tắc tính trang:**  
  Chủ đề: Information Systems Management.  
  Tài liệu: *Introduction to Information Systems Management*, tác giả Roy Wood. Nguồn: Open Oklahoma (Oklahoma State Regents for Higher Education). Tài liệu sử dụng giấy phép CC BY 4.0; một số nội dung bên thứ ba có thể có điều khoản riêng.  
  Corpus gồm 54 trang nội dung: PDF trang 10–31, 80–103 và 154–161. Chỉ tính các trang được chọn có nội dung, không tính toàn bộ 309 trang PDF.

- **Chuẩn hóa, lỗi và giới hạn:**  
  Trích xuất văn bản từ PDF bằng PyPDF. Chuẩn hóa Unicode NFC, xuống dòng, khoảng trắng và loại bỏ một số thành phần đầu/cuối trang như số trang, header và footer.  
  Giới hạn: chất lượng văn bản phụ thuộc vào cấu trúc PDF; một số định dạng hoặc nội dung đặc biệt có thể không được trích xuất hoàn toàn chính xác.

- **Embedding model/provider/version/số chiều, vector store/version, metric, lệnh chạy và chi phí:**  
  - Provider: Local.
  - Model: `sentence-transformers/all-MiniLM-L6-v2`.
  - Thư viện: Sentence Transformers 6.3.0.
  - Vector dimension: 384.
  - Vector store: PostgreSQL 16 + pgvector.
  - Retrieval metric: Cosine similarity.
  - Lệnh chạy: `python -m src.run` (thực hiện trong thư mục `starter`).
  - Chi phí API embedding: 0 vì sử dụng model local. Chưa đo chi phí tài nguyên máy.
  - Thời gian ingest: chưa ghi nhận riêng.

- **Metadata bắt buộc, trường lọc bổ sung, nguồn giá trị và lý do chọn:**  
  Metadata gồm `document_id`, `source`, `page`, `category`.  
  Trường lọc bổ sung là `category`, lấy từ phân loại chủ đề của các chương trong tài liệu. Trường này được sử dụng để giới hạn kết quả truy xuất theo nhóm nội dung như `information_systems`, `data_management` và `cybersecurity`.

## Cấu hình và benchmark

- **A / B / C:**
  - A: Fixed-size chunking, kích thước 500 ký tự, overlap 50 ký tự.
  - B: Paragraph chunking, giới hạn tối đa 500 ký tự.
  - C: Sử dụng cùng paragraph chunking như B, nhưng áp dụng metadata filter theo `category` khi câu hỏi có yêu cầu lọc.

  B và C chỉ khác nhau ở việc áp dụng metadata filter.

- **Benchmark:**  
  Có 20 câu hỏi, gồm 15 câu dev và 5 câu test. Trong đó có 4 câu sử dụng metadata filter: Q05, Q10, Q14 và Q20.  
  Mỗi câu hỏi có nguồn, trang và evidence quote để đối chiếu với nội dung chunk được truy xuất. Evidence được kiểm tra bằng cách so sánh tài liệu, trang và đoạn trích mong đợi với nội dung kết quả.

- **Tiêu chí chọn chiến lược:**  
  Sử dụng Hit@1 và Evidence Hit@3 trên tập dev để so sánh khả năng truy xuất. Test được dùng để đánh giá kết quả cuối cùng, không dùng làm căn cứ tối ưu cấu hình. Việc xác nhận tiêu chí này đã được đặt ra trước khi xem test chưa được ghi nhận trong quá trình thực nghiệm.

## Kết quả

### 1. Retrieval evaluation

| Strategy | Split | Hit@1 (n/N) | Evidence Hit@3 (n/N) | Chunk count | Thời gian | Chi phí |
|---|---|---:|---:|---:|---|---|
| A | Dev | 4/15 (26.67%) | 9/15 (60%) | 200 | Chưa đo | 0 API |
| A | Test | 3/5 (60%) | 4/5 (80%) | 200 | Chưa đo | 0 API |
| B | Dev | 5/15 (33.33%) | 9/15 (60%) | 188 | Chưa đo | 0 API |
| B | Test | 3/5 (60%) | 3/5 (60%) | 188 | Chưa đo | 0 API |
| C | Dev | 5/15 (33.33%) | 9/15 (60%) | 188 | Chưa đo | 0 API |
| C | Test | 3/5 (60%) | 3/5 (60%) | 188 | Chưa đo | 0 API |

### 2. Manual evaluation

| Strategy | Coherence trung bình /2 (n) | Metadata đủ và đúng (n/N) | Filter tuân thủ (n/N hoặc N/A) | Grounding 0/1/2 và trung bình /2 |
|---|---|---|---|---|
| A | Chưa đánh giá thủ công | Chưa đánh giá thủ công | N/A | Chưa đánh giá thủ công |
| B | Chưa đánh giá thủ công | Chưa đánh giá thủ công | N/A | Chưa đánh giá thủ công |
| C | Chưa đánh giá thủ công | Chưa đánh giá thủ công | 12/12 (100%) | Chưa đánh giá thủ công |

**Đường dẫn trace, nhãn thủ công và cách chọn mẫu:**

- `starter/artifacts/evaluation_traces.json`: lưu kết quả top-3 cho từng câu hỏi và chiến lược.
- `starter/artifacts/evaluation_summary.json`: lưu các chỉ số tổng hợp.
- Filter compliance của Strategy C: 12/12 kết quả top-3 thuộc đúng category được yêu cầu trên 4 câu hỏi Q05, Q10, Q14 và Q20 (100%).
- Chưa thực hiện gán nhãn thủ công cho coherence, metadata usefulness và grounding.

## Phân tích và kết luận

- **So sánh A–B:**  
  B có số lượng chunk ít hơn A (188 so với 200). Trên dev, B đạt Hit@1 33.33%, cao hơn A ở mức 26.67%; Evidence Hit@3 bằng nhau ở mức 60%. Trên test, Hit@1 bằng nhau ở mức 60%, trong khi A có Evidence Hit@3 cao hơn B (80% so với 60%).

- **So sánh B–C:**  
  B và C có cùng phương pháp chunking và cùng số lượng chunk. Các chỉ số Hit@1 và Evidence Hit@3 trong kết quả hiện tại bằng nhau. C có thêm khả năng lọc theo category khi câu hỏi cung cấp filter.

- **Hai ví dụ truy xuất chưa đạt:**  
  - Q05: Với chiến lược C, câu hỏi có filter `information_systems` nhưng top-3 chưa chứa đoạn evidence mong đợi ở trang 29. Đây là một trường hợp truy xuất chưa tìm được bằng chứng cần thiết.
  - Q10: Với B/C, kết quả đầu tiên không nằm ở trang gold 89; đoạn bằng chứng đúng xuất hiện ở vị trí thứ ba. Vì vậy Hit@1 không đạt nhưng Evidence Hit@3 vẫn đạt.

- **Chiến lược chọn, đánh đổi và điều kiện áp dụng:**  
  B và C có kết quả dev tương đương. C phù hợp khi cần giới hạn kết quả theo category; B đơn giản hơn khi không cần lọc metadata. A có Evidence Hit@3 tốt hơn trên tập test nhỏ trong lần chạy này, nhưng chưa đủ cơ sở để kết luận A tốt hơn trong mọi trường hợp.

- **Hạn chế:**  
  Corpus chỉ gồm 54 trang từ một tài liệu. Benchmark có 20 câu hỏi, trong đó tập test chỉ có 5 câu. Chưa thực hiện đánh giá thủ công và chưa đo riêng thời gian ingest cũng như chi phí tài nguyên máy.

- **Nếu làm lại hoặc mở rộng:**  
  Có thể bổ sung tài liệu thuộc nhiều nguồn khác nhau, mở rộng benchmark, đo thời gian ingestion và thực hiện đánh giá thủ công trên cùng một tập mẫu cho cả ba chiến lược.
