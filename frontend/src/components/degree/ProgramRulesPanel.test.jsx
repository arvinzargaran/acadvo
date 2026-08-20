import { describe, it, expect, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import ProgramRulesPanel from './ProgramRulesPanel';
import { getProgramRules } from '../../api/courseAdvisor';

vi.mock('../../api/courseAdvisor', () => ({
  getProgramRules: vi.fn(),
  refreshProgramRules: vi.fn(),
}));

vi.mock('react-hot-toast', () => ({
  default: { success: vi.fn(), error: vi.fn() },
}));

function state(over = {}) {
  return {
    data: {
      university: 'York University',
      program: 'Computer Science',
      state: 'researching',
      message:
        "Acadvo is reading your university's published requirements for your program.",
      research_enabled: true,
      job: { status: 'pending', attempts: 0, last_error: null },
      bucket_count: 0,
      stale: false,
      buckets: [],
      ...over,
    },
  };
}

describe('ProgramRulesPanel', () => {
  beforeEach(() => vi.clearAllMocks());

  it('says what it is doing while research is in flight', async () => {
    getProgramRules.mockResolvedValue(state());
    render(<ProgramRulesPanel />);
    expect(await screen.findByText('Reading your university')).toBeInTheDocument();
    expect(screen.getByText(/reading your university's published requirements/i)).toBeInTheDocument();
  });

  it('shows each rule with the basis spelled out in words', async () => {
    getProgramRules.mockResolvedValue(
      state({
        state: 'ready',
        message: 'Acadvo has requirement rules for 1 bucket(s) in your program.',
        bucket_count: 1,
        buckets: [
          {
            bucket_name: 'Non-Science General Education',
            credits_required: 18.0,
            allowed_subjects: ['AP/HUMA', 'AP/SOSC'],
            level_floor: null,
            excluded_codes: ['AP/ECON 1000'],
            basis: 'stated',
            basis_label: "Read directly from the university's page",
            source_quote: '6.00 credits in AP/HUMA.',
            source_urls: ['https://calendars.students.yorku.ca/rules'],
            stale: false,
          },
        ],
      })
    );

    render(<ProgramRulesPanel />);
    // Rules are behind a disclosure so the panel stays small; open it.
    fireEvent.click(await screen.findByText(/Show 1 requirement rule/));

    await waitFor(() => {
      expect(screen.getByText('Non-Science General Education')).toBeInTheDocument();
    });
    expect(screen.getByText("Read directly from the university's page")).toBeInTheDocument();
    expect(screen.getByText(/Accepts: AP\/HUMA, AP\/SOSC/)).toBeInTheDocument();
    // Exclusions are labelled as exclusions, never listed as options.
    expect(screen.getByText(/Explicitly excluded: AP\/ECON 1000/)).toBeInTheDocument();
  });

  it('is honest, not silent, when the provider is unconfigured', async () => {
    getProgramRules.mockResolvedValue(
      state({
        state: 'unavailable',
        research_enabled: false,
        message:
          'Acadvo has not worked out your program requirement rules, and requirement research is not configured on this server.',
      })
    );
    render(<ProgramRulesPanel />);
    expect(await screen.findByText('Not configured')).toBeInTheDocument();
    // No re-check button to press when there is no provider behind it.
    expect(screen.queryByText('Re-check requirements')).not.toBeInTheDocument();
  });

  it('surfaces why research failed rather than burying it in logs', async () => {
    getProgramRules.mockResolvedValue(
      state({
        state: 'failed',
        message: "Acadvo could not find your program's requirements.",
        job: {
          status: 'failed',
          attempts: 3,
          last_error: 'Research result rejected: no search grounding was returned.',
        },
      })
    );
    render(<ProgramRulesPanel />);
    expect(await screen.findByText('Could not read')).toBeInTheDocument();
    expect(screen.getByText(/no search grounding was returned/)).toBeInTheDocument();
  });

  it('renders nothing when the request fails', async () => {
    getProgramRules.mockRejectedValue(new Error('network'));
    const { container } = render(<ProgramRulesPanel />);
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });
});
