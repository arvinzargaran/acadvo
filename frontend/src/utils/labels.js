// Storage vocabulary -> label copy.
//
// The API's enum values are snake_case identifiers meant for the database. Left
// alone they surface in the UI as `IN_PROGRESS`, which is the clearest sign a
// screen was wired straight to a schema and never read by a person. Everything
// a user sees goes through here.

const MILESTONE_STATUS = {
  pending: 'Not started',
  in_progress: 'In progress',
  complete: 'Done',
  overdue: 'Overdue',
};

const TARGET_STATUS = {
  researching: 'Researching',
  applied: 'Applied',
  interviewing: 'Interviewing',
  offer: 'Offer',
  rejected: 'Rejected',
};

// Fallback for enums with no explicit entry: `in_progress` -> `In progress`.
// Sentence case, not Title Case — the latter is its own tell.
function humanize(value) {
  if (!value) return '';
  const spaced = String(value).replace(/[_-]+/g, ' ').trim();
  return spaced.charAt(0).toUpperCase() + spaced.slice(1).toLowerCase();
}

export function milestoneStatusLabel(status) {
  return MILESTONE_STATUS[status] || humanize(status);
}

export function targetStatusLabel(status) {
  return TARGET_STATUS[status] || humanize(status);
}

export { humanize };
