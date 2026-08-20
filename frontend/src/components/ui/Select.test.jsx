import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import Select from './Select';

/**
 * The searchable Select is the control that asks a new student for their
 * university and program during onboarding. Before this, it was a text input
 * beside a `<ul>` of `<li onClick>` rows: no roles, no `aria-expanded`, nothing
 * focusable in the list, and the only keyboard path was Enter — which always
 * took the *first* match regardless of what looked highlighted. Someone using a
 * keyboard or a screen reader could not complete onboarding, which means they
 * could not use the app at all.
 *
 * Each test below pins one part of that not coming back.
 */

const UNIVERSITIES = ['York University', 'York St John University', 'Yale University'];

describe('Select (plain)', () => {
  it('associates its label with the control', () => {
    render(<Select label="Program" options={['Computer Science']} />);
    // getByLabelText resolves through htmlFor/id — it fails on a label that is
    // merely adjacent, which is what this used to be.
    expect(screen.getByLabelText('Program').tagName).toBe('SELECT');
  });

  it('marks itself invalid and points at the reason', () => {
    render(<Select label="Program" options={['CS']} error="Pick a program" />);
    const field = screen.getByLabelText('Program');
    expect(field).toHaveAttribute('aria-invalid', 'true');
    const describedBy = field.getAttribute('aria-describedby');
    expect(document.getElementById(describedBy)).toHaveTextContent('Pick a program');
  });
});

describe('Select (searchable)', () => {
  it('exposes itself as a combobox owning a listbox', () => {
    render(<Select label="University" searchable options={UNIVERSITIES} />);
    const combo = screen.getByLabelText('University');

    expect(combo).toHaveAttribute('role', 'combobox');
    expect(combo).toHaveAttribute('aria-expanded', 'false');

    fireEvent.focus(combo);
    expect(combo).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByRole('listbox')).toBeInTheDocument();
    expect(screen.getAllByRole('option')).toHaveLength(3);
  });

  it('selects the highlighted option, not merely the first match', () => {
    const onChange = vi.fn();
    render(<Select label="University" searchable options={UNIVERSITIES} onChange={onChange} />);
    const combo = screen.getByLabelText('University');

    fireEvent.focus(combo);
    fireEvent.change(combo, { target: { value: 'York' } }); // two matches
    fireEvent.keyDown(combo, { key: 'ArrowDown' }); // first
    fireEvent.keyDown(combo, { key: 'ArrowDown' }); // second
    fireEvent.keyDown(combo, { key: 'Enter' });

    expect(onChange).toHaveBeenCalledWith({ target: { value: 'York St John University' } });
  });

  it('tracks the highlight with aria-activedescendant', () => {
    render(<Select label="University" searchable options={UNIVERSITIES} />);
    const combo = screen.getByLabelText('University');

    fireEvent.focus(combo);
    fireEvent.keyDown(combo, { key: 'ArrowDown' });

    const activeId = combo.getAttribute('aria-activedescendant');
    expect(activeId).toBeTruthy();
    expect(document.getElementById(activeId)).toHaveTextContent('York University');
  });

  it('closes on Escape without choosing anything', () => {
    const onChange = vi.fn();
    render(<Select label="University" searchable options={UNIVERSITIES} onChange={onChange} />);
    const combo = screen.getByLabelText('University');

    fireEvent.focus(combo);
    fireEvent.keyDown(combo, { key: 'ArrowDown' });
    fireEvent.keyDown(combo, { key: 'Escape' });

    expect(combo).toHaveAttribute('aria-expanded', 'false');
    expect(onChange).not.toHaveBeenCalled();
  });

  it('filters to what was typed', () => {
    render(<Select label="University" searchable options={UNIVERSITIES} />);
    const combo = screen.getByLabelText('University');

    fireEvent.focus(combo);
    fireEvent.change(combo, { target: { value: 'Yale' } });

    expect(screen.getAllByRole('option')).toHaveLength(1);
    expect(screen.getByRole('option')).toHaveTextContent('Yale University');
  });
});
