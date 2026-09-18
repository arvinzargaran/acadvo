import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router';

import RegisterPage from './RegisterPage';
import { useAuth } from '../context/AuthContext';
import { TERMS_VERSION } from '../legal/config';
import { MINIMUM_AGE } from '../legal/config';

vi.mock('../context/AuthContext', () => ({ useAuth: vi.fn() }));

const register = vi.fn();

/**
 * The consent tick is the only record that the person declared their age and
 * accepted the terms. `required` alone is not enough: it is enforced by the
 * browser's own submit path, so any programmatic submit (a form library, an
 * Enter key on a control that calls requestSubmit, a future refactor) would
 * create an account with no consent behind it. These tests pin the JS guard.
 */
function renderPage() {
  return render(
    <MemoryRouter>
      <RegisterPage />
    </MemoryRouter>
  );
}

function fillCredentials() {
  fireEvent.change(screen.getByLabelText('Full Name'), { target: { value: 'Jane Doe' } });
  fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'jane@example.com' } });
  fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'correct horse battery' } });
  fireEvent.change(screen.getByLabelText('Confirm Password'), {
    target: { value: 'correct horse battery' },
  });
}

// The university field is the searchable combobox: typing alone does not commit
// a value, an option has to be chosen. The program field is a plain <select>.
function fillProgramFields() {
  const combo = screen.getByLabelText('University');
  fireEvent.focus(combo);
  fireEvent.change(combo, { target: { value: 'York' } });
  fireEvent.keyDown(combo, { key: 'ArrowDown' });
  fireEvent.keyDown(combo, { key: 'Enter' });

  fireEvent.change(screen.getByLabelText('Program'), {
    target: { value: 'Computer Science' },
  });
}

describe('RegisterPage consent', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuth.mockReturnValue({ register, user: null });
  });

  it('labels the checkbox and states the age it is declaring', () => {
    renderPage();
    // Resolves through htmlFor/id — an adjacent-but-unassociated label fails.
    const box = screen.getByRole('checkbox', {
      name: new RegExp(`I am ${MINIMUM_AGE} or older`, 'i'),
    });
    expect(box).not.toBeChecked();
    expect(box).toBeRequired();
  });

  it('blocks a programmatic submit while the box is unticked', () => {
    const { container } = renderPage();
    fillCredentials();
    fillProgramFields();

    fireEvent.submit(container.querySelector('form'));

    expect(register).not.toHaveBeenCalled();
    expect(
      screen.getByText(/confirm your age and accept the terms/i)
    ).toBeInTheDocument();
  });

  it('registers once the box is ticked', async () => {
    const { container } = renderPage();
    fillCredentials();
    fillProgramFields();
    fireEvent.click(screen.getByRole('checkbox'));

    fireEvent.submit(container.querySelector('form'));

    // register() is awaited, so let the navigate-on-success settle before asserting.
    await waitFor(() => expect(register).toHaveBeenCalledTimes(1));
    // The acceptance and its version travel with the payload: the server
    // refuses a registration without them, so a client that stops sending them
    // breaks signup entirely.
    expect(register.mock.calls[0][0]).toMatchObject({
      email: 'jane@example.com',
      accepted_terms: true,
      terms_version: TERMS_VERSION,
    });
    expect(
      screen.queryByText(/confirm your age and accept the terms/i)
    ).not.toBeInTheDocument();
  });

  it('unticking the box after ticking it blocks submission again', () => {
    const { container } = renderPage();
    fillCredentials();
    fillProgramFields();

    const box = screen.getByRole('checkbox');
    fireEvent.click(box);
    fireEvent.click(box);

    fireEvent.submit(container.querySelector('form'));

    expect(register).not.toHaveBeenCalled();
  });

  it('links to both documents the tick accepts', () => {
    renderPage();
    expect(screen.getByRole('link', { name: /terms of use/i })).toHaveAttribute('href', '/terms');
    expect(screen.getByRole('link', { name: /privacy policy/i })).toHaveAttribute('href', '/privacy');
  });
});
