import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import BucketVerdict from './BucketVerdict';

/**
 * These tests defend one property: a degree-credit claim never reaches the
 * screen without its qualifier and its citation.
 *
 * The server builds `label` with the hedging already in it, so the risk is not
 * that the wording is wrong — it is that a UI drops the label, re-words it, or
 * shows the "Counts" chip on its own. Each test below is one of those.
 */

const SOURCED = ['https://calendars.students.yorku.ca/2025-2026/rules'];

function verdict(over = {}) {
  return {
    bucket_name: 'Non-Science General Education',
    outcome: 'satisfies',
    certainty: 'inferred',
    counts: true,
    is_inference: true,
    reason: 'AP/HUMA 1105 matches the subject rule.',
    rule_basis: 'stated',
    label:
      "Likely counts toward Non-Science General Education. This is Acadvo's " +
      'inference from the requirement’s subject and level rules, not a ' +
      'statement from your university — confirm before you rely on it.',
    source_urls: SOURCED,
    source_quote: '6.00 credits in AP/HUMA and 6.00 credits in AP/SOSC.',
    stale: false,
    credits_required: 18.0,
    ...over,
  };
}

describe('BucketVerdict', () => {
  it('renders nothing when no rule covers the course', () => {
    // Silence is the honest answer. A grey "does not count" would be a claim
    // nobody made.
    const { container } = render(<BucketVerdict verdict={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('keeps the hedge on an inferred verdict', () => {
    render(<BucketVerdict verdict={verdict()} />);
    // Both the chip and the full label hedge — neither alone is enough, because
    // a reader who sees only one of them must still not read it as a fact.
    expect(screen.getByText('Likely counts')).toBeInTheDocument();
    expect(screen.getByText(/not a statement from your university/)).toBeInTheDocument();
    expect(screen.getByText("Acadvo's inference")).toBeInTheDocument();
  });

  it('shows the citation alongside any positive claim', () => {
    render(<BucketVerdict verdict={verdict()} />);
    const link = screen.getByRole('link', { name: 'calendars.students.yorku.ca' });
    expect(link).toHaveAttribute('href', SOURCED[0]);
    // Opened safely, since the URL came from a model-driven research run.
    expect(link).toHaveAttribute('rel', expect.stringContaining('noopener'));
  });

  it('quotes the sentence the rule was read from', () => {
    render(<BucketVerdict verdict={verdict()} />);
    expect(
      screen.getByText(/6.00 credits in AP\/HUMA and 6.00 credits in AP\/SOSC/)
    ).toBeInTheDocument();
  });

  it('drops the inference badge when the university named the course itself', () => {
    render(
      <BucketVerdict
        verdict={verdict({
          certainty: 'stated',
          is_inference: false,
          label: 'Counts toward Non-Science General Education — named in the requirement.',
        })}
      />
    );
    expect(screen.getByText(/named in the requirement/)).toBeInTheDocument();
    expect(screen.queryByText(/Acadvo's inference/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Likely counts/)).not.toBeInTheDocument();
  });

  it('renders an exclusion as a definite no', () => {
    render(
      <BucketVerdict
        verdict={verdict({
          outcome: 'excluded',
          certainty: 'stated',
          counts: false,
          is_inference: false,
          label:
            'Does NOT count toward Non-Science General Education — the requirement explicitly excludes it.',
        })}
      />
    );
    expect(screen.getByText('Does not count')).toBeInTheDocument();
    expect(screen.getByText(/explicitly excludes it/)).toBeInTheDocument();
  });

  it('reports an uncovered course as unknown, not as a refusal', () => {
    render(
      <BucketVerdict
        verdict={verdict({
          outcome: 'no_match',
          counts: false,
          label:
            "Not covered by Acadvo's rule for Non-Science General Education. That is " +
            "not the same as 'does not count' — check with your advisor.",
        })}
      />
    );
    expect(screen.getByText('Not covered')).toBeInTheDocument();
    expect(screen.getByText(/not the same as/)).toBeInTheDocument();
  });

  it('flags a rule that is due for re-checking', () => {
    render(<BucketVerdict verdict={verdict({ stale: true })} />);
    expect(screen.getByText('Needs re-check')).toBeInTheDocument();
  });

  it('collapses to a chip in compact mode, without the bare "Counts" wording', () => {
    render(<BucketVerdict verdict={verdict()} compact />);
    // An inferred verdict must not shorten to an unqualified "Counts".
    expect(screen.getByText('Likely counts')).toBeInTheDocument();
    expect(screen.queryByText(/^Counts$/)).not.toBeInTheDocument();
  });
});
