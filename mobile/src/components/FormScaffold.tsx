/**
 * Khung chung cho mọi màn hình có form nhập liệu.
 *
 * Tồn tại vì bàn phím ảo che mất ô nhập và nút bấm trên Android. Ba việc phải
 * làm đúng, và cả ba đều được đo trên máy ảo chứ không suy đoán.
 *
 * ── 1. `adjustResize` không còn hiệu lực ────────────────────────────────────
 * Từ Android 15, ứng dụng nhắm `targetSdk` ≥ 35 bị buộc chạy edge-to-edge, và
 * khi đó `android:windowSoftInputMode="adjustResize"` trong AndroidManifest bị
 * bỏ qua. Cửa sổ KHÔNG co lại nữa — bàn phím chỉ đè lên. Dự án đang ở
 * `targetSdk 36`, nên đó là trạng thái thực tế: đo được chiều cao nội dung vẫn
 * nguyên 2400px sau khi bàn phím hiện.
 *
 * Hệ quả: đoạn `behavior={Platform.OS === 'ios' ? 'padding' : undefined}` từng
 * đúng nay thành sai. Nó cố ý TẮT việc né bàn phím trên Android, vì ngày đó hệ
 * điều hành đã tự co cửa sổ và thêm padding nữa sẽ bị cộng dồn hai lần. Hệ
 * điều hành không còn làm việc đó, nên không còn ai né bàn phím cả.
 *
 * ── 2. Tự tính phần bị che, không dùng `KeyboardAvoidingView` ───────────────
 * `KeyboardAvoidingView` lấy khung của chính nó từ `onLayout` — toạ độ TƯƠNG
 * ĐỐI với view cha — rồi đem trừ vào `screenY` của bàn phím, một toạ độ TUYỆT
 * ĐỐI trên màn hình. Màn hình nằm dưới header nên phần padding bị thiếu đúng
 * bằng chiều cao header (đo được: 279px).
 *
 * Truyền `keyboardVerticalOffset` đo từ `onLayout` cũng chưa đủ: lúc đó màn
 * hình còn đang trượt vào, vị trí chưa ổn định, và phần thiếu chỉ giảm còn
 * 116px. Nên ở đây đo lại NGAY khi bàn phím hiện — thời điểm duy nhất chắc
 * chắn mọi thứ đã yên vị.
 *
 * ── 3. Cuộn ô đang nhập lên, SAU KHI padding đã áp ──────────────────────────
 * Thứ tự sự kiện là mấu chốt: chạm vào ô nhập → hệ thống cuộn nó vào tầm nhìn
 * khi màn hình VẪN còn cao đủ, nên thấy chẳng cần cuộn bao nhiêu → rồi bàn
 * phím mới hiện và vùng nhìn co lại, nhưng không ai cuộn lại lần nữa. Vì vậy
 * việc cuộn nằm trong `useEffect` phụ thuộc phần bị che: nó chỉ chạy sau khi
 * padding đã vào DOM.
 */

import React, {useCallback, useEffect, useRef, useState} from 'react';
import {
  Keyboard,
  ScrollView,
  StyleSheet,
  TextInput,
  View,
  type ScrollViewInstance,
  type StyleProp,
  type ViewInstance,
  type ViewStyle,
} from 'react-native';

import {colors} from '../theme';

/** Khoảng hở để ô nhập không dính sát mép bàn phím. */
const BREATHING_ROOM = 24;

export interface FormScaffoldProps {
  children: React.ReactNode;
  /** Style cho nội dung bên trong ScrollView (padding, canh giữa…). */
  contentContainerStyle?: StyleProp<ViewStyle>;
}

export default function FormScaffold({
  children,
  contentContainerStyle,
}: FormScaffoldProps) {
  const scrollRef = useRef<ScrollViewInstance>(null);
  const rootRef = useRef<ViewInstance>(null);
  const [overlap, setOverlap] = useState(0);
  /** Vị trí cuộn hiện tại, để tính điểm đến tuyệt đối cho scrollTo. */
  const scrollY = useRef(0);
  /** Đáy vùng nhìn sau khi đã trừ bàn phím, toạ độ tuyệt đối. */
  const viewportBottom = useRef(0);

  const applyOverlap = useCallback((keyboardScreenY: number) => {
    rootRef.current?.measureInWindow(
      (_x: number, y: number, _w: number, height: number) => {
        if (!Number.isFinite(y) || !Number.isFinite(height)) {
          return;
        }
        // `measureInWindow` trả toạ độ TUYỆT ĐỐI, cùng hệ quy chiếu với
        // `screenY` của bàn phím — đó là điều kiện để phép trừ này có nghĩa.
        const hidden = Math.max(0, y + height - keyboardScreenY);
        viewportBottom.current = y + height - hidden;
        setOverlap(hidden);
      },
    );
  }, []);

  useEffect(() => {
    const subs = [
      // Android chỉ có `keyboardDidShow`; iOS có cả `willShow` nhưng dùng
      // chung một sự kiện thì hành vi hai nền tảng giống nhau, dễ suy luận hơn.
      Keyboard.addListener('keyboardDidShow', event => {
        applyOverlap(event.endCoordinates.screenY);
      }),
      Keyboard.addListener('keyboardDidHide', () => setOverlap(0)),
    ];
    return () => subs.forEach(s => s.remove());
  }, [applyOverlap]);

  /**
   * Kéo ô đang nhập lên trên bàn phím.
   *
   * Tự tính thay vì gọi `scrollResponderScrollNativeHandleToKeyboard`: hàm đó
   * cũng so khung tương-đối với toạ độ tuyệt-đối của bàn phím, đúng cùng loại
   * lỗi đã mô tả ở mục 2, nên nó cuộn thiếu.
   *
   * Chỉ cần xử lý ô được chạm TRƯỚC khi bàn phím mở — đó là ô duy nhất có thể
   * bị che. Sau khi vùng nhìn đã co đúng, mọi ô người dùng còn nhìn thấy để
   * chạm đều đã nằm trên bàn phím.
   */
  useEffect(() => {
    if (overlap <= 0) {
      return;
    }
    const focused = TextInput.State.currentlyFocusedInput();
    focused?.measureInWindow(
      (_x: number, y: number, _w: number, height: number) => {
        const delta = y + height + BREATHING_ROOM - viewportBottom.current;
        if (delta > 0) {
          scrollRef.current?.scrollTo({
            y: scrollY.current + delta,
            animated: true,
          });
        }
      },
    );
  }, [overlap]);

  return (
    // `paddingBottom` trên khung ngoài co vùng nhìn của ScrollView lên đúng
    // mép bàn phím — giống hệt việc hệ điều hành từng tự làm với adjustResize,
    // chỉ khác là con số này do ta đo và nó đúng.
    <View ref={rootRef} style={[styles.flex, {paddingBottom: overlap}]}>
      <ScrollView
        ref={scrollRef}
        style={styles.flex}
        contentContainerStyle={contentContainerStyle}
        onScroll={e => {
          scrollY.current = e.nativeEvent.contentOffset.y;
        }}
        scrollEventThrottle={16}
        keyboardShouldPersistTaps="handled"
        keyboardDismissMode="on-drag">
        {children}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  flex: {flex: 1, backgroundColor: colors.background},
});
