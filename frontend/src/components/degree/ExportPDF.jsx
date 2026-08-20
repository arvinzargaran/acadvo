const ESCAPES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };

// Everything interpolated below is untrusted: course and bucket names come from
// AI extraction of a user-uploaded transcript, so a crafted document can plant
// markup that would otherwise execute in this same-origin print window.
const esc = (value) =>
  String(value ?? '').replace(/[&<>"']/g, (ch) => ESCAPES[ch]);

export default function ExportPDF({ courses, summary }) {
  const handleExport = () => {
    const grouped = {};
    for (const course of courses) {
      const key = course.term || 'Unscheduled';
      if (!grouped[key]) grouped[key] = [];
      grouped[key].push(course);
    }

    const sortedTerms = Object.keys(grouped).sort();

    const html = `
      <!DOCTYPE html>
      <html>
      <head>
        <title>Degree Plan</title>
        <style>
          body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; padding: 40px; color: #1a1a1a; }
          h1 { font-size: 24px; margin-bottom: 4px; }
          .subtitle { color: #666; font-size: 14px; margin-bottom: 24px; }
          .summary { display: flex; gap: 32px; margin-bottom: 24px; padding: 16px; background: #f5f5f5; border-radius: 8px; }
          .summary-item { text-align: center; }
          .summary-item .value { font-size: 24px; font-weight: bold; }
          .summary-item .label { font-size: 12px; color: #666; }
          h2 { font-size: 16px; margin-top: 24px; margin-bottom: 8px; border-bottom: 1px solid #ddd; padding-bottom: 4px; }
          table { width: 100%; border-collapse: collapse; font-size: 13px; margin-bottom: 16px; }
          th { text-align: left; padding: 6px 8px; background: #f0f0f0; border: 1px solid #ddd; }
          td { padding: 6px 8px; border: 1px solid #ddd; }
          .status-completed { color: #16a34a; }
          .status-in_progress { color: #C96A00; }
          .status-planned { color: #5A6472; }
          .status-not_scheduled { color: #999; }
          .buckets { margin-bottom: 24px; }
          .bucket { display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px solid #eee; font-size: 13px; }
          .progress-bar { width: 100px; height: 8px; background: #e5e5e5; border-radius: 4px; display: inline-block; vertical-align: middle; margin-left: 8px; }
          .progress-fill { height: 100%; background: #1B62F0; border-radius: 0; }
          @media print { body { padding: 20px; } }
        </style>
      </head>
      <body>
        <h1>Degree Plan</h1>
        <p class="subtitle">Exported ${new Date().toLocaleDateString()}</p>

        ${summary ? `
        <div class="summary">
          <div class="summary-item">
            <div class="value">${esc(summary.overall_percentage)}%</div>
            <div class="label">Complete</div>
          </div>
          <div class="summary-item">
            <div class="value">${esc(summary.total_credits_completed)}/${esc(summary.total_credits_required)}</div>
            <div class="label">Credits</div>
          </div>
          ${summary.cumulative_gpa != null ? `
          <div class="summary-item">
            <div class="value">${summary.cumulative_gpa.toFixed(2)}</div>
            <div class="label">GPA</div>
          </div>` : ''}
        </div>
        ` : ''}

        ${summary?.buckets?.length > 0 ? `
        <h2>Requirements</h2>
        <div class="buckets">
          ${summary.buckets.map(b => `
            <div class="bucket">
              <span>${esc(b.bucket_name)}</span>
              <span>
                ${esc(b.credits_completed)}/${esc(b.credits_required)}
                <span class="progress-bar"><span class="progress-fill" style="width:${Math.min(Number(b.percentage) || 0, 100)}%"></span></span>
              </span>
            </div>
          `).join('')}
        </div>
        ` : ''}

        ${sortedTerms.map(term => `
          <h2>${esc(term)}</h2>
          <table>
            <thead><tr><th>Code</th><th>Course</th><th>Credits</th><th>Status</th><th>Grade</th></tr></thead>
            <tbody>
              ${grouped[term].map(c => `
                <tr>
                  <td>${esc(c.course_code)}</td>
                  <td>${esc(c.course_name)}</td>
                  <td>${esc(c.credit_value)}</td>
                  <td class="status-${esc(c.status)}">${esc(String(c.status ?? '').replace('_', ' '))}</td>
                  <td>${esc(c.grade || '—')}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        `).join('')}
      </body>
      </html>
    `;

    const printWindow = window.open('', '_blank');
    // Popup blockers return null; without this the click throws a TypeError.
    if (!printWindow) return;
    printWindow.document.write(html);
    printWindow.document.close();
    printWindow.onload = () => {
      printWindow.print();
    };
  };

  return (
    <button
      onClick={handleExport}
      className="flex items-center gap-2 px-3 py-1.5 bg-dark-800 text-dark-300 hover:text-dark-50 text-sm font-medium rounded-lg hover:bg-dark-700 transition-all border border-dark-700"
    >
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
      Export PDF
    </button>
  );
}
