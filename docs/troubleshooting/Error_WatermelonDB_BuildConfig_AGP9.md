# Báo cáo sự cố — WatermelonDB không biên dịch được dưới AGP 9

**Ngày:** 13/08/2026
**Ảnh hưởng:** Build Android lần đầu (Issue #16), mọi build sau này cho tới khi thư viện nâng cấp
**Mức độ:** Chặn hoàn toàn — không cài được app lên thiết bị/máy ảo
**Trạng thái:** Đã sửa bằng `patch-package`, bền vững qua các lần `npm install` lại

---

## 1. Mô tả lỗi

```
> Task :nozbe_watermelondb:compileDebugJavaWithJavac
WMDatabaseDriver.java:63: error: cannot find symbol
        if (BuildConfig.DEBUG) {
            ^
  symbol:   variable BuildConfig
  location: class WMDatabaseDriver

WMDatabaseBridge.java:257: error: cannot find symbol
WMDatabaseBridge.java:276: error: cannot find symbol

3 errors
BUILD FAILED
```

## 2. Nguyên nhân gốc

**Từ Android Gradle Plugin 8 trở đi, việc sinh lớp `BuildConfig` không còn mặc định bật cho mọi module** — nó phải khai báo tường minh:

```groovy
android {
    buildFeatures {
        buildConfig = true
    }
}
```

RN template tự bật cờ này cho module `:app`, nhưng `@nozbe/watermelondb` — thư viện xuất bản từ trước khi mặc định này đổi — không hề khai báo trong `native/android/build.gradle` của nó. Mã Java của thư viện tham chiếu `BuildConfig.DEBUG` (dùng để bật log gỡ lỗi có điều kiện), và dưới **AGP 9** (dự án này dùng Gradle 9.4.1 / AGP mới nhất), lớp đó đơn giản là không tồn tại → lỗi biên dịch.

### Vì sao không sửa bằng cờ toàn cục

AGP từng có một cờ toàn dự án để khôi phục hành vi cũ cho mọi module chưa tự khai báo:

```properties
android.defaults.buildfeatures.buildconfig=true
```

Thử cờ này trước tiên — nhưng AGP 9.0 đã **xoá hẳn** nó (không chỉ deprecated):

```
FAILURE: Build failed with an exception.
> The option 'android.defaults.buildfeatures.buildconfig' is deprecated.
  The current default is 'false'.
  It was removed in version 9.0 of the Android Gradle plugin.
```

Nghĩa là chỉ cần khai báo cờ này thôi — dù giá trị gì — cũng làm build sập ngay từ bước đọc cấu hình. Không còn đường tắt toàn cục nào ở AGP 9; phải sửa đúng module bị lỗi.

## 3. Cách sửa từng bước

### 3.1 Thêm cờ vào đúng module trong `node_modules`

```groovy
// node_modules/@nozbe/watermelondb/native/android/build.gradle
android {
    ...
    namespace "com.nozbe.watermelondb"

    buildFeatures {
        buildConfig true
    }

    defaultConfig { ... }
}
```

### 3.2 Đóng băng bằng `patch-package`

Sửa trực tiếp trong `node_modules` sẽ **mất khi `npm install` lại**. Dùng `patch-package` để lưu lại:

```powershell
cd mobile
npm install --save-dev patch-package
npx patch-package @nozbe/watermelondb
```

Lệnh này tạo `mobile/patches/@nozbe+watermelondb+0.28.0.patch` — file này **được commit vào git**.

Gắn `postinstall` vào `package.json` để patch tự áp dụng mỗi lần cài lại:

```json
{
  "scripts": {
    "postinstall": "patch-package"
  }
}
```

### 3.3 Kiểm chứng

```powershell
cd mobile\android
.\gradlew.bat installDebug
```

```
> Task :nozbe_watermelondb:compileDebugJavaWithJavac
Note: ... uses or overrides a deprecated API.
2 warnings
BUILD SUCCESSFUL
```

Chỉ còn cảnh báo (API deprecated không liên quan), không còn lỗi.

## 4. Vì sao đây không phải lỗi cấu hình máy

Nếu chỉ đổi phiên bản AGP xuống thấp hơn để "né" lỗi này, dự án sẽ mất quyền dùng compileSdk 37 và các API Android mới — và vấn đề chỉ trì hoãn tới lần nâng cấp AGP tiếp theo. Patch trực tiếp vào thư viện, đóng băng bằng `patch-package`, là cách duy nhất giữ được cả AGP mới nhất lẫn một thư viện WatermelonDB chưa cập nhật theo kịp — và đúng là quy trình chính thức mà `patch-package` được tạo ra để giải quyết.

## 5. Bài học cho báo cáo đồ án

Đây là ví dụ rõ ràng của việc chọn công nghệ đi trước hệ sinh thái thư viện: React Native 0.87 + AGP 9 là bản mới nhất tại thời điểm dự án bắt đầu, nhưng `@nozbe/watermelondb@0.28.0` — thư viện lưu trữ cục bộ cốt lõi của toàn bộ kiến trúc offline-first — được publish trước khi AGP 9 thay đổi mặc định này. Không có gói cập nhật thay thế tại thời điểm viết. Giải pháp không phải là hạ cấp AGP, mà là vá đúng một dòng cấu hình, ghi lại bằng `patch-package` để không cần lặp lại thao tác thủ công mỗi khi môi trường build mới.

---

*Liên quan: README.md §6 (yêu cầu môi trường), mobile/patches/@nozbe+watermelondb+0.28.0.patch.*
