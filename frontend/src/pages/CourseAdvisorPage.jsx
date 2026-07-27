import { useState, useEffect, useRef } from 'react';
import { useAuth } from '../context/AuthContext';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import Skeleton from '../components/ui/Skeleton';
import Spinner from '../components/ui/Spinner';
import {
  searchCourses,
  listRecommendations,
  generateRecommendations,
  acceptRecommendation,
  dismissRecommendation,
  streamSemesterPlan,
  applySemesterPlan,
} from '../api/courseAdvisor';
import { createCourse } from '../api/degree';
import toast from 'react-hot-toast';

const PRIORITY_COLORS = {
  high: 'border-green-500/50 bg-green-500/5',
  medium: 'border-yellow-500/50 bg-yellow-500/5',
  low: 'border-dark-600 bg-dark-800/50',
};

const PRIORITY_BADGES = {
  high: 'bg-green-500/20 text-green-400',
  medium: 'bg-yellow-500/20 text-yellow-400',
  low: 'bg-dark-600 text-dark-400',
};

function buildSemesters(gradYear) {
  const semesters = [];
  const now = new Date();
  const startYear = now.getFullYear();
  const endYear = gradYear || startYear + 4;
  for (let y = startYear; y <= endYear; y++) {
    if (y === startYear && now.getMonth() < 4) semesters.push(`Winter ${y}`);
    if (y >= startYear) semesters.push(`Summer ${y}`);
    semesters.push(`Fall ${y}`);
    if (y < endYear) semesters.push(`Winter ${y + 1}`);
  }
  // Deduplicate
  return [...new Set(semesters)];
}


