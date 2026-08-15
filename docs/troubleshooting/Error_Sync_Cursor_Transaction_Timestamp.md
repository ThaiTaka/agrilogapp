# Báo cáo sự cố — Con trỏ đồng bộ có thể bỏ sót bản ghi vĩnh viễn

**Ngày:** 11/08/2026
**Ảnh hưởng:** Issue #9 (contract đồng bộ), #31/#32 (push/pull), #40 (kiểm thử xung đột đa thiết bị)
**Mức độ:** **Nghiêm trọng** — mất dữ liệu âm thầm, vĩnh viễn. Bắt được trước khi có bất kỳ client nào.
**Trạng thái:** Đã sửa trong migration `0001`. Đã thêm test hồi quy. Khe hở còn lại được đóng bằng biên an toàn cho con trỏ.

---

## 1. Mô tả lỗi

Test thất bại:

```
FAILED tests/test_schema_integrity.py::TestTriggerKeepsPullCursorHonest
       ::test_raw_sql_update_still_bumps_the_cursor

AssertionError: raw UPDATE did not bump server_updated_at
assert datetime(2026, 8, 11, 15, 7, 1, 815884, tzinfo=ZoneInfo('Asia/Bangkok'))
     > datetime(2026, 8, 11, 15, 7, 1, 815884, tzinfo=ZoneInfo('Asia/Bangkok'))
```

Hai mốc thời gian **giống hệt nhau đến từng micro-giây**. Một lệnh `INSERT` rồi `UPDATE` trên cùng một dòng, trong cùng một transaction, cho ra cùng một `server_updated_at`.

Phản xạ đầu tiên — "trigger không chạy" — là sai. Trigger chạy đúng. Giá trị nó ghi mới là thứ sai.

---

## 2. Nguyên nhân gốc

**`now()` trong PostgreSQL chính là `transaction_timestamp()`, không phải thời điểm hiện tại.**

Mọi câu lệnh bên trong một transaction đều nhận thời điểm *transaction bắt đầu*. Đây là hành vi có tài liệu, đúng chuẩn SQL, và là chính xác thứ ta muốn cho các cột kiểu `created_at`. Nhưng nó hoàn toàn sai cho một luồng thay đổi dựa trên con trỏ.

Trigger ban đầu:

```sql
CREATE OR REPLACE FUNCTION touch_server_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.server_updated_at := now();   -- thời điểm transaction bắt đầu
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

### Vì sao đây là mất dữ liệu chứ không phải chuyện hình thức

`server_updated_at` **chính là con trỏ pull** (`Data_Requirements_Database.md` §6.5). Endpoint pull trả lời câu hỏi "cho tôi mọi thứ đã đổi sau thời điểm T", và client lưu mốc trả về làm con trỏ kế tiếp. Một dòng có `server_updated_at` cũ hơn con trỏ mà client đã lưu thì **sẽ không bao giờ được trả về nữa**.

```
             T1        T2      T3        T4         T5      T6
Txn A     bắt đầu ────────────────────────────── ghi ──── commit
                                                (đóng dấu T1)
Txn B                bắt đầu ─── commit
                                (đóng dấu T2, thấy được từ T3)

Client PULL lúc T4  →  thấy dữ liệu của B, lưu con trỏ = T4
Txn A commit lúc T6 →  dữ liệu của nó mang server_updated_at = T1

Lần PULL sau hỏi     server_updated_at > T4
   → dữ liệu của A (T1) không khớp. Và sẽ không bao giờ khớp.
