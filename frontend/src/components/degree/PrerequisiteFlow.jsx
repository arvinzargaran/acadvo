const statusDot = {
  completed: 'bg-green-600',
  in_progress: 'bg-primary-500',
  planned: 'bg-sky-500',
  not_scheduled: 'bg-dark-500',
};


function parseTerm(term) {
  if (!term) return { order: 99999, label: 'Unscheduled' };
  const match = term.match(/(\w+)\s+(\d{4})/);
  if (!match) return { order: 50000, label: term };
  const seasonOrder = { winter: 0, spring: 1, summer: 2, fall: 3 };
  const season = match[1].toLowerCase();
  const year = parseInt(match[2], 10);
  return { order: year * 10 + (seasonOrder[season] ?? 5), label: term };
}

/**
 * Group courses by a meaningful key:
 * - Courses with proper semester terms (e.g. "Fall 2025") → group by that term
 * - Courses with short offering codes (e.g. "F", "W", "F or W") → group by status
 */
function groupCourses(courses) {
  const groups = {};

  for (const course of courses) {
    const term = course.term || '';
    const hasProperTerm = /\w+\s+\d{4}/.test(term);

    let key;
    if (hasProperTerm) {
      key = term;
    } else {
      // Group by status for courses without proper semester assignments
      const status = course.status || 'not_scheduled';
      if (status === 'completed') {
        key = `__status__Completed`;
      } else if (status === 'in_progress') {
        key = `__status__In Progress (Current)`;
      } else if (status === 'planned') {
        key = `__status__Planned (Needs Scheduling)`;
      } else {
        key = `__status__Not Scheduled`;
      }
    }

    if (!groups[key]) groups[key] = [];
    groups[key].push(course);
  }

  // Sort groups: proper terms by chronological order, status groups by status order
  const sortedKeys = Object.keys(groups).sort((a, b) => {
    const aIsStatus = a.startsWith('__status__');
    const bIsStatus = b.startsWith('__status__');

    if (!aIsStatus && !bIsStatus) {
      return parseTerm(a).order - parseTerm(b).order;
    }
    if (aIsStatus && bIsStatus) {
      const aStatus = a.includes('Completed') ? 0 : a.includes('In Progress') ? 1 : a.includes('Planned') ? 2 : 3;
      const bStatus = b.includes('Completed') ? 0 : b.includes('In Progress') ? 1 : b.includes('Planned') ? 2 : 3;
      return aStatus - bStatus;
    }
    // Status groups come before proper terms if completed/in-progress, after if planned
    if (aIsStatus) {
      return a.includes('Completed') || a.includes('In Progress') ? -1 : 1;
    }
    return b.includes('Completed') || b.includes('In Progress') ? 1 : -1;
  });

  return sortedKeys.map(key => ({
    key,
    label: key.startsWith('__status__') ? key.replace('__status__', '') : key,
    courses: groups[key],
    isStatusGroup: key.startsWith('__status__'),
  }));
}

export default function PrerequisiteFlow({ courses }) {
  if (!courses || courses.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-dark-400">No courses to visualize.</p>
      </div>
    );
  }

  const groups = groupCourses(courses);

  return (
    <div className="relative">
      {/* Horizontal flow */}
      <div className="overflow-x-auto pb-4">
        <div className="flex gap-0 min-w-max">
          {groups.map((group, groupIdx) => (
            <div key={group.key} className="flex items-start">
              {/* Term column */}
              <div className="w-52 flex-shrink-0">
                <div className="text-center mb-3">
                  <span className={`text-xs font-medium rounded-full px-3 py-1 ${
                    group.isStatusGroup
                      ? 'text-dark-300 bg-dark-700 border border-dark-600'
                      : 'text-dark-400 bg-dark-800 border border-dark-700'
                  }`}>
                    {group.label}
                  </span>
                  <span className="text-dark-500 text-[10px] block mt-1">
                    {group.courses.length} course{group.courses.length !== 1 ? 's' : ''}
                  </span>
                </div>
                <div className="space-y-2 px-2">
                  {group.courses.map(course => (
                    <div
                      key={course.id}
                      className="bg-dark-800 border border-dark-700 rounded-lg p-2.5 hover:border-dark-500 transition-colors"
                      title={`${course.course_code}: ${course.course_name}${course.term ? ` (${course.term})` : ''}`}
                    >
                      <div className="flex items-center gap-2">
                        <div className={`w-2 h-2 rounded-full flex-shrink-0 ${statusDot[course.status] || statusDot.not_scheduled}`} />
                        <span className="text-dark-50 text-xs font-medium truncate">{course.course_code}</span>
                      </div>
                      <p className="text-dark-400 text-[10px] mt-0.5 truncate pl-4">{course.course_name}</p>
                      <div className="flex items-center gap-2 pl-4 mt-0.5">
                        {course.grade && (
                          <span className="text-[10px] text-green-400 font-medium">{course.grade}</span>
                        )}
                        {course.term && group.isStatusGroup && (
                          <span className="text-[10px] text-dark-500">({course.term})</span>
                        )}
                        <span className="text-[10px] text-dark-500">{course.credit_value} cr</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Arrow connector between groups */}
              {groupIdx < groups.length - 1 && (
                <div className="flex items-center self-center px-1 pt-8">
                  <div className="w-6 h-px bg-dark-600" />
                  <svg className="w-3 h-3 text-dark-600 -ml-1" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" />
                  </svg>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Legend */}
      <div className="flex gap-4 mt-4 border-t border-dark-700 pt-3">
        {Object.entries({ completed: 'Completed', in_progress: 'In Progress', planned: 'Planned', not_scheduled: 'Not Scheduled' }).map(([key, label]) => (
          <div key={key} className="flex items-center gap-1.5">
            <div className={`w-2 h-2 rounded-full ${statusDot[key]}`} />
            <span className="text-dark-500 text-[10px]">{label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
