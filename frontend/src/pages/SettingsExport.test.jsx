import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router';

import SettingsPage from './SettingsPage';
import { exportMyData } from '../api/users';
import { useAuth } from '../context/AuthContext';

vi.mock('../context/AuthContext', () => ({ useAuth: vi.fn() }));
vi.mock('../api/client', () => ({ default: { get: vi.fn(), post: vi.fn(), put: vi.fn() } }));
vi.mock('../api/auth', () => ({ resendVerification: vi.fn() }));
vi.mock('../api/users', () => ({
  deleteAccount: vi.fn(),
  changePassword: vi.fn(),
  exportMyData: vi.fn(),
  getCalendarFeed: vi.fn(() => new Promise(() => {})),
  regenerateCalendarFeed: vi.fn(),
}));

/**
 * "Download my data" is the PIPEDA access right in one button, so it has to
 * actually hand over a file. The two ways it silently failed before are both
 * invisible in a happy-path click-through: a blob URL freed in the same tick as
 * the click (the download arrives empty in Firefox and Safari), and an error
 * body that stays a Blob so every failure reads as the generic fallback.
 */
// jsdom 25 ships Blob without `text()`, which every browser has had since 2019.
// Without it the blob-body branch under test can never run here.
if (!Blob.prototype.text) {
  Blob.prototype.text = function text() {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = () => reject(reader.error);
      reader.readAsText(this);
    });
  };
}

describe('Settings — download my data', () => {
  let revoke;

  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers({ shouldAdvanceTime: true });
    useAuth.mockReturnValue({
      user: { full_name: 'Jane', email: 'jane@example.com', email_verified: true },
      setUser: vi.fn(),
      logout: vi.fn(),
    });
    revoke = vi.fn();
    URL.createObjectURL = vi.fn(() => 'blob:mock-url');
    URL.revokeObjectURL = revoke;
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  function renderSettings() {
    return render(
      <MemoryRouter>
        <SettingsPage />
      </MemoryRouter>
    );
  }

  it('keeps the blob URL alive past the click that downloads it', async () => {
    exportMyData.mockResolvedValue({ data: new Blob(['{}'], { type: 'application/json' }) });
    renderSettings();

    fireEvent.click(screen.getByRole('button', { name: /download my data/i }));

    await waitFor(() => expect(URL.createObjectURL).toHaveBeenCalledTimes(1));
    // The download is dispatched after the current task; revoking now would
    // hand the browser a URL that no longer resolves.
    expect(revoke).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(1000);
    expect(revoke).toHaveBeenCalledWith('blob:mock-url');
  });

  it('surfaces the server reason when the failure body is a blob', async () => {
    exportMyData.mockRejectedValue({
      response: {
        status: 429,
        data: new Blob([JSON.stringify({ detail: 'Too many exports. Try again in 60 seconds.' })]),
      },
    });
    renderSettings();

    fireEvent.click(screen.getByRole('button', { name: /download my data/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      /too many exports\. try again in 60 seconds\./i
    );
    // A failed export must not leave a blob URL behind either.
    expect(URL.createObjectURL).not.toHaveBeenCalled();
  });

  it('falls back to a generic message when the failure body is not JSON', async () => {
    exportMyData.mockRejectedValue({
      response: { status: 502, data: new Blob(['<html>Bad Gateway</html>']) },
    });
    renderSettings();

    fireEvent.click(screen.getByRole('button', { name: /download my data/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/failed to prepare your data/i);
  });
});
