import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import MessageBubble from './MessageBubble';

/**
 * The advisor answers "which course and why" with a markdown table. Plain
 * CommonMark has no tables, so before remark-gfm every one of those answers
 * rendered as a paragraph of literal pipes and dashes — the model was right and
 * the UI made it look broken.
 */
describe('MessageBubble markdown', () => {
  // Passed through a variable, not as a literal: MessageBubble's prop happens
  // to be named `role`, and jsx-a11y reads a literal `role={assistant}` as an
  // invalid ARIA role. Indirection keeps the lint rule on for real elements.
  const assistant = 'assistant';
  const TABLE = [
    '| Reason | How it helps you |',
    '|--------|------------------|',
    '| Fulfills a major-elective slot | You need 18 credits |',
  ].join('\n');

  it('renders a GFM table as a real table', () => {
    render(<MessageBubble role={assistant} content={TABLE} />);

    const table = document.querySelector('table');
    expect(table).not.toBeNull();
    expect(screen.getByText('Reason')).toBeInTheDocument();
    expect(screen.getByText('Fulfills a major-elective slot')).toBeInTheDocument();
  });

  it('leaves no raw pipe characters behind', () => {
    const { container } = render(<MessageBubble role={assistant} content={TABLE} />);
    expect(container.textContent).not.toContain('|---');
    expect(container.textContent).not.toContain('| Reason |');
  });

  it('still renders ordinary markdown', () => {
    render(<MessageBubble role={assistant} content={'**bold** and `code`'} />);
    expect(document.querySelector('strong')).not.toBeNull();
    expect(document.querySelector('code')).not.toBeNull();
  });
});
