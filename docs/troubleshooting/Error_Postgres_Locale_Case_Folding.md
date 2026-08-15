# Báo cáo sự cố — `lower()` không hạ chữ tiếng Việt, khiến vật tư trùng lọt lưới

**Ngày:** 11/08/2026
**Ảnh hưởng:** Issue #23 (vật tư / tồn kho), và mọi phép so khớp không phân biệt hoa thường về sau
**Mức độ:** Cao — sai đúng đắn một cách âm thầm, ngay trong ngôn ngữ chính của ứng dụng
**Trạng thái:** Đã sửa trong migration `0002`. Đã thêm hai test hồi quy.

---

## 1. Mô tả lỗi

Hai test cùng thất bại:

```
FAILED tests/test_supplies.py::TestCatalogue::test_duplicate_name_and_unit_conflicts
  AssertionError: assert 'đã có trong danh mục' in 'The request conflicts with existing data.'

FAILED tests/test_supplies.py::TestCatalogue::test_duplicate_check_is_case_insensitive
  AssertionError: assert 201 == 409
```

Test thứ nhất cho thấy thông báo tiếng Việt thân thiện không hề xuất hiện — request bị chặn bởi bộ xử lý `IntegrityError` chung, nghĩa là **database** bắt được trùng còn **service** thì không.

Test thứ hai tệ hơn: tạo vật tư `"đạm urê phú mỹ"` sau khi đã có `"Đạm Urê Phú Mỹ"` trả về **201 Created**. Không tầng nào bắt được. Một bao phân giờ thành hai dòng tồn kho, và mọi con số tồn kho suy ra từ đó bị chia đôi.

---

## 2. Nguyên nhân gốc

**`lower()` của PostgreSQL hạ chữ theo collation của database. Với collation `C`, nó chỉ đụng tới ASCII `A-Z`.**

Đo trực tiếp:

```
db collate/ctype : ('C', 'C')
pg  lower()      : 'Đạm urê phú mỹ'      ← chữ Đ không đổi
py  .lower()     : 'đạm urê phú mỹ'
AGREE            : False
```

Cả hai thất bại đều bắt nguồn từ đúng một dòng đó:

| Tầng | Nó làm gì | Vì sao hỏng |
|---|---|---|
| Service | `WHERE lower(name) = :chuỗi_python_đã_hạ` | So `'Đạm urê phú mỹ'` (PG) với `'đạm urê phú mỹ'` (Python). Không bao giờ khớp, nên thông báo thân thiện không bao giờ chạy. |
| Unique index | `UNIQUE (household_id, lower(name), unit)` | `lower('Đạm Urê…')` và `lower('đạm urê…')` là *hai chuỗi khác nhau*, nên cả hai dòng đều được chấp nhận. |

Ở test 1, hai tên giống nhau từng byte nên index vẫn bắt được — qua `IntegrityError`, do đó ra thông báo chung. Ở test 2, hai tên chỉ khác hoa thường nên **không gì bắt được cả**.

### Vì sao đây không chỉ là chuyện của môi trường test

Cụm test tạm được tạo bằng `initdb --locale=C`, và đó là thứ làm lộ lỗi. Người ta có thể kết luận "dùng locale tử tế là xong".

Kết luận đó sai, vì ba lý do:

1. **Nó khiến tính đúng đắn của ứng dụng phụ thuộc vào một cờ `initdb`** được ai đó chọn một lần, nhiều năm trước, lúc cài PostgreSQL. Không có dòng code nào trong dự án khẳng định điều đó. Máy tiếp theo, container CI tiếp theo, lần triển khai tiếp theo — đều là tung đồng xu.
2. **Container CI thường mặc định `C`.** Workflow GitHub Actions ở Issue #18 chạy `postgres:18` như một service container; `C`/`C.UTF-8` là khả năng rất thực. Khi đó lỗi sẽ chỉ hiện trên CI, hoặc chỉ trên máy chủ, nhưng không hiện trên máy của người phát triển — kiểu phân bố tệ nhất có thể.
3. **Dù sao `lower()` cũng không phải phép toán đúng.** Unicode định nghĩa `casefold()` cho việc so sánh bỏ qua hoa thường; `lower()` là để hiển thị. Chúng khác nhau với các hệ chữ thật.

### Vì sao bắt được

Chỉ vì test dùng dữ liệu tiếng Việt thật. `test_duplicate_check_is_case_insensitive` với `"Urea"`/`"urea"` — thuần ASCII — sẽ pass với code hỏng trên mọi locale. Viết test bằng đúng ngôn ngữ mà ứng dụng thực sự được dùng chính là điều làm lỗi này hiện ra.

---

## 3. Cách sửa từng bước

**Đừng nhờ database hạ chữ nữa.** Hạ trong Python, lưu kết quả, để index so sánh byte.

### 3.1 Hàm chuẩn hoá

`backend/app/core/text.py`:

```python
def normalise_key(value: str) -> str:
    return unicodedata.normalize("NFC", value).strip().casefold()
```

- **`casefold()` chứ không phải `lower()`** — đây là phép toán Unicode định nghĩa cho so sánh bỏ qua hoa thường.
- **NFC trước** — chữ `â` có thể tới dưới dạng một điểm mã (U+00E2) hoặc `a` + dấu mũ tổ hợp, tuỳ bàn phím và hệ điều hành. Với con người là cùng một chữ; không chuẩn hoá thì là hai chuỗi byte khác nhau.

### 3.2 Lưu khoá

`supplies.name_key VARCHAR(160) NOT NULL`, do `SupplyService` duy trì ở mọi lần tạo và sửa. Vì suy ra từ `name` nên nó **chỉ tồn tại phía máy chủ** và không bao giờ đi vào payload đồng bộ (client vẫn tự tính gợi ý cục bộ bằng `toLowerCase()`).

