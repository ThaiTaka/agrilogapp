import React, {useState} from 'react';
import {
  ActivityIndicator,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';

import FormScaffold from '../../components/FormScaffold';
import {useAuth} from '../../services/auth';
import {colors, MIN_TOUCH_TARGET, radius, spacing, typography} from '../../theme';

export default function LoginScreen() {
  const {signIn, error, clearError} = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);

  const canSubmit = email.trim().length > 0 && password.length >= 8 && !busy;

  // Shown only once they have started typing: the rule is already in the
  // placeholder before that, and a requirement stated as an error against an
  // untouched field reads as a complaint.
  const showPasswordHint = password.length > 0 && password.length < 8;

  async function onSubmit() {
    if (!canSubmit) {
      return;
    }
    setBusy(true);
    try {
      await signIn(email.trim(), password);
    } catch {
      // The error is already surfaced through the auth context.
    } finally {
      setBusy(false);
    }
  }

  return (
    <FormScaffold contentContainerStyle={styles.container}>
        <View style={styles.header}>
          <Text style={styles.logo}>🌾</Text>
          <Text style={styles.title}>AgriLog</Text>
          <Text style={styles.subtitle}>Nhật ký canh tác · Vật tư · Thu chi</Text>
        </View>

        <View style={styles.form}>
          <Text style={styles.label}>Email</Text>
          <TextInput
            style={styles.input}
            value={email}
            onChangeText={t => {
              setEmail(t);
              clearError();
            }}
            autoCapitalize="none"
            autoCorrect={false}
            keyboardType="email-address"
            placeholder="nongho@example.com"
            placeholderTextColor={colors.textDisabled}
            editable={!busy}
          />

          <Text style={styles.label}>Mật khẩu</Text>
          <TextInput
            style={styles.input}
            value={password}
            onChangeText={t => {
              setPassword(t);
              clearError();
            }}
            secureTextEntry
            placeholder="Ít nhất 8 ký tự"
            placeholderTextColor={colors.textDisabled}
            editable={!busy}
            onSubmitEditing={onSubmit}
          />

          {/*
            The button below dims until this rule is met. Without saying so,
            the farmer is left tapping a dead control with nothing on screen
            explaining what is wrong — the commonest way a login screen gets
            abandoned.
          */}
          {showPasswordHint ? (
            <Text style={styles.hintInline}>Mật khẩu cần ít nhất 8 ký tự</Text>
          ) : null}

          {error ? <Text style={styles.error}>{error}</Text> : null}

          <TouchableOpacity
            style={[styles.button, !canSubmit && styles.buttonDisabled]}
            onPress={onSubmit}
            disabled={!canSubmit}
            accessibilityRole="button">
            {busy ? (
              <ActivityIndicator color={colors.textOnPrimary} />
            ) : (
              <Text style={styles.buttonText}>Đăng nhập</Text>
            )}
          </TouchableOpacity>

          {/*
            Stated plainly because it is the app's central promise, and
            because a farmer who does not know it will not trust the app
            enough to rely on it in a field.
          */}
          <Text style={styles.hint}>
            Chỉ cần đăng nhập một lần. Sau đó ứng dụng hoạt động đầy đủ ngay cả khi
            không có mạng.
          </Text>
        </View>
    </FormScaffold>
  );
}

const styles = StyleSheet.create({
  container: {flexGrow: 1, justifyContent: 'center', padding: spacing.lg},
  header: {alignItems: 'center', marginBottom: spacing.xl},
  logo: {fontSize: 56},
  title: {...typography.title, fontSize: 32, color: colors.primaryDark, marginTop: spacing.sm},
  subtitle: {...typography.caption, color: colors.textSecondary, marginTop: spacing.xs},
  form: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: colors.border,
  },
  label: {...typography.label, color: colors.text, marginBottom: spacing.xs, marginTop: spacing.sm},
  input: {
    ...typography.body,
    minHeight: MIN_TOUCH_TARGET,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    color: colors.text,
    backgroundColor: colors.surface,
  },
  error: {...typography.caption, color: colors.danger, marginTop: spacing.md},
  // Secondary, not danger: this is guidance while typing, not a rejection.
  hintInline: {...typography.caption, color: colors.textSecondary, marginTop: spacing.xs},
  button: {
    minHeight: MIN_TOUCH_TARGET,
    backgroundColor: colors.primary,
    borderRadius: radius.md,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: spacing.lg,
  },
  buttonDisabled: {backgroundColor: colors.textDisabled},
  buttonText: {...typography.heading, color: colors.textOnPrimary},
  hint: {
    ...typography.caption,
    color: colors.textSecondary,
    textAlign: 'center',
    marginTop: spacing.md,
    lineHeight: 18,
  },
});
