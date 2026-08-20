import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import Modal from './Modal';

/**
 * Three modals in the app were hand-rolled copies of this one — a backdrop div
 * with an onClick, no focus trap, no Escape, no dialog role — and each had to be
 * found by hand. These tests pin what the shared component guarantees, so the
 * next person reaches for it instead of rebuilding it.
 */
describe('Modal', () => {
  it('renders nothing when closed', () => {
    render(<Modal isOpen={false} onClose={() => {}} title="Hidden">body</Modal>);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('is a labelled modal dialog when open', () => {
    render(<Modal isOpen onClose={() => {}} title="Import Degree Document">body</Modal>);
    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    // The accessible name comes from the title, via aria-labelledby.
    expect(dialog).toHaveAccessibleName('Import Degree Document');
  });

  it('closes on Escape', () => {
    const onClose = vi.fn();
    render(<Modal isOpen onClose={onClose} title="T">body</Modal>);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalled();
  });

  it('offers a labelled close button', () => {
    const onClose = vi.fn();
    render(<Modal isOpen onClose={onClose} title="T">body</Modal>);
    fireEvent.click(screen.getByRole('button', { name: /close dialog/i }));
    expect(onClose).toHaveBeenCalled();
  });

  it('hides the click-to-dismiss backdrop from assistive tech', () => {
    /* The backdrop is a mouse convenience. Exposed, it would be an unlabelled
       full-screen control announced ahead of the dialog's real content. */
    const { container } = render(<Modal isOpen onClose={() => {}} title="T">body</Modal>);
    expect(container.querySelector('[aria-hidden="true"]')).toBeInTheDocument();
  });

  it('moves focus into the dialog on open', () => {
    render(
      <Modal isOpen onClose={() => {}} title="T">
        <button type="button">First</button>
      </Modal>
    );
    // Whatever is first in the dialog takes focus — here the close button,
    // which precedes the body in DOM order.
    expect(document.activeElement).toBe(screen.getByRole('button', { name: /close dialog/i }));
  });

  it('honours a wider layout when the content needs one', () => {
    /* The degree-import dialog holds a parsed-data review table and does not fit
       the default. Before widthClass existed it was rebuilt from scratch to get
       the width, and lost the focus trap and Escape handling in the process. */
    render(<Modal isOpen onClose={() => {}} title="T" widthClass="max-w-4xl">body</Modal>);
    expect(screen.getByRole('dialog').className).toContain('max-w-4xl');
  });

  it('defaults to the narrow layout', () => {
    render(<Modal isOpen onClose={() => {}} title="T">body</Modal>);
    expect(screen.getByRole('dialog').className).toContain('max-w-lg');
  });
});
