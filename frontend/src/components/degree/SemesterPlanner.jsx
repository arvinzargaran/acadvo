import { useState } from 'react';
import { generateSemesterPlan, applySemesterPlan } from '../../api/courseAdvisor';
import { getErrorMessage } from '../../utils/errors';

const statusColors = {
  completed: 'bg-green-500/20 border-green-500/40 text-green-300',
  in_progress: 'bg-primary-500/20 border-primary-500/40 text-primary-300',
  planned: 'bg-primary-500/20 border-primary-500/40 text-primary-300',
  not_scheduled: 'bg-dark-700 border-dark-600 text-dark-300',
};

const statusLabels = {
  completed: 'Completed',
  in_progress: 'In Progress',
  planned: 'Planned',
  not_scheduled: 'Not Scheduled',
};

function parseTerm(term) {
  if (!term) return { order: 99999 };
  const match = term.match(/(\w+)\s+(\d{4})/);
  if (!match) return { order: 0 };
  const seasonOrder = { winter: 0, spring: 1, summer: 2, fall: 3 };
  const season = match[1].toLowerCase();
  const year = parseInt(match[2], 10);
  return { order: (year * 10) + (seasonOrder[season] ?? 5) };
}

function ExistingCourses({ courses }) {
  const grouped = {};
  for (const course of courses) {
    const key = course.term || 'Unscheduled';
    if (!grouped[key]) grouped[key] = [];
    grouped[key].push(course);
  }

  const sortedTerms = Object.keys(grouped).sort((a, b) => parseTerm(a).order - parseTerm(b).order);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
      {sortedTerms.map(term => {
        const termCourses = grouped[term];
        const totalCredits = termCourses.reduce((sum, c) => sum + Number(c.credit_value || 0), 0);

        return (
          <div key={term} className="bg-dark-800 border border-dark-700 rounded-xl overflow-hidden">
            <div className="px-4 py-3 border-b border-dark-700 flex items-center justify-between">
              <h3 className="text-dark-50 font-semibold text-sm">{term}</h3>
              <span className="text-dark-400 text-xs">{totalCredits} credits</span>
            </div>
            <div className="p-3 space-y-2">
              {termCourses.map(course => (
                <div
                  key={course.id}
                  className={`px-3 py-2 rounded-lg border text-sm ${statusColors[course.status] || statusColors.not_scheduled}`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium">{course.course_code}</span>
                    <span className="text-xs opacity-70">{course.credit_value} cr</span>
                  </div>
                  <p className="text-xs opacity-80 mt-0.5 truncate">{course.course_name}</p>
                  {course.grade && (
                    <span className="text-xs font-medium mt-1 inline-block">{course.grade}</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function AIPlanView({ plan, onApply, applying }) {
  const [expandedSem, setExpandedSem] = useState(null);

  return (
    <div className="space-y-6">
      {/* Plan summary */}
      {plan.plan_summary && (
        <div className="bg-primary-500/5 border border-dark-600 rounded-xl p-4">
          <h3 className="text-dark-50 font-semibold text-sm mb-1">AI Plan Strategy</h3>
          <p className="text-dark-300 text-sm">{plan.plan_summary}</p>
        </div>
      )}

      {/* Warnings */}
      {plan.warnings?.length > 0 && (
        <div className="space-y-2">
          {plan.warnings.map((w, i) => (
            <div key={i} className="flex items-start gap-2 bg-yellow-500/10 border border-yellow-500/30 rounded-lg px-3 py-2">
              <span className="text-yellow-400 text-sm flex-shrink-0">!</span>
              <p className="text-yellow-300 text-sm">{w}</p>
            </div>
          ))}
        </div>
      )}

      {/* Semester cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {plan.semesters?.map((sem, semIdx) => {
          const totalCredits = sem.courses?.reduce((s, c) => s + (c.credits || 0), 0) || 0;
          const newCourses = sem.courses?.filter(c => !c.already_in_plan) || [];
          const isExpanded = expandedSem === semIdx;

          return (
            <div key={semIdx} className="bg-dark-800 border border-dark-700 rounded-xl overflow-hidden">
              <button
                type="button"
                aria-expanded={isExpanded}
                className="w-full text-left px-4 py-3 border-b border-dark-700 flex items-center justify-between cursor-pointer hover:bg-dark-750 transition-colors"
                onClick={() => setExpandedSem(isExpanded ? null : semIdx)}
              >
                <div>
                  <h3 className="text-dark-50 font-semibold text-sm">{sem.term}</h3>
                  {sem.semester_notes && (
                    <p className="text-dark-500 text-[10px] mt-0.5">{sem.semester_notes}</p>
                  )}
                </div>
                <div className="text-right">
                  <span className="text-dark-400 text-xs">{totalCredits} cr</span>
                  {newCourses.length > 0 && (
                    <span className="text-primary-400 text-[10px] block">+{newCourses.length} new</span>
                  )}
                </div>
              </button>
              <div className="p-3 space-y-2">
                {sem.courses?.map((course, cIdx) => (
                  <div
                    key={cIdx}
                    className={`px-3 py-2 rounded-lg border text-sm ${
                      course.already_in_plan
                        ? 'bg-dark-700/50 border-dark-600 text-dark-400'
                        : 'bg-primary-500/10 border-primary-500/30 text-primary-200'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium">{course.course_code}</span>
                      <div className="flex items-center gap-2">
                        <span className="text-xs opacity-70">{course.credits} cr</span>
                        {course.already_in_plan && (
                          <span className="text-[9px] bg-dark-600 text-dark-400 rounded px-1.5 py-0.5">exists</span>
                        )}
                      </div>
                    </div>
                    <p className="text-xs opacity-80 mt-0.5">{course.course_name}</p>
                    {course.requirement_bucket && (
                      <span className="text-[10px] opacity-60 block mt-0.5">Satisfies: {course.requirement_bucket}</span>
                    )}

                    {/* Expanded details */}
                    {isExpanded && (
                      <div className="mt-2 space-y-1 border-t border-dark-600/50 pt-2">
                        {course.reasoning && (
                          <p className="text-[11px] opacity-70"><span className="text-primary-400">Why: </span>{course.reasoning}</p>
                        )}
                        {course.career_relevance && (
                          <p className="text-[11px] opacity-70"><span className="text-primary-400">Career: </span>{course.career_relevance}</p>
                        )}
                        {course.prerequisites && course.prerequisites !== 'None' && (
                          <p className="text-[11px] opacity-70"><span className="text-yellow-400">Prereqs: </span>{course.prerequisites}</p>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {/* Apply button */}
      {plan.semesters?.some(s => s.courses?.some(c => !c.already_in_plan)) && (
        <div className="flex items-center justify-between bg-dark-800 border border-dark-700 rounded-xl p-4">
          <div>
            <p className="text-dark-50 text-sm font-medium">Apply this plan to your degree</p>
            <p className="text-dark-400 text-xs mt-0.5">
              New courses will be added as "Planned". Existing courses won't be affected.
            </p>
          </div>
          <button
            onClick={() => onApply(plan.semesters)}
            disabled={applying}
            className="px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white text-sm font-medium rounded-lg transition-all disabled:opacity-50"
          >
            {applying ? 'Applying...' : 'Apply Plan'}
          </button>
        </div>
      )}
    </div>
  );
}

export default function SemesterPlanner({ courses, onRefresh }) {
  const [plan, setPlan] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState(null);

  const handleGenerate = async () => {
    setGenerating(true);
    setError(null);
    setPlan(null);
    try {
      const { data } = await generateSemesterPlan();
      setPlan(data);
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to generate plan. Try again.'));
    } finally {
      setGenerating(false);
    }
  };

  const handleApply = async (semesters) => {
    setApplying(true);
    try {
      await applySemesterPlan(semesters);
      setPlan(null);
      if (onRefresh) onRefresh();
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to apply plan.'));
    } finally {
      setApplying(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Generate button */}
      <div className="flex items-center justify-between">
        <div className="flex flex-wrap gap-4">
          {Object.entries(statusLabels).map(([key, label]) => (
            <div key={key} className="flex items-center gap-2">
              <div className={`w-3 h-3 rounded-sm border ${statusColors[key]}`} />
              <span className="text-dark-400 text-xs">{label}</span>
            </div>
          ))}
        </div>
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="flex items-center gap-2 px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white text-sm font-medium rounded-lg transition-all disabled:opacity-50"
        >
          {generating ? (
            <>
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
              Planning with AI...
            </>
          ) : (
            <>
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
              </svg>
              {plan ? 'Regenerate Plan' : 'Generate AI Plan'}
            </>
          )}
        </button>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3">
          <p className="text-red-400 text-sm">{error}</p>
        </div>
      )}

      {generating && (
        <div className="flex flex-col items-center py-16 gap-4">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-primary-500" />
          <div className="text-center">
            <p className="text-dark-50 font-medium">AI is building your semester plan...</p>
            <p className="text-dark-400 text-sm mt-1">Searching your university's course catalog, analyzing prerequisites, and optimizing for your career goals.</p>
          </div>
        </div>
      )}

      {/* Show AI plan if generated */}
      {plan && !generating && (
        <AIPlanView plan={plan} onApply={handleApply} applying={applying} />
      )}

      {/* Always show existing courses below */}
      {!generating && courses.length > 0 && (
        <div>
          {plan && <h3 className="text-dark-50 font-semibold mb-3 text-sm">Current Courses</h3>}
          <ExistingCourses courses={courses} />
        </div>
      )}

      {!generating && !plan && courses.length === 0 && (
        <div className="text-center py-12">
          <p className="text-dark-400">No courses yet.</p>
          <p className="text-dark-500 text-sm mt-2">Click "Generate AI Plan" to get a complete semester-by-semester course plan.</p>
        </div>
      )}
    </div>
  );
}