### 3.3 Đổi index — migration `0002`

```python
op.add_column("supplies", sa.Column("name_key", sa.String(160), nullable=True))
op.execute("UPDATE supplies SET name_key = lower(trim(name)) WHERE name_key IS NULL")
op.alter_column("supplies", "name_key", nullable=False)

op.drop_index("uq_supply_name_unit", table_name="supplies")
op.create_index(
    "uq_supply_key_unit", "supplies",
    ["household_id", "name_key", "unit"],
    unique=True, postgresql_where=sa.text("deleted_at IS NULL"),
)
```

> Bước điền dữ liệu ngược dùng chính `lower()` — hàm mà migration này sinh ra để ngừng tin tưởng. Đó là cố ý và chấp nhận được: đây là phép hạ chữ duy nhất có sẵn trong SQL, mọi dòng đang tồn tại đều là dữ liệu phát triển, và ứng dụng sẽ ghi lại `name_key` đúng ở lần cập nhật tiếp theo của từng dòng. Trên dữ liệu thật, bước này phải là một script Python chạy một lần, lặp qua các dòng và gọi `normalise_key`.

### 3.4 So sánh theo khoá

```python
name_key = normalise_key(payload.name)
duplicate = db.execute(
    _scoped(household_id).where(Supply.name_key == name_key, Supply.unit == payload.unit)
).scalar_one_or_none()
```

So sánh byte thuần tuý. Cùng một kết quả trên mọi cụm, bất kể nó được `initdb` thế nào.

### 3.5 Sửa kèm: script seed

`app/seed.py` trước đây tạo `Supply(...)` trực tiếp và sẽ vi phạm `name_key NOT NULL`. Nay nó đi qua `supply_service.create_supply`, và đó mới là cách đúng dù có lỗi này hay không — seed bằng một đường code song song chính là cách một script seed tạo ra những dòng dữ liệu mà bản thân ứng dụng không bao giờ tạo được.

---

## 4. Kiểm chứng

```
184 passed in 29.12s
alembic downgrade base -> upgrade head -> current = 0002 (head)
ruff check app tests: All checks passed!
```

Hai test hồi quy, đều chạy trên database collation `C`:

- `test_duplicate_check_survives_a_c_locale_database` — khẳng định khoá lưu đúng bằng `"đạm urê phú mỹ"`, rồi từ chối `"ĐẠM URÊ PHÚ MỸ"`, `"đạm urê phú mỹ"` và `"  Đạm Urê Phú Mỹ  "` với mã 409.
- `test_unicode_composition_is_normalised` — dựng dạng NFC và NFD của cùng một tên bằng `unicodedata` rồi khẳng định chúng va nhau. Dựng bằng code có chủ đích: nếu gõ thành chuỗi ký tự trực tiếp, trình soạn thảo sẽ âm thầm chuẩn hoá lại file nguồn và test sẽ pass mà không kiểm tra gì cả.

---

## 5. Bài học cho báo cáo đồ án

**Hãy test bằng đúng loại dữ liệu mà ứng dụng sẽ chứa.** Một fixture ASCII (`"Urea"`, `"Fertilizer A"`) sẽ pass với lỗi này trên mọi locale, trên mọi máy, mãi mãi. Lỗi chỉ chạm tới được qua chữ tiếng Việt — tức là qua từng dòng dữ liệu thật mà hệ thống này sẽ lưu. Một bộ test viết bằng tiếng Anh sẽ cho ra đời một ứng dụng tiếng Việt không phân biệt nổi `Đạm Urê` với `đạm urê`.

**Locale là cấu hình, và tính đúng đắn không được phụ thuộc vào cấu hình.** Bất cứ thứ gì quyết định ở thời điểm `initdb`, trong một Dockerfile, hay bởi mặc định của trình cài đặt, đều không phải thuộc tính của mã nguồn. Nó khác nhau giữa máy cá nhân, CI và máy chủ — nên một lỗi phụ thuộc vào nó sẽ chỉ hiện ra ở đúng một trong ba nơi, đó là kiểu hỏng khó chẩn đoán nhất. Ở đâu hành vi phải giống nhau khắp nơi, hãy tính trong ứng dụng và lưu kết quả lại.

Đây cũng chính là nguyên tắc đã được áp dụng hai lần ở chỗ khác trong dự án, đáng ghi nhận là một khuôn mẫu chứ không phải ba sự trùng hợp:

- **Ngày tháng** lưu dưới dạng số nguyên epoch-ms thay vì `DATE`, nên không có phép chuyển múi giờ nào chen giữa thiết bị và máy chủ (§7.2).
- **Ngày lịch địa phương** là số học nguyên trên hằng số UTC+7 thay vì gọi `timezone()`, nên nó bất biến và đánh index được (§7.2).
- **Hạ chữ** giờ là `casefold()` của Python lưu vào một cột, thay vì `lower()` của SQL tính lại mỗi truy vấn.

Trong cả ba trường hợp, quy tắc là như nhau: *đẩy sự mơ hồ ra khỏi ranh giới database và ghim nó lại trong đoạn code được quản lý phiên bản, được kiểm thử, và giống hệt nhau ở hai phía của quá trình đồng bộ.*

---

*Liên quan: [Data_Requirements_Database.md](Data_Requirements_Database.md) §5.5 (bảng vật tư), §8.3 (chính sách trùng lặp), §10.3 (ràng buộc duy nhất); [Error_Sync_Cursor_Transaction_Timestamp.md](Error_Sync_Cursor_Transaction_Timestamp.md) (cùng một họ lỗi "database không hiểu như bạn nghĩ").*