export default function CourseAdvisorPage() {
  const { user } = useAuth();
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState(null);
  const [searching, setSearching] = useState(false);
  const [selectedSemester, setSelectedSemester] = useState('');
  const [recommendations, setRecommendations] = useState([]);
  const [generating, setGenerating] = useState(false);
  const [loadingRecs, setLoadingRecs] = useState(true);
  const [fullPlan, setFullPlan] = useState(null);
  const [generatingPlan, setGeneratingPlan] = useState(false);
  const [streamingDone, setStreamingDone] = useState(false);
  const [applyingPlan, setApplyingPlan] = useState(false);
  const [planError, setPlanError] = useState(null);
  const [addingCourse, setAddingCourse] = useState(null);
  const [includeSummers, setIncludeSummers] = useState(false);
  const [includeWinters, setIncludeWinters] = useState(true);
  const abortRef = useRef(null);

  const semesters = buildSemesters(user?.expected_graduation_year);

  useEffect(() => {
    if (!selectedSemester && semesters.length) {
      setSelectedSemester(semesters[0]);
    }
  }, [semesters]);

  useEffect(() => {
    loadRecommendations();
  }, []);

  async function loadRecommendations() {
    try {
      const { data } = await listRecommendations();
      setRecommendations(data);
    } finally {
      setLoadingRecs(false);
    }
  }

  async function handleSearch(e) {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    setSearching(true);
    try {
      const { data } = await searchCourses(searchQuery);
      setSearchResults(data.results);
    } catch {
      setSearchResults([]);
    } finally {
      setSearching(false);
    }
  }

  async function handleGenerate() {
    if (!selectedSemester) return;
    setGenerating(true);
    try {
      const { data } = await generateRecommendations(selectedSemester);
      setRecommendations((prev) => [...data, ...prev]);
    } finally {
      setGenerating(false);
    }
  }

  async function handleAccept(id) {
    await acceptRecommendation(id);
    setRecommendations((prev) =>
      prev.map((r) => (r.id === id ? { ...r, accepted: true } : r))
    );
  }

  async function handleDismiss(id) {
    await dismissRecommendation(id);
    setRecommendations((prev) =>
      prev.map((r) => (r.id === id ? { ...r, dismissed: true } : r))
    );
  }

  function handleGenerateFullPlan() {
    // Cancel any in-flight stream
    if (abortRef.current) abortRef.current.abort();

    setGeneratingPlan(true);
    setStreamingDone(false);
    setPlanError(null);
    // Fresh start — always reset (backend generates the full plan each time)
    setFullPlan({ plan_summary: '', semesters: [], warnings: [] });

    const controller = streamSemesterPlan({
      skip_summers: !includeSummers,
      skip_winters: !includeWinters,
    }, (event) => {
      switch (event.type) {
        case 'summary':
          setFullPlan((prev) => ({ ...prev, plan_summary: event.plan_summary }));
          break;
        case 'semester':
          setFullPlan((prev) => ({
            ...prev,
            semesters: [...prev.semesters, event.semester],
          }));
          break;
        case 'warnings':
          setFullPlan((prev) => ({ ...prev, warnings: event.warnings }));
          break;
        case 'done':
          setGeneratingPlan(false);
          setStreamingDone(true);
          break;
        case 'error':
          setGeneratingPlan(false);
          setPlanError(event.message);
          break;
      }
    });
    abortRef.current = controller;
  }

  // Cleanup abort controller on unmount
  useEffect(() => {
    return () => { if (abortRef.current) abortRef.current.abort(); };
  }, []);

  async function handleApplyPlan() {
    if (!fullPlan?.semesters) return;
    setApplyingPlan(true);
    try {
      await applySemesterPlan(fullPlan.semesters);
      setFullPlan(null);
    } catch {
      setPlanError('Failed to apply plan.');
    } finally {
      setApplyingPlan(false);
    }
  }

  const universityName = user?.university || 'your university';

  // Group recommendations by semester
  const activeBySemester = {};
  const savedRecs = [];
  for (const rec of recommendations) {
    if (rec.dismissed) continue;
    if (rec.accepted) continue;
    savedRecs.push(rec);
    if (!activeBySemester[rec.semester]) activeBySemester[rec.semester] = [];
    activeBySemester[rec.semester].push(rec);
  }

  const semesterRecs = activeBySemester[selectedSemester] || [];

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold text-white">Course Advisor</h1>

      {/* Section 0: AI Full Semester Plan */}
      <Card gradient>
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-4">
          <div>
            <h2 className="text-white font-semibold">AI Semester Plan</h2>
            <p className="text-dark-400 text-sm mt-1">
              Generate a complete semester-by-semester course plan from now until graduation.
              The AI searches {universityName}'s catalog, considers prerequisites, balances workload, and aligns with your career goals.
            </p>
          </div>
          <button
            onClick={handleGenerateFullPlan}
            disabled={generatingPlan}
            className="flex items-center gap-2 px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white text-sm font-medium rounded-lg transition-all disabled:opacity-50 flex-shrink-0"
          >
            {generatingPlan ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
                Planning...
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
                </svg>
                Generate Full Plan
              </>
            )}
          </button>
        </div>

        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 mb-4 bg-dark-800/50 rounded-lg px-4 py-2.5">
          <span className="text-dark-400 text-xs font-medium uppercase tracking-wide">Planning Preferences</span>
          <label className="flex items-center gap-2 cursor-pointer">
            <div className="relative">
              <input
                type="checkbox"
                checked={includeSummers}
                onChange={(e) => setIncludeSummers(e.target.checked)}
                className="sr-only peer"
              />
              <div className="w-8 h-[18px] bg-dark-600 rounded-full peer peer-checked:bg-primary-600 transition-colors"></div>
              <div className="absolute top-0.5 left-0.5 w-3.5 h-3.5 bg-white rounded-full transition-transform peer-checked:translate-x-3.5"></div>
            </div>
            <span className="text-dark-300 text-sm">Include Summer</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <div className="relative">
              <input
                type="checkbox"
                checked={includeWinters}
                onChange={(e) => setIncludeWinters(e.target.checked)}
                className="sr-only peer"
              />
              <div className="w-8 h-[18px] bg-dark-600 rounded-full peer peer-checked:bg-primary-600 transition-colors"></div>
              <div className="absolute top-0.5 left-0.5 w-3.5 h-3.5 bg-white rounded-full transition-transform peer-checked:translate-x-3.5"></div>
            </div>
            <span className="text-dark-300 text-sm">Include Winter</span>
          </label>
        </div>

        {planError && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 mb-4 flex items-center justify-between">
            <p className="text-red-400 text-sm">{planError}</p>
            <div className="flex gap-2 flex-shrink-0 ml-3">
              <button
                onClick={handleGenerateFullPlan}
                className="text-xs bg-red-500/20 text-red-400 hover:bg-red-500/30 px-3 py-1.5 rounded-lg transition-colors"
              >
                {fullPlan?.semesters?.length > 0 ? 'Resume Generation' : 'Retry'}
              </button>
            </div>
          </div>
        )}

        {generatingPlan && (!fullPlan?.semesters?.length) && (
          <div className="flex flex-col items-center py-12 gap-4">
            <div className="animate-spin rounded-full h-10 w-10 border-2 border-primary-400/30 border-t-primary-400" />
            <div className="text-center">
              <p className="text-white font-medium">Building your semester plan...</p>
              <p className="text-dark-300 text-sm mt-1">Searching {universityName}'s course catalog, analyzing prerequisites, and optimizing for your goals.</p>
            </div>
          </div>
        )}

        {fullPlan && (fullPlan.semesters?.length > 0 || !generatingPlan) && (
          <div className="space-y-4">
            {fullPlan.plan_summary && (
              <div className="bg-dark-700/50 rounded-lg p-3">
                <p className="text-dark-300 text-sm">{fullPlan.plan_summary}</p>
              </div>
            )}

            {fullPlan.warnings?.length > 0 && (
              <div className="space-y-1">
                {fullPlan.warnings.map((w, i) => (
                  <p key={i} className="text-yellow-400 text-xs flex gap-1.5"><span>!</span> {w}</p>
                ))}
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
              {fullPlan.semesters?.map((sem, i) => {
                const credits = sem.courses?.reduce((s, c) => s + (c.credits || 0), 0) || 0;
                const newCount = sem.courses?.filter(c => !c.already_in_plan).length || 0;
                return (
                  <div key={i} className="bg-dark-800 border border-dark-700 rounded-xl overflow-hidden">
                    <div className="px-3 py-2 border-b border-dark-700 flex items-center justify-between">
                      <span className="text-white font-semibold text-sm">{sem.term}</span>
                      <div className="flex items-center gap-2">
                        <span className="text-dark-400 text-xs">{credits} cr</span>
                        {newCount > 0 && <span className="text-primary-400 text-[10px]">+{newCount} new</span>}
                      </div>
                    </div>
                    <div className="p-2 space-y-1.5">
                      {sem.courses?.map((c, j) => (
                        <div key={j} className={`px-2.5 py-1.5 rounded-lg border text-xs ${c.already_in_plan ? 'bg-dark-700/50 border-dark-600 text-dark-400' : 'bg-primary-500/10 border-primary-500/30 text-primary-200'}`}>
                          <div className="flex justify-between">
                            <span className="font-medium">{c.course_code}</span>
                            <span className="opacity-60">{c.credits} cr</span>
                          </div>
                          <p className="opacity-70 truncate">{c.course_name}</p>
                          {c.reasoning && <p className="opacity-50 mt-0.5 line-clamp-2">{c.reasoning}</p>}
                        </div>
                      ))}
                    </div>
                    {sem.semester_notes && (
                      <div className="px-3 py-1.5 border-t border-dark-700">
                        <p className="text-dark-500 text-[10px]">{sem.semester_notes}</p>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {generatingPlan && fullPlan.semesters?.length > 0 && (
              <div className="bg-dark-800 border border-dark-700 border-dashed rounded-xl overflow-hidden animate-pulse">
                <div className="px-3 py-2 border-b border-dark-700 flex items-center gap-2">
                  <span className="relative flex h-2.5 w-2.5">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-primary-500"></span>
                  </span>
                  <span className="text-dark-400 text-sm">Loading next semester...</span>
                </div>
                <div className="p-2 space-y-1.5">
                  <div className="h-8 bg-dark-700/50 rounded-lg"></div>
                  <div className="h-8 bg-dark-700/30 rounded-lg"></div>
                </div>
              </div>
            )}

            {streamingDone && !generatingPlan && fullPlan.semesters?.some(s => s.courses?.some(c => !c.already_in_plan)) && (
              <div className="flex items-center justify-between bg-dark-700/50 rounded-lg p-3">
                <p className="text-dark-300 text-sm">New courses will be added as "Planned" to your degree.</p>
                <button
                  onClick={handleApplyPlan}
                  disabled={applyingPlan}
                  className="px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white text-sm font-medium rounded-lg transition-all disabled:opacity-50"
                >
                  {applyingPlan ? 'Applying...' : 'Apply Plan to Degree'}
                </button>
              </div>
            )}
          </div>
        )}
      </Card>

      {/* Section 1: Course Search */}
      <Card>
        <h2 className="text-white font-semibold mb-3">Course Search</h2>
        <form onSubmit={handleSearch} className="flex gap-3">
          <input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={`Search ${universityName} courses by name, code, or topic...`}
            className="flex-1 bg-dark-800 border border-dark-600 text-white rounded-lg px-4 py-2.5 text-sm placeholder-dark-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-colors"
          />
          <Button type="submit" loading={searching}>Search</Button>
        </form>

        {searching && (
          <div className="mt-4 space-y-3">
            {[0, 1, 2].map((i) => (
              <div key={i} className="bg-dark-800/50 border border-dark-700 rounded-xl p-4">
                <div className="flex items-center gap-2">
                  <Skeleton className="h-4 w-20" />
                  <Skeleton className="h-4 w-48" />
                </div>
                <Skeleton className="h-3 w-full mt-3" />
                <Skeleton className="h-3 w-2/3 mt-2" />
              </div>
            ))}
          </div>
        )}

        {!searching && searchResults !== null && (
          <div className="mt-4 space-y-3">
            {searchResults.length === 0 ? (
              <p className="text-dark-400 text-sm">No courses found for "{searchQuery}"</p>
            ) : (
              searchResults.map((course, i) => (
                <div key={i} className="bg-dark-800/50 border border-dark-700 rounded-xl p-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-white font-medium text-sm">{course.course_code}</span>
                        <span className="text-dark-300 text-sm">— {course.course_name}</span>
                        <span className="text-dark-500 text-xs">{course.credits} credits</span>
                        {course.in_plan && (
                          <span className="bg-primary-500/20 text-primary-400 text-xs px-2 py-0.5 rounded-full">In your plan</span>
                        )}
                      </div>
                      {course.description && (
                        <p className="text-dark-400 text-sm mt-1">{course.description}</p>
                      )}
                      {course.requirement_bucket && (
                        <p className="text-dark-500 text-xs mt-1">Satisfies: {course.requirement_bucket}</p>
                      )}
                    </div>
                    <div className="flex gap-2 shrink-0">
                      {!course.in_plan && (
                        <button
                          disabled={addingCourse === course.course_code}
                          onClick={async () => {
                            setAddingCourse(course.course_code);
                            try {
                              await createCourse({
                                course_code: course.course_code,
                                course_name: course.course_name,
                                credit_value: course.credits || 3,
                                term: selectedSemester || null,
                                status: 'planned',
                              });
                              setSearchResults(prev =>
                                prev.map(c => c.course_code === course.course_code ? { ...c, in_plan: true } : c)
                              );
                              toast.success(`${course.course_code} added to your plan`);
                            } catch {
                              toast.error('Failed to add course');
                            } finally {
                              setAddingCourse(null);
                            }
                          }}
                          className="text-xs text-primary-400 hover:text-primary-300 transition-colors whitespace-nowrap disabled:opacity-50"
                        >
                          {addingCourse === course.course_code ? 'Adding...' : 'Add to plan'}
                        </button>
                      )}
                      <button
                        onClick={() => window.dispatchEvent(new CustomEvent('open-chat-widget', { detail: { message: `Tell me about ${course.course_code} and whether I should take it given my goals.` } }))}
                        className="text-xs text-dark-400 hover:text-white transition-colors whitespace-nowrap"
                      >
                        Ask advisor
                      </button>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </Card>

      {/* Section 2: AI Recommendations */}
      <Card gradient>
        <div className="flex items-start justify-between gap-4 mb-4">
          <div>
            <h2 className="text-white font-semibold">Get Personalized Recommendations</h2>
            <p className="text-dark-400 text-sm mt-1">
              Your advisor will review your remaining degree requirements, career goals, and current plan — then suggest the best courses to take next.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={selectedSemester}
            onChange={(e) => setSelectedSemester(e.target.value)}
            className="bg-dark-800 border border-dark-600 text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            {semesters.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
          <Button onClick={handleGenerate} loading={generating}>
            Recommend courses for {selectedSemester}
          </Button>
        </div>

        {/* Show recommendations for selected semester */}
        {generating ? (
          <div className="mt-6 space-y-4">
            <div className="flex items-center gap-2 text-dark-400 text-sm">
              <Spinner className="w-4 h-4 text-primary-400" />
              Finding the best courses for {selectedSemester}...
            </div>
            {[0, 1].map((i) => (
              <div key={i} className="border border-dark-700 rounded-xl p-4">
                <div className="flex items-center gap-2">
                  <Skeleton className="h-4 w-20" />
                  <Skeleton className="h-4 w-40" />
                  <Skeleton className="h-4 w-14 rounded-full" />
                </div>
                <Skeleton className="h-3 w-full mt-3" />
                <Skeleton className="h-3 w-3/4 mt-2" />
              </div>
            ))}
          </div>
        ) : semesterRecs.length > 0 ? (
          <div className="mt-6 space-y-4">
            {semesterRecs.map((rec) => (
              <RecommendationCard
                key={rec.id}
                rec={rec}
                onAccept={handleAccept}
                onDismiss={handleDismiss}
              />
            ))}
          </div>
        ) : loadingRecs ? (
          <div className="mt-6 space-y-4">
            {[0, 1].map((i) => (
              <div key={i} className="border border-dark-700 rounded-xl p-4">
                <div className="flex items-center gap-2">
                  <Skeleton className="h-4 w-20" />
                  <Skeleton className="h-4 w-40" />
                  <Skeleton className="h-4 w-14 rounded-full" />
                </div>
                <Skeleton className="h-3 w-full mt-3" />
                <Skeleton className="h-3 w-3/4 mt-2" />
              </div>
            ))}
          </div>
        ) : (
          <div className="mt-6 text-center py-8">
            <p className="text-dark-400 text-sm">No recommendations yet for {selectedSemester}</p>
            <p className="text-dark-500 text-xs mt-1">Click the button above to get personalized suggestions from your AI advisor.</p>
          </div>
        )}
      </Card>

      {/* Section 3: All Saved Recommendations */}
      {savedRecs.length > 0 && (
        <Card>
          <h2 className="text-white font-semibold mb-4">Saved Recommendations</h2>
          <div className="space-y-4">
            {Object.entries(activeBySemester).map(([semester, recs]) => (
              <div key={semester}>
                <h3 className="text-sm font-medium text-dark-300 mb-2">{semester}</h3>
                <div className="space-y-3">
                  {recs.map((rec) => (
                    <RecommendationCard
                      key={rec.id}
                      rec={rec}
                      onAccept={handleAccept}
                      onDismiss={handleDismiss}
                      compact
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}

function RecommendationCard({ rec, onAccept, onDismiss, compact = false }) {
  const borderClass = PRIORITY_COLORS[rec.priority] || PRIORITY_COLORS.medium;
  const badgeClass = PRIORITY_BADGES[rec.priority] || PRIORITY_BADGES.medium;

  return (
    <div className={`border rounded-xl p-4 ${borderClass} transition-all`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-white font-medium">{rec.course_code}</span>
            <span className="text-dark-300 text-sm">{rec.course_name}</span>
            <span className="text-dark-500 text-xs">{rec.credits} credits</span>
            <span className={`text-xs px-2 py-0.5 rounded-full ${badgeClass}`}>{rec.priority}</span>
            {rec.requirement_bucket && (
              <span className="text-xs text-dark-500 bg-dark-800 px-2 py-0.5 rounded-full">{rec.requirement_bucket}</span>
            )}
          </div>
          {!compact && (
            <>
              {rec.reasoning && (
                <p className="text-dark-300 text-sm mt-2">{rec.reasoning}</p>
              )}
              {rec.career_relevance && (
                <p className="text-sm mt-1">
                  <span className="text-dark-500">Career relevance: </span>
                  <span className="text-dark-300">{rec.career_relevance}</span>
                </p>
              )}
              {rec.prerequisite_notes && (
                <p className="text-sm mt-1">
                  <span className="text-dark-500">Prerequisites: </span>
                  <span className="text-dark-400">{rec.prerequisite_notes}</span>
                </p>
              )}
            </>
          )}
        </div>
        <div className="flex gap-2 shrink-0">
          <button
            onClick={() => onAccept(rec.id)}
            className="text-xs bg-green-500/20 text-green-400 hover:bg-green-500/30 px-3 py-1.5 rounded-lg transition-colors"
          >
            Add to plan
          </button>
          <button
            onClick={() => onDismiss(rec.id)}
            className="text-xs text-dark-400 hover:text-red-400 px-2 py-1.5 rounded-lg transition-colors"
          >
            Dismiss
          </button>
        </div>
      </div>
    </div>
  );
}
