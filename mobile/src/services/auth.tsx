/**
 * Authentication state (Issue #17).
 *
 * The session is restored from AsyncStorage at launch WITHOUT contacting the
 * server. A farmer opening the app in a field with no signal must land on
 * their data, not on a login screen — the token is long-lived precisely so
 * that this works, and validating it against the network at startup would
 * throw that away.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import React, {createContext, useCallback, useContext, useEffect, useMemo, useState} from 'react';

import {
  ApiError,
  clearTokens,
  getAccessToken,
  getRefreshToken,
  request,
  storeTokens,
} from './api';

export interface Household {
  id: string;
  name: string;
  phone: string | null;
  province: string | null;
  commune: string | null;
}

export interface User {
  id: string;
  household_id: string;
  email: string;
  full_name: string;
  is_active: boolean;
}

interface TokenPair {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  user: User;
  household: Household;
}

interface AuthState {
  status: 'loading' | 'signedIn' | 'signedOut';
  user: User | null;
  household: Household | null;
  error: string | null;
  signIn: (email: string, password: string) => Promise<void>;
  register: (payload: RegisterPayload) => Promise<void>;
  signOut: () => Promise<void>;
  clearError: () => void;
}

export interface RegisterPayload {
  email: string;
  password: string;
  full_name: string;
  household_name: string;
  phone?: string;
  province?: string;
  commune?: string;
}

const USER_KEY = '@agrilog/user';
const HOUSEHOLD_KEY = '@agrilog/household';

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({children}: {children: React.ReactNode}) {
  const [status, setStatus] = useState<AuthState['status']>('loading');
  const [user, setUser] = useState<User | null>(null);
  const [household, setHousehold] = useState<Household | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Restore offline, from storage only.
  useEffect(() => {
    (async () => {
      const [token, stored] = await Promise.all([
        getAccessToken(),
        AsyncStorage.getMany([USER_KEY, HOUSEHOLD_KEY]),
      ]);
      const rawUser = stored[USER_KEY];
      const rawHousehold = stored[HOUSEHOLD_KEY];

      if (token && rawUser && rawHousehold) {
        setUser(JSON.parse(rawUser));
        setHousehold(JSON.parse(rawHousehold));
        setStatus('signedIn');
      } else {
        setStatus('signedOut');
      }
    })();
  }, []);

  const persist = useCallback(async (pair: TokenPair) => {
    await storeTokens(pair.access_token, pair.refresh_token);
    await AsyncStorage.setMany({
      [USER_KEY]: JSON.stringify(pair.user),
      [HOUSEHOLD_KEY]: JSON.stringify(pair.household),
    });
    setUser(pair.user);
    setHousehold(pair.household);
    setStatus('signedIn');
    setError(null);
  }, []);

  const signIn = useCallback(
    async (email: string, password: string) => {
      setError(null);
      try {
        const pair = await request<TokenPair>('/api/v1/auth/login', {
          method: 'POST',
          auth: false,
          body: {email, password},
        });
        await persist(pair);
      } catch (e) {
        setError(
          e instanceof ApiError ? e.message : 'Đăng nhập thất bại. Vui lòng thử lại.',
        );
        throw e;
      }
    },
    [persist],
  );

  const register = useCallback(
    async (payload: RegisterPayload) => {
      setError(null);
      try {
        const pair = await request<TokenPair>('/api/v1/auth/register', {
          method: 'POST',
          auth: false,
          body: payload,
        });
        await persist(pair);
      } catch (e) {
        setError(e instanceof ApiError ? e.message : 'Đăng ký thất bại.');
        throw e;
      }
    },
    [persist],
  );

  const signOut = useCallback(async () => {
    const refresh = await getRefreshToken();

    // Best effort. Logging out with no signal must still work locally —
    // otherwise the farmer is stuck signed in until they find a connection.
    if (refresh) {
      try {
        await request('/api/v1/auth/logout', {
          method: 'POST',
          auth: false,
          body: {refresh_token: refresh},
          timeoutMs: 5_000,
        });
      } catch {
        // ignored on purpose
      }
    }

    await clearTokens();
    await AsyncStorage.removeMany([USER_KEY, HOUSEHOLD_KEY]);
    setUser(null);
    setHousehold(null);
    setStatus('signedOut');
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      status,
      user,
      household,
      error,
      signIn,
      register,
      signOut,
      clearError: () => setError(null),
    }),
    [status, user, household, error, signIn, register, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth phải được dùng bên trong <AuthProvider>');
  }
  return ctx;
}
