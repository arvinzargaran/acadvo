import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import CatalogStatus from './CatalogStatus';
import { getCatalogStatus } from '../../api/degree';

// Mock the api module the component calls.
vi.mock('../../api/degree', () => ({
  getCatalogStatus: vi.fn(),
}));

describe('CatalogStatus', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the verified state (green) when a seeded catalog exists', async () => {
    getCatalogStatus.mockResolvedValue({
      data: {
        university: 'Simon Fraser University',
        verified: true,
        course_count: 1200,
        last_updated: '2026-07-01T12:00:00Z',
        sources: ['sfu_course_outlines'],
      },
    });

    render(<CatalogStatus />);

    // Verified copy appears once the promise resolves.
    const heading = await screen.findByText(/Verified catalog for Simon Fraser University/i);
    expect(heading).toBeInTheDocument();
    expect(screen.getByText(/1200 verified courses/i)).toBeInTheDocument();
    expect(screen.getByText(/sfu_course_outlines/i)).toBeInTheDocument();
    // Best-effort copy must NOT be present in the verified state.
    expect(screen.queryByText(/Best-effort mode/i)).not.toBeInTheDocument();
  });

  it('renders the best-effort state (amber) when no catalog is seeded', async () => {
    getCatalogStatus.mockResolvedValue({
      data: {
        university: 'Nowhere University',
        verified: false,
        course_count: 0,
        last_updated: null,
        sources: [],
      },
    });

    render(<CatalogStatus />);

    expect(await screen.findByText(/Best-effort mode/i)).toBeInTheDocument();
    expect(screen.getByText(/based on your uploaded courses/i)).toBeInTheDocument();
    expect(screen.getByText(/No verified catalog for Nowhere University yet/i)).toBeInTheDocument();
    // The verified-state grounding copy must NOT appear in best-effort mode.
    expect(screen.queryByText(/grounded in/i)).not.toBeInTheDocument();
  });

  it('renders nothing when the status request fails', async () => {
    getCatalogStatus.mockRejectedValue(new Error('network'));

    const { container } = render(<CatalogStatus />);

    // After the rejected promise settles, the component renders null.
    await waitFor(() => {
      expect(container).toBeEmptyDOMElement();
    });
  });

  it('handles a singular course count without pluralizing', async () => {
    getCatalogStatus.mockResolvedValue({
      data: {
        university: 'Solo U',
        verified: true,
        course_count: 1,
        last_updated: '2026-07-01T12:00:00Z',
        sources: [],
      },
    });

    render(<CatalogStatus />);

    expect(await screen.findByText(/1 verified course(?!s)/i)).toBeInTheDocument();
  });
});
