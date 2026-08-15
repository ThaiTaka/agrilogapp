# Báo cáo sự cố — Metro bundler sập khi build native chạy song song

**Ngày:** 13/08/2026
**Ảnh hưởng:** Lần chạy app đầu tiên trên máy ảo (Issue #16, #17)
**Mức độ:** Cao — app báo lỗi "Unable to load script" trong khi nguyên nhân thật nằm ở một tiến trình khác đã chết từ trước
**Trạng thái:** Đã sửa bằng cách loại thư mục build native khỏi phạm vi Metro theo dõi

---

## 1. Mô tả lỗi

Sau khi build Android thành công và cài app lên máy ảo, ứng dụng báo lỗi:

```
ReactHost: Fault reason: Unable to load script.
adb reverse tcp:8081 tcp:8081
```

Đây là thông báo chung chung — nó nói "không tải được script", không nói *vì sao*. Kiểm tra log của chính Metro bundler (đang chạy nền, tách biệt khỏi log của app) mới lộ ra nguyên nhân thật:

```
node:internal/fs/watchers:329
    throw error;
    ^

Error: ENOENT: no such file or directory, watch
  'android\app\.cxx\Debug\3e4j4l4r\armeabi-v7a\CMakeFiles\CMakeTmp\CMakeFiles\cmTC_b8c92.dir'
    at FSWatcher.<computed> (node:internal/fs/watchers:321:19)
    at ... metro-file-map/src/watchers/FallbackWatcher.js:133:33

Node.js v24.18.0
```

**Toàn bộ tiến trình Metro đã thoát** — không phải một file bị bỏ qua, mà cả server bundler chết hẳn. App cố kết nối tới cổng 8081 để tải bundle JS, không có gì lắng nghe ở đó, và báo lỗi không liên quan gì tới nguyên nhân thật.

## 2. Nguyên nhân gốc

**Watchman chưa được cài trên máy phát triển.** Metro dùng Watchman làm bộ theo dõi file mặc định — nhanh, ổn định, viết bằng native code. Khi không có Watchman, nó lùi về `FallbackWatcher`, cài đặt bằng `fs.watch()` thuần của Node.

`fs.watch()` thuần có một điểm yếu đã biết: nếu một thư mục bị xoá **giữa lúc** gọi `watch()` và lúc hệ điều hành đăng ký xong việc theo dõi, nó ném `ENOENT` — và `FallbackWatcher` của Metro không bọc try/catch quanh trường hợp này, nên ngoại lệ đó không được bắt và giết chết tiến trình Node.

Tình huống đó xảy ra thật: bước biên dịch native (CMake, chạy trong lúc Gradle build) liên tục tạo rồi xoá các thư mục "thăm dò trình biên dịch" trong `android/app/.cxx/Debug/.../CMakeFiles/CMakeTmp/` chỉ trong vài mili-giây — đây là hành vi bình thường của CMake khi kiểm tra trình biên dịch. Metro, mặc định theo dõi **toàn bộ cây thư mục dự án** (bao gồm cả `android/`), bắt trúng đúng khoảnh khắc một thư mục như vậy vừa biến mất.

## 3. Cách sửa từng bước

### 3.1 Loại thư mục build ra khỏi phạm vi Metro theo dõi

`mobile/metro.config.js`:

```js
const { getDefaultConfig, mergeConfig } = require('@react-native/metro-config');

const config = {
  resolver: {
    blockList: [
      /android[/\\](app[/\\])?build[/\\].*/,
      /android[/\\]app[/\\]\.cxx[/\\].*/,
      /android[/\\]\.gradle[/\\].*/,
      /ios[/\\]build[/\\].*/,
      /ios[/\\]Pods[/\\].*/,
    ],
  },
};

module.exports = mergeConfig(getDefaultConfig(__dirname), config);
```

> **Lưu ý về cách viết:** cách thông thường để build danh sách này là `require('metro-config/src/defaults/exclusionList')`, nhưng phiên bản `metro-config` hiện tại chặn import sâu này qua trường `exports` trong `package.json`:
> ```
> Error [ERR_PACKAGE_PATH_NOT_EXPORTED]: Package subpath './src/defaults/exclusionList'
> is not defined by "exports" in metro-config/package.json
> ```
> Giải pháp là truyền thẳng một mảng `RegExp` cho `blockList` — Metro tự gộp nó với danh sách loại trừ mặc định của framework (`mergeConfig` nối mảng, không ghi đè).

### 3.2 Khởi động lại Metro với cache sạch

```powershell
npx react-native start --port 8081 --reset-cache
```

### 3.3 Kiểm chứng

```powershell
curl http://127.0.0.1:8081/status
# packager-status:running
```

Build lại app native (kích hoạt lại bước CMake) trong khi Metro đang chạy — Metro phải sống sót qua toàn bộ quá trình đó.

## 4. Vì sao đây không phải lỗi trong code ứng dụng

Log lỗi hiển thị trên **app** — "Unable to load script" — hoàn toàn không nhắc gì tới file bị mất hay Metro. Đây là kiểu lỗi nguy hiểm nhất: triệu chứng xuất hiện ở một tiến trình (app), nguyên nhân nằm ở tiến trình khác (Metro) đã chết từ trước đó vài giây. Gỡ lỗi bằng cách chỉ nhìn vào log app sẽ đi sai hướng hoàn toàn — chỉ khi đọc log riêng của Metro mới thấy được ngoại lệ `ENOENT` gốc.

## 5. Bài học cho báo cáo đồ án

Hai điều đáng ghi:

**Một: cài Watchman lẽ ra đã tránh được sự cố này từ đầu.** Đây là khuyến nghị chính thức của tài liệu React Native cho Windows, và bộ theo dõi native của nó không có lỗ hổng đua tranh (race condition) này. Việc chưa cài không sai — chỉ là thiếu — nhưng ghi nhận rằng cấu hình `blockList` vẫn là lớp bảo vệ đáng có **ngay cả khi có Watchman**, vì nó còn giảm tải cho bộ theo dõi (không cần quét hàng nghìn file tạm trong `build/`) chứ không chỉ né được lỗi crash.

**Hai: cùng một họ lỗi với các sự cố backend đã gặp trong dự án** (`Error_Sync_Cursor_Transaction_Timestamp.md`, `Error_Postgres_Locale_Case_Folding.md`): một giả định ngầm ("thư mục đang theo dõi sẽ không biến mất giữa chừng", "lower() sẽ hạ đúng chữ", "now() sẽ trả về thời gian hiện tại") hoá ra sai trong một trường hợp biên hiếm gặp, và hậu quả xuất hiện ở một nơi hoàn toàn khác với nguyên nhân. Quy tắc chung vẫn vậy: khi triệu chứng và nguyên nhân cách xa nhau, hãy tìm log của *từng tiến trình liên quan riêng biệt*, đừng chỉ tin vào log của nơi triệu chứng xuất hiện.

---

*Liên quan: [Error_WatermelonDB_BuildConfig_AGP9.md](Error_WatermelonDB_BuildConfig_AGP9.md) (sự cố xảy ra ngay trước đó trong cùng phiên build), README.md §8 (cài đặt mobile).*
