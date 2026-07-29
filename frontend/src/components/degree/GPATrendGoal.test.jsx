import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import GPATrendGoal from './GPATrendGoal';
import { getGPA, getGPAGoal, getGPAGoalMajor } from '../../api/degree';

// Mock the api module; GPATrendGoal fetches GPA data on mount.
vi.mock('../../api/degree', () => ({
  getGPA: vi.fn(),
  getGPAGoal: vi.fn(),
  getGPAGoalMajor: vi.fn(),
}));

const baseGpa = {
  cumulative_gpa: 7.2,
  term_gpas: [
    { term: 'Fall 2025', gpa: 7.0, credits: 15, course_count: 5 },
    { term: 'Winter 2026', gpa: 7.5, credits: 15, course_count: 5 },
  ],
  total_credits_completed: 30,
  graded_course_count: 10,
  scale_max: 9.0,
  scale_name: 'York 9-point',
  using_fallback: false,
  major_gpas: [],
};

describe('GPATrendGoal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getGPAGoal.mockResolvedValue({ data: null });
    getGPAGoalMajor.mockResolvedValue({ data: null });
  });

  it('renders the GPA trend once data loads', async () => {
    getGPA.mockResolvedValue({ data: baseGpa });

    render(<GPATrendGoal />);

    expect(await screen.findByText('GPA Trend')).toBeInTheDocument();
    expect(screen.getByText('York 9-point')).toBeInTheDocument();
    // The goal-projection section is always shown.
    expect(screen.getByText('Goal Projection')).toBeInTheDocument();
  });

  it('shows an empty-trend message when there are no term GPAs', async () => {
    getGPA.mockResolvedValue({ data: { ...baseGpa, term_gpas: [] } });

    render(<GPATrendGoal />);

    expect(
      await screen.findByText(/Add completed courses with grades across terms/i)
    ).toBeInTheDocument();
  });
});
