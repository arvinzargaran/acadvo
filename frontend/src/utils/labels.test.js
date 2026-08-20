import { describe, it, expect } from 'vitest';
import { milestoneStatusLabel, targetStatusLabel, humanize } from './labels';

describe('milestoneStatusLabel', () => {
  it('never leaks a snake_case enum to the UI', () => {
    expect(milestoneStatusLabel('in_progress')).toBe('In progress');
  });

  it('maps every status the API can return', () => {
    expect(milestoneStatusLabel('pending')).toBe('Not started');
    expect(milestoneStatusLabel('complete')).toBe('Done');
    expect(milestoneStatusLabel('overdue')).toBe('Overdue');
  });

  it('humanizes an unknown status rather than rendering it raw', () => {
    expect(milestoneStatusLabel('on_hold')).toBe('On hold');
  });

  it('renders nothing for a missing status', () => {
    expect(milestoneStatusLabel(undefined)).toBe('');
    expect(milestoneStatusLabel(null)).toBe('');
  });
});

describe('targetStatusLabel', () => {
  it('maps the career-target statuses', () => {
    expect(targetStatusLabel('researching')).toBe('Researching');
    expect(targetStatusLabel('interviewing')).toBe('Interviewing');
  });
});

describe('humanize', () => {
  it('uses sentence case, not Title Case', () => {
    expect(humanize('NOT_STARTED')).toBe('Not started');
  });

  it('handles hyphenated enums', () => {
    expect(humanize('half-done')).toBe('Half done');
  });
});
