/**
 * App bootstrap smoke test (Issue #17).
 *
 * Asserts the thing that actually matters at launch: an unauthenticated user
 * gets the login screen, and — critically — the app decides that from local
 * storage alone, with no network call. A farmer opening the app in a field
 * with no signal must never be blocked by a startup request.
 */

import React from 'react';
import {act, create} from 'react-test-renderer';

import App from '../App';

// The real module opens SQLite through JSI. The bootstrap path only needs it
// to import cleanly; database behaviour is covered by its own suites.
jest.mock('../src/db', () => ({
  database: {},
}));

// Any fetch during startup is a bug, so it is stubbed to fail loudly rather
// than to return something plausible.
globalThis.fetch = jest.fn(() => {
  throw new Error('App khởi động không được phép gọi mạng');
}) as unknown as typeof fetch;

describe('App', () => {
  afterEach(() => {
    jest.clearAllMocks();
  });

  it('khởi động không lỗi', async () => {
    let tree: ReturnType<typeof create> | undefined;
    await act(async () => {
      tree = create(<App />);
    });
    expect(tree).toBeDefined();
    await act(async () => {
      tree?.unmount();
    });
  });

  it('không gọi mạng khi khởi động', async () => {
    let tree: ReturnType<typeof create> | undefined;
    await act(async () => {
      tree = create(<App />);
    });
    expect(globalThis.fetch).not.toHaveBeenCalled();
    await act(async () => {
      tree?.unmount();
    });
  });

  it('hiện màn hình đăng nhập khi chưa có phiên lưu sẵn', async () => {
    let tree: ReturnType<typeof create> | undefined;
    await act(async () => {
      tree = create(<App />);
    });

    const text = JSON.stringify(tree?.toJSON());
    expect(text).toContain('AgriLog');
    await act(async () => {
      tree?.unmount();
    });
  });
});
