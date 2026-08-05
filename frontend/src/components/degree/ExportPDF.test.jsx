import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import ExportPDF from './ExportPDF';

/**
 * The export builds raw HTML and writes it into a same-origin popup, so every
 * interpolated value has to be escaped. Course and bucket names are not
 * user-typed-only — they come out of AI extraction of an uploaded transcript,
 * so a crafted document can plant markup that would run on our origin.
 */
function captureExportedHtml(props) {
  let written = '';
  const fakeWindow = {
    document: {
      write: (html) => {
        written += html;
      },
      close: () => {},
    },
    print: () => {},
  };
  vi.spyOn(window, 'open').mockReturnValue(fakeWindow);

  render(<ExportPDF {...props} />);
  fireEvent.click(screen.getByRole('button'));
  return written;
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe('ExportPDF escaping', () => {
  const payload = '<img src=x onerror="alert(1)">';

  it('escapes malicious course names and codes', () => {
    const html = captureExportedHtml({
      courses: [
        {
          course_code: payload,
          course_name: payload,
          credit_value: 3,
          status: 'completed',
          grade: 'A',
          term: 'Fall 2025',
        },
      ],
      requirements: [],
      summary: null,
    });

    expect(html).not.toContain('<img src=x');
    expect(html).not.toContain('onerror="alert(1)"');
    expect(html).toContain('&lt;img src=x onerror=&quot;alert(1)&quot;&gt;');
  });

  it('escapes the term heading', () => {
    const html = captureExportedHtml({
      courses: [
        {
          course_code: 'CSC148',
          course_name: 'Intro',
          credit_value: 3,
          status: 'completed',
          grade: 'A',
          term: '</h2><script>alert(1)</script>',
        },
      ],
      requirements: [],
      summary: null,
    });

    expect(html).not.toContain('<script>alert(1)</script>');
    expect(html).toContain('&lt;script&gt;');
  });

  it('escapes requirement bucket names', () => {
    const html = captureExportedHtml({
      courses: [],
      requirements: [],
      summary: {
        overall_percentage: 50,
        total_credits_completed: 60,
        total_credits_required: 120,
        cumulative_gpa: null,
        buckets: [
          {
            bucket_name: payload,
            credits_completed: 10,
            credits_required: 20,
            percentage: 50,
          },
        ],
      },
    });

    expect(html).not.toContain('<img src=x');
    expect(html).toContain('&lt;img src=x');
  });

  it('keeps a non-numeric percentage out of the style attribute', () => {
    const html = captureExportedHtml({
      courses: [],
      requirements: [],
      summary: {
        overall_percentage: 50,
        total_credits_completed: 60,
        total_credits_required: 120,
        cumulative_gpa: null,
        buckets: [
          {
            bucket_name: 'Major',
            credits_completed: 10,
            credits_required: 20,
            percentage: '50;background:url(//evil)',
          },
        ],
      },
    });

    expect(html).not.toContain('background:url(//evil)');
    expect(html).toContain('width:0%');
  });

  it('does not throw when the popup is blocked', () => {
    vi.spyOn(window, 'open').mockReturnValue(null);
    render(<ExportPDF courses={[]} requirements={[]} summary={null} />);
    expect(() => fireEvent.click(screen.getByRole('button'))).not.toThrow();
  });
});