```

Nhật ký của nông dân nằm trong PostgreSQL, nhìn thấy được trong pgAdmin, và **vĩnh viễn vô hình với mọi thiết bị**. Không báo lỗi. Không ghi log. Triệu chứng duy nhất là nông dân khăng khăng họ đã ghi một thứ không có trong ứng dụng — loại lỗi khó gỡ nhất mà đồ án này có thể tạo ra.

### Vì sao bắt được

Chỉ vì bộ khung test chạy mỗi test bên trong một transaction rồi rollback. Điều đó khiến `INSERT` và `UPDATE` dùng chung một transaction — đúng điều kiện làm lộ ra khiếm khuyết. Khi test thủ công, mỗi request HTTP là một transaction, `now()` và `clock_timestamp()` không phân biệt được, và lỗi này đã lọt lưới.

Một transaction cho mỗi request thì ngắn. Nhưng **sync push cố ý áp cả lô trong một transaction** (§6.6, yêu cầu về tính nguyên tử), và một thiết bị offline ba tuần có thể đẩy lên hàng trăm bản ghi. Transaction đó đủ dài để một lần pull đồng thời bước qua nó.

---

## 3. Cách sửa từng bước

### 3.1 Dùng giờ câu lệnh, không dùng giờ transaction

`backend/alembic/versions/0001_initial_schema.py`:

```python
op.execute(
    """
    CREATE OR REPLACE FUNCTION touch_server_updated_at() RETURNS trigger AS $$
    BEGIN
        NEW.server_updated_at := clock_timestamp();
    RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
)
```

| Hàm | Trả về | Cố định trong một transaction? |
|---|---|---|
| `now()` / `transaction_timestamp()` | lúc transaction bắt đầu | có ← chính là lỗi |
| `statement_timestamp()` | lúc câu lệnh hiện tại bắt đầu | không |
| `clock_timestamp()` | thời gian thực, mỗi lần gọi | không ← đúng |

Chọn `clock_timestamp()` thay vì `statement_timestamp()` vì một câu `UPDATE ... WHERE` chạm nhiều dòng thì không nên đóng dấu tất cả giống nhau; thời gian thực theo từng dòng giữ cho luồng thay đổi có thứ tự chặt chẽ.

> **Migration 0001 được sửa tại chỗ thay vì tạo bản 0002.** Bình thường đây là thực hành không tốt, nhưng tại thời điểm sửa migration chưa từng chạy trên bất kỳ database thật nào — chỉ trên một cụm test tạm. Tạo bản sửa tiếp theo sẽ khiến database `agrilog` của mọi người sau này mang một trigger hỏng trong đúng một revision. **Nếu bạn đã chạy `alembic upgrade head` trên một database quan trọng**, đừng cho rằng pull code mới là xong — hãy chạy §3.4.

### 3.2 Đóng khe hở còn lại bằng biên an toàn cho con trỏ

`clock_timestamp()` xử lý được trường hợp transaction dài, nhưng chưa xử lý một trường hợp tinh vi hơn: một dòng được *đóng dấu* khi ghi nhưng chỉ *thấy được* khi transaction commit. Một transaction ghi lúc T5 và commit lúc T8 là vô hình với lần pull chạy lúc T6 — lần pull đó lưu con trỏ T6 rồi bỏ qua dòng ấy mãi mãi.

Vì vậy endpoint pull lùi con trỏ lại trước khi truy vấn. Thêm vào `backend/app/core/config.py`:

```python
SYNC_CURSOR_SAFETY_MARGIN_MS: int = 2_000
```

**Gửi lại một dòng là vô hại.** ID bản ghi do client sinh (quy tắc R1) và client áp dụng thay đổi bằng upsert, nên pull trùng là thao tác rỗng. Thiết kế đánh đổi vài dòng dư mỗi lần đồng bộ lấy điều bất khả: mất một dòng.

Biên phải lớn hơn transaction ghi dài nhất. 2 giây thừa sức bao một lô push 500 bản ghi; bài kiểm thử tải ở Issue #39 sẽ đo lại và xem xét con số này.

> **Bổ sung phát hiện trong lúc cài đặt sync engine (#32):** biên an toàn chỉ được mở rộng phạm vi **phát hiện**. Nếu dùng con trỏ đã lùi để phân loại `created` với `updated` thì mọi bản ghi được gửi lại vì an toàn sẽ đến dưới dạng `created` cho một bản ghi mà client **đã có** — WatermelonDB báo đó là lỗi. Việc phân loại phải dùng `lastPulledAt` gốc chưa lùi.

### 3.3 Test hồi quy

`backend/tests/test_schema_integrity.py::test_cursor_advances_within_a_single_transaction`
chèn hai dòng trong một transaction và khẳng định mốc thời gian của chúng khác nhau. Test thất bại ngay nếu ai đó đưa trigger về `now()`.

### 3.4 Nếu bạn đã migrate một database rồi

Trigger được thay mà không đụng tới dữ liệu:

```powershell
cd d:\agrilogapp\backend
$env:PGPASSWORD = "<mật khẩu postgres>"
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -h localhost -d agrilog -c @"
CREATE OR REPLACE FUNCTION touch_server_updated_at() RETURNS trigger AS `$`$
BEGIN
    NEW.server_updated_at := clock_timestamp();
    RETURN NEW;
END;
`$`$ LANGUAGE plpgsql;
"@
Remove-Item Env:\PGPASSWORD
```

`CREATE OR REPLACE FUNCTION` thay hàm tại chỗ; sáu trigger đã trỏ tới nó theo tên nên không cần sửa gì thêm.

Kiểm chứng:

```sql
SELECT prosrc FROM pg_proc WHERE proname = 'touch_server_updated_at';
-- phải chứa clock_timestamp(), không phải now()
```

---

## 4. Kiểm chứng

```
102 passed in 10.64s          (trước đó: 100 passed, 2 failed)
alembic downgrade base -> upgrade head -> current = 0001 (head)
ruff check app tests: All checks passed!
```

---

## 5. Bài học cho báo cáo đồ án

Phần này nên đưa vào chương *Kiểm thử*, vì nó là bằng chứng rõ ràng nhất cho thấy chiến lược kiểm thử xứng đáng với chi phí bỏ ra.

Lỗi này vô hình với mọi hình thức test thủ công. Bấm qua ứng dụng — chạy tốt. Đồng bộ một thiết bị — chạy tốt. Nó chỉ xuất hiện khi hai thao tác dùng chung một transaction và có bên thứ ba đọc vào giữa — một tình huống tranh chấp mà test thủ công không thể tái hiện đáng tin cậy, và triệu chứng duy nhất trong thực tế là câu nói của nông dân: "tôi ghi rồi mà".

Hai đặc điểm của bộ khung test đã biến một lỗi không thể tìm ra thành một bản vá hai dòng:

1. **Test chạy trong transaction rồi rollback.** Chọn như vậy vì tính cô lập và tốc độ. Nó tình cờ tái hiện đúng điều kiện làm lộ khiếm khuyết — nhắc rằng một bộ khung tốt bắt được cả những thứ nó không được thiết kế để bắt.
2. **Assertion đặt trên hành vi, không phải sự tồn tại.** Một test yếu hơn — "có trigger tên `trg_seasons_...` không?" — sẽ pass với phiên bản hỏng. Chính việc khẳng định mốc thời gian *thực sự tiến lên* mới bắt được lỗi.

**Quy tắc tổng quát, nay đã áp dụng cho toàn bộ sync engine:** đừng bao giờ giả định một hàm thời gian trả về thời điểm hiện tại. Trong PostgreSQL, `now()` không làm vậy. Mọi thiết kế con trỏ đơn điệu phải nêu rõ nó dùng đồng hồ nào và vì sao, và phải chấp nhận được việc gửi lại — bởi một luồng có thể bỏ sót là không thể sửa sau khi đã bỏ sót, còn một luồng thỉnh thoảng lặp lại thì chỉ hơi lãng phí.

---

*Liên quan: [Data_Requirements_Database.md](Data_Requirements_Database.md) §6.1 (khối cột đồng bộ), §6.5 (contract con trỏ pull), §6.6 (tính nguyên tử của push).*
