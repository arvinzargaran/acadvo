import { describe, expect, it } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router';

import PrivacyPage from '../pages/PrivacyPage';
import TermsPage from '../pages/TermsPage';

/**
 * These two documents are the only pages a regulator, a university, or a
 * screen-reader user is likely to read end to end without an account. The
 * structure is the content: a table that reads as a flat list of fragments, or
 * a heading level skipped, makes the policy unreadable to the people most
 * likely to need it.
 */
function renderAt(path, element) {
  return render(<MemoryRouter initialEntries={[path]}>{element}</MemoryRouter>);
}

describe.each([
  ['/privacy', <PrivacyPage key="p" />],
  ['/terms', <TermsPage key="t" />],
])('legal page %s', (path, element) => {
  it('has exactly one h1 and never skips a heading level', () => {
    renderAt(path, element);

    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
    expect(screen.getAllByRole('heading', { level: 2 }).length).toBeGreaterThan(0);
    // A jump from h1 straight to h3 is what makes "next heading" navigation lie
    // about nesting; there is no h3 here at all, so nothing can skip.
    expect(screen.queryAllByRole('heading', { level: 3 })).toHaveLength(0);
  });

  it('puts the body in a main landmark', () => {
    renderAt(path, element);
    expect(screen.getByRole('main')).toBeInTheDocument();
  });

  it('marks the open document in the legal nav', () => {
    renderAt(path, element);
    const nav = screen.getByRole('navigation', { name: /legal documents/i });
    const current = within(nav)
      .getAllByRole('link')
      .filter((link) => link.getAttribute('aria-current') === 'page');
    expect(current).toHaveLength(1);
    expect(current[0]).toHaveAttribute('href', path);
  });

  it('gives every link a purpose from its own text', () => {
    renderAt(path, element);
    for (const link of screen.getAllByRole('link')) {
      expect(link).toHaveAccessibleName();
      expect(link.textContent.trim()).not.toMatch(/^(here|click here|read more|link)$/i);
    }
  });
});

describe('the collection table', () => {
  it('is a real table: named, with column and row headers', () => {
    renderAt('/privacy', <PrivacyPage />);

    const table = screen.getByRole('table');
    expect(table).toHaveAccessibleName(/personal information collected/i);
    expect(within(table).getAllByRole('columnheader').map((c) => c.textContent.trim())).toEqual([
      'What',
      'Why',
      'Kept until',
    ]);
    // Every body row leads with a row header, so a cell read in isolation still
    // says which piece of information it is about.
    const bodyRows = within(table).getAllByRole('row').slice(1);
    expect(bodyRows.length).toBeGreaterThan(0);
    for (const row of bodyRows) {
      expect(within(row).getAllByRole('rowheader')).toHaveLength(1);
    }
  });

  it('scrolls inside its own region, and that region is keyboard reachable', () => {
    renderAt('/privacy', <PrivacyPage />);

    const region = screen.getByRole('region', { name: /personal information collected/i });
    // The scroll lives on the wrapper, not on the document: a 375px viewport
    // must not scroll the whole policy sideways to read one column.
    expect(region.className).toContain('overflow-x-auto');
    // A scrollable box with no tab stop cannot be scrolled without a pointer.
    expect(region).toHaveAttribute('tabindex', '0');
    expect(region).toContainElement(screen.getByRole('table'));
  });
});
