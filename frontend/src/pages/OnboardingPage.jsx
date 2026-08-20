/* eslint-disable jsx-a11y/no-autofocus --
 * Every autoFocus in this file is on the single field of a one-question wizard
 * step, or on the first field of a modal that has just opened. That is the case
 * the rule exists to permit: focus moves to the only thing on screen the user
 * came here to do, rather than being stolen from something they were already
 * using. Reviewed site by site; a new autoFocus elsewhere in the app is still
 * an error.
 */
import { useState, useCallback, useMemo, useRef } from 'react';
import { useNavigate } from 'react-router';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuth } from '../context/AuthContext';
import { updateUser } from '../api/users';
import { createRequirement, createCourse } from '../api/degree';
import { createProject } from '../api/projects';
import { createCareerTarget } from '../api/career';
import Input from '../components/ui/Input';
import Select from '../components/ui/Select';
import Button from '../components/ui/Button';
import Modal from '../components/ui/Modal';
import { CANADIAN_UNIVERSITIES } from '../data/universities';
import { PROGRAMS } from '../data/programs';
import { getScale } from '../data/gradingScales';
import FileUploadZone from '../components/degree/FileUploadZone';
import VerifyEmailNotice from '../components/degree/VerifyEmailNotice';

const VALID_STATUSES = new Set(['completed', 'in_progress', 'planned', 'not_scheduled']);
function normalizeStatus(s) {
  if (!s) return 'planned';
  const lower = s.trim().toLowerCase().replace(/\s+/g, '_');
  if (VALID_STATUSES.has(lower)) return lower;
  if (['done', 'passed', 'failed'].includes(lower)) return 'completed';
  if (['enrolled', 'current', 'taking', 'incomplete'].includes(lower)) return 'in_progress';
  return 'planned';
}

const PRIORITY_OPTIONS = [
  { value: '1', label: 'High' },
  { value: '2', label: 'Medium' },
  { value: '3', label: 'Low' },
];

// ── Animation variants ───────────────────────────────────────────

const slideVariants = {
  enter: (dir) => ({ x: dir > 0 ? 60 : -60, opacity: 0 }),
  center: { x: 0, opacity: 1 },
  exit: (dir) => ({ x: dir > 0 ? -60 : 60, opacity: 0 }),
};

const springTransition = { type: 'spring', stiffness: 300, damping: 30, mass: 0.8 };

// ── Question definitions ─────────────────────────────────────────

const QUESTIONS = [
  // 0–6: Profile (one at a time)
  { id: 'name',      section: 'About You',    question: () => `What's your name?`,                     field: 'full_name' },
  { id: 'university', section: 'About You',   question: () => `Which university do you attend?`,        field: 'university' },
  { id: 'program',   section: 'About You',    question: () => `What program are you in?`,               field: 'program' },
  { id: 'years',     section: 'About You',    question: () => `When did you start, and when do you graduate?`, field: '_years', multi: true },
  { id: 'city',      section: 'About You',    question: () => `What city are you based in?`,            field: 'city' },
  { id: 'career',    section: 'About You',    question: () => `What are you working towards?`,          field: 'career_target' },
  // 7: Degree upload
  { id: 'degree',    section: 'Degree',       question: () => `Upload your degree checklist`,           field: '_degree' },
  // 8: Courses review
  { id: 'courses',   section: 'Courses',      question: () => `Which courses have you completed, and which are in progress?`, field: '_courses' },
  // 9: Projects
  { id: 'projects',  section: 'Projects',     question: () => `Any portfolio projects?`,                field: '_projects' },
  // 10: Career targets
  { id: 'targets',   section: 'Career',       question: () => `Companies you're targeting`,             field: '_targets' },
  // 11: Review + Launch
  { id: 'review',    section: 'Launch',        question: () => `You're all set — ready to launch?`,     field: '_review' },
];

const TOTAL_STEPS = QUESTIONS.length;

// ── Main Component ───────────────────────────────────────────────

export default function OnboardingPage() {
  const { user, setUser, logout } = useAuth();
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [direction, setDirection] = useState(1);
  const [hasNavigated, setHasNavigated] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const [profile, setProfile] = useState({
    full_name: user?.full_name || '',
    university: user?.university || '',
    program: user?.program || '',
    start_year: '',
    expected_graduation_year: '',
    country: 'Canada',
    city: '',
    career_target: '',
  });

  const [buckets, setBuckets] = useState([]);
  const [courses, setCourses] = useState([]);
  const [projects, setProjects] = useState([]);
  const [careerTargets, setCareerTargets] = useState([]);

  // Memoize per-field handlers to avoid re-creating on every render
  const fieldHandlers = useRef({});
  const up = useCallback((field) => {
    if (!fieldHandlers.current[field]) {
      fieldHandlers.current[field] = (e) => {
        const val = e?.target?.value ?? e;
        setProfile((p) => ({ ...p, [field]: val }));
      };
    }
    return fieldHandlers.current[field];
  }, []);

  // List helpers
  function updateListItem(setter) {
    return (index, field, value) =>
      setter((list) => list.map((item, i) => (i === index ? { ...item, [field]: value } : item)));
  }
  function addListItem(setter, template) {
    return () => setter((list) => [...list, { ...template }]);
  }
  function removeListItem(setter) {
    return (index) => setter((list) => list.filter((_, i) => i !== index));
  }

  const updateCourse = updateListItem(setCourses);
  const removeCourse = removeListItem(setCourses);

  const updateProject = updateListItem(setProjects);
  const addProject = addListItem(setProjects, {
    name: '', description: '', priority: '2', tech_stack: '', hard_deadline: '',
  });
  const removeProject = removeListItem(setProjects);

  const updateTarget = updateListItem(setCareerTargets);
  const addTarget = addListItem(setCareerTargets, {
    company_name: '', role_type: '', location: '', target_term: '',
  });
  const removeTarget = removeListItem(setCareerTargets);

  // ── Validation per step ──────────────────────────────────────

  function canContinue() {
    const q = QUESTIONS[step];
    switch (q.id) {
      case 'name':       return profile.full_name.trim().length >= 2;
      case 'university': return profile.university.trim().length > 0;
      case 'program':    return profile.program.trim().length > 0;
      case 'years': {
        const sy = parseInt(profile.start_year);
        const gy = parseInt(profile.expected_graduation_year);
        return sy >= 2000 && sy <= 2100 && gy >= sy && gy <= 2100;
      }
      default:           return true; // city, career, degree, courses, projects, targets, review are all optional/skippable
    }
  }

  function goNext() {
    if (!canContinue()) return;
    setHasNavigated(true);
    setDirection(1);
    setStep((s) => Math.min(s + 1, TOTAL_STEPS - 1));
  }

  function goBack() {
    setHasNavigated(true);
    setDirection(-1);
    setStep((s) => Math.max(s - 1, 0));
  }

  function goTo(target) {
    setHasNavigated(true);
    setDirection(target > step ? 1 : -1);
    setStep(target);
  }

  // Handle Enter key for single-field steps
  function handleStepSubmit(e) {
    // Steps that are a single field wrap it in a <form>, so Enter advances the
    // wizard natively. This used to be an onKeyDown on the wrapping <div>: it
    // worked for a sighted mouse-and-keyboard user and for nobody else — a div
    // with a key handler is not an interactive element, and mobile keyboards
    // showed no "Go" key because there was no form to submit.
    e.preventDefault();
    if (canContinue() && step < TOTAL_STEPS - 1) goNext();
  }

  // ── Document parsed handler ──────────────────────────────────

  function handleDocumentParsed(data) {
    if (data.requirements?.length) {
      setBuckets(data.requirements.map((r) => ({
        bucket_name: r.bucket_name,
        credits_required: String(r.credits_required),
      })));
    }
    if (data.courses?.length) {
      setCourses(data.courses.map((c) => ({
        course_code: c.course_code || '',
        course_name: c.course_name || '',
        credit_value: String(c.credit_value || ''),
        requirement_bucket: c.requirement_bucket || '',
        term: c.term || '',
        status: normalizeStatus(c.status),
        grade: c.grade || '',
      })));
    }
    // Auto-advance to courses review
    setTimeout(() => { setDirection(1); setStep(7); }, 600);
  }

  // ── Submit ───────────────────────────────────────────────────

  async function handleSubmit() {
    setSaving(true);
    setError('');
    try {
      const profileData = {
        ...profile,
        start_year: profile.start_year ? parseInt(profile.start_year) : null,
        expected_graduation_year: profile.expected_graduation_year ? parseInt(profile.expected_graduation_year) : null,
      };
      await updateUser(profileData);

      const validBuckets = buckets.filter((b) => b.bucket_name && b.credits_required);
      const bucketMap = {};
      for (const bucket of validBuckets) {
        const { data } = await createRequirement({
          bucket_name: bucket.bucket_name,
          credits_required: parseFloat(bucket.credits_required),
        });
        bucketMap[bucket.bucket_name] = data.id;
      }

      const validCourses = courses.filter((c) => c.course_code && c.course_name);
      for (const course of validCourses) {
        await createCourse({
          course_code: course.course_code,
          course_name: course.course_name,
          credit_value: parseFloat(course.credit_value) || 0.5,
          requirement_bucket_id: bucketMap[course.requirement_bucket] || null,
          term: course.term || null,
          status: normalizeStatus(course.status),
          grade: course.grade || null,
        });
      }

      const validProjects = projects.filter((p) => p.name);
      for (const project of validProjects) {
        await createProject({
          name: project.name,
          description: project.description || null,
          priority: parseInt(project.priority) || 2,
          status: 'not_started',
          tech_stack: project.tech_stack || null,
          hard_deadline: project.hard_deadline || null,
        });
      }

      const validTargets = careerTargets.filter((t) => t.company_name);
      for (const target of validTargets) {
        await createCareerTarget({
          company_name: target.company_name,
          role_type: target.role_type || null,
          location: target.location || null,
          target_term: target.target_term || null,
        });
      }

      const { data: updatedUser } = await updateUser({ onboarding_complete: true });
      setUser(updatedUser);
      navigate('/dashboard');
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map(d => d.msg).join(', ') : 'Something went wrong. Please try again.');
    } finally {
      setSaving(false);
    }
  }

  // ── Render step content ──────────────────────────────────────

  const q = QUESTIONS[step];
  const progress = ((step + 1) / TOTAL_STEPS) * 100;

  function renderContent() {
    switch (q.id) {
      case 'name':
        return (
          <form className="w-full max-w-md" onSubmit={handleStepSubmit}>
            <Input
              value={profile.full_name}
              onChange={up('full_name')}
              placeholder="Your full name"
              className="!text-lg !py-3"
              autoFocus
            />
          </form>
        );
      case 'university':
        return (
          <div className="w-full max-w-md">
            <Select
              searchable
              options={CANADIAN_UNIVERSITIES}
              value={profile.university}
              onChange={up('university')}
              placeholder="Search your university..."
            />
          </div>
        );
      case 'program':
        return (
          <div className="w-full max-w-md">
            <Select
              options={PROGRAMS}
              value={profile.program}
              onChange={up('program')}
              placeholder="Select your program"
            />
          </div>
        );
      case 'years':
        return (
          <form className="w-full max-w-md flex gap-4" onSubmit={handleStepSubmit}>
            <Input
              label="Start Year"
              type="number"
              value={profile.start_year}
              onChange={up('start_year')}
              placeholder="e.g. 2023"
              autoFocus
            />
            <Input
              label="Graduation Year"
              type="number"
              value={profile.expected_graduation_year}
              onChange={up('expected_graduation_year')}
              placeholder="e.g. 2027"
            />
          </form>
        );
      case 'city':
        return (
          <form className="w-full max-w-md" onSubmit={handleStepSubmit}>
            <Input
              value={profile.city}
              onChange={up('city')}
              placeholder="e.g. Toronto"
              autoFocus
            />
          </form>
        );
      case 'career':
        return (
          <div className="w-full max-w-md">
            <textarea
              value={profile.career_target}
              onChange={up('career_target')}
              placeholder="e.g. Land a SWE internship at a FAANG company by Summer 2027"
              rows={3}
              autoFocus
              className="w-full bg-dark-800 border border-dark-600 text-dark-50 rounded-xl px-4 py-3 text-base placeholder-dark-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-colors resize-none"
            />
          </div>
        );
      case 'degree':
        return (
          <div className="w-full max-w-lg">
            {/* Said "PDF or image" while the dropzone underneath advertised
                Excel and CSV — the exact formats a degree checklist usually
                arrives in. Kept in step with FileUploadZone's `accept`. */}
            <p className="text-dark-400 text-sm mb-4 text-center">
              Upload a degree checklist, academic calendar, or transcript — PDF,
              image, Excel, or CSV.
              <br />
              <span className="text-dark-500">We'll auto-extract your requirements and courses.</span>
            </p>
            <VerifyEmailNotice feature="checklist parsing" />
            <FileUploadZone onParsed={handleDocumentParsed} />
            {buckets.length > 0 && (
              <div className="mt-4 bg-green-500/10 border border-green-500/20 rounded-xl p-3 text-center">
                <p className="text-green-400 text-sm font-medium">
                  Parsed {buckets.length} requirement{buckets.length !== 1 ? 's' : ''} and {courses.length} course{courses.length !== 1 ? 's' : ''}
                </p>
              </div>
            )}
          </div>
        );
      case 'courses':
        return <CoursesPanel courses={courses} updateCourse={updateCourse} removeCourse={removeCourse} setCourses={setCourses} />;
      case 'projects':
        return <ProjectsPanel projects={projects} updateProject={updateProject} addProject={addProject} removeProject={removeProject} />;
      case 'targets':
        return <TargetsPanel targets={careerTargets} updateTarget={updateTarget} addTarget={addTarget} removeTarget={removeTarget} />;
      case 'review':
        return <ReviewPanel profile={profile} buckets={buckets} courses={courses} projects={projects} targets={careerTargets} onEdit={goTo} />;
      default:
        return null;
    }
  }

  return (
    <div className="min-h-screen bg-dark-950 flex flex-col overflow-x-hidden">
      {/* Progress bar */}
      <div className="h-1 bg-dark-800 w-full">
        <motion.div
          className="h-full bg-[var(--wf-live)]"
          animate={{ width: `${progress}%` }}
          transition={{ duration: 0.4, ease: 'easeOut' }}
        />
      </div>

      {/* Top bar */}
      <div className="px-6 py-4 flex items-center justify-between">
        <div className="flex items-baseline gap-3">
          <span className="text-xl font-bold font-display text-primary-600 tracking-tight">Acadvo</span>
          <span className="text-dark-400 text-xs font-semibold uppercase tracking-[0.18em] tabular-nums">
            Step {step + 1} / {TOTAL_STEPS}
          </span>
        </div>
        <button
          onClick={async () => {
            if (!window.confirm('Leave setup? Your progress on this page will be lost.')) return;
            await logout();
            navigate('/');
          }}
          className="flex items-center gap-1.5 text-dark-400 hover:text-dark-50 text-sm transition-colors"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
          </svg>
          Sign Out
        </button>
      </div>

      {/* Main content — centered */}
      <div className="flex-1 flex flex-col items-center justify-center px-6 pb-32">
        <AnimatePresence mode="wait" custom={direction}>
          <motion.div
            key={step}
            custom={direction}
            variants={slideVariants}
            initial={hasNavigated ? "enter" : false}
            animate="center"
            exit="exit"
            transition={springTransition}
            className="w-full flex flex-col items-center text-center"
          >
            {/* Section label */}
            <p className="eyebrow mb-3">
              {q.section}
            </p>

            {/* Question */}
            <h1 className="font-display text-3xl sm:text-4xl tracking-tight text-dark-50 mb-8 max-w-xl leading-[1.15]">
              {q.question(profile)}
            </h1>

            {/* Input area */}
            {renderContent()}
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Bottom nav */}
      <div className="fixed bottom-0 inset-x-0 bg-dark-950/80 backdrop-blur-xl border-t border-dark-800">
        <div className="max-w-xl mx-auto flex items-center justify-between px-6 py-4">
          <button
            onClick={goBack}
            disabled={step === 0}
            className={`flex items-center gap-1.5 text-sm font-medium transition-colors ${
              step === 0 ? 'text-dark-600 cursor-not-allowed' : 'text-dark-400 hover:text-dark-50'
            }`}
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Back
          </button>

          {error && <p className="text-red-400 text-xs max-w-[200px] truncate">{error}</p>}

          {step < TOTAL_STEPS - 1 ? (
            <button
              onClick={goNext}
              disabled={!canContinue()}
              className={`flex items-center gap-1.5 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all ${
                canContinue()
                  ? 'btn-accent'
                  : 'bg-dark-800 text-dark-500 cursor-not-allowed'
              }`}
            >
              {['city', 'career', 'degree', 'courses', 'projects', 'targets'].includes(q.id) ? 'Continue' : 'Next'}
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </button>
          ) : (
            <Button onClick={handleSubmit} loading={saving}>
              Launch Dashboard
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Multi-item panels (scrollable, within the centered layout) ──

const STATUS_CYCLE = ['planned', 'completed', 'in_progress'];

function CoursesPanel({ courses, updateCourse, removeCourse, setCourses }) {
  const { user } = useAuth();
  // The grade buttons below were a hardcoded York letter set — including E,
  // which most schools do not use — offered to every student during the one
  // step where they enter their grades. A student elsewhere picked a letter
  // their own scale has no entry for, and the backend then dropped that course
  // from their GPA with only a server-side log to show for it. Every other
  // grade picker in the app already resolves the scale from the profile.
  const { scale } = useMemo(() => getScale(user?.university), [user?.university]);
  const gradeOptions = useMemo(
    () => [...scale.grades.map((g) => g.letter), 'Pass', 'Fail'],
    [scale]
  );
  const [showAddModal, setShowAddModal] = useState(false);
  const [newCourse, setNewCourse] = useState({ course_code: '', course_name: '', credit_value: '3.0' });

  function cycleStatus(i) {
    const current = courses[i].status || 'planned';
    const idx = STATUS_CYCLE.indexOf(current);
    const next = STATUS_CYCLE[(idx + 1) % STATUS_CYCLE.length];
    updateCourse(i, 'status', next);
    // Clear grade if no longer completed
    if (next !== 'completed') updateCourse(i, 'grade', '');
  }

  function handleAddManual() {
    if (!newCourse.course_code.trim()) return;
    setCourses((prev) => [...prev, {
      course_code: newCourse.course_code,
      course_name: newCourse.course_name,
      credit_value: newCourse.credit_value || '3.0',
      requirement_bucket: '',
      term: '',
      status: 'planned',
      grade: '',
    }]);
    setNewCourse({ course_code: '', course_name: '', credit_value: '3.0' });
    setShowAddModal(false);
  }

  return (
    <div className="w-full max-w-3xl text-left">
      <p className="text-dark-400 text-sm mb-4 text-center">
        {courses.length > 0
          ? `Tap a course to mark it as completed (with your grade) or in progress.`
          : 'No courses yet. Add your past and current courses manually to track your progress.'}
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 max-h-[50vh] overflow-y-auto pr-1 pb-1">
        {courses.map((course, i) => {
          const isCompleted = course.status === 'completed';
          const isInProgress = course.status === 'in_progress';
          return (
            <div
              key={i}
              className={`relative rounded-xl border p-4 transition-all duration-200 cursor-pointer group ${
                isCompleted
                  ? 'bg-green-500/10 border-green-500/30 shadow-lg shadow-green-500/5'
                  : isInProgress
                    ? 'bg-amber-500/10 border-amber-500/30 shadow-lg shadow-amber-500/5'
                    : 'bg-white/5 border-white/10 hover:border-white/20'
              }`}
            >
              {/* Status icon — top right */}
              <div className="absolute top-3 right-3 flex items-center gap-1.5">
                {isCompleted && (
                  <svg className="w-4.5 h-4.5 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                  </svg>
                )}
                {isInProgress && (
                  <svg className="w-4.5 h-4.5 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                )}
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); removeCourse(i); }}
                  aria-label={`Remove ${course.course_code || 'this course'}`}
                  // Hidden until hover left it unreachable by keyboard; it now
                  // also appears on focus.
                  className="opacity-0 transition-all group-hover:opacity-100 focus-visible:opacity-100 text-dark-500 hover:text-red-400"
                >
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              {/* Clickable area. A real button, not a div with onClick: this is
                  the primary action of the step ("Tap a course to mark it as
                  completed") and as a bare div it was unreachable by keyboard
                  entirely — no focus, no Enter, nothing in the a11y tree. */}
              <button
                type="button"
                onClick={() => cycleStatus(i)}
                aria-label={`${course.course_code || 'Untitled'} — ${
                  isCompleted ? 'completed' : isInProgress ? 'in progress' : 'not started'
                }. Activate to change status.`}
                className="block w-full text-left"
              >
                <p className="text-dark-50 font-semibold text-sm pr-8">{course.course_code || 'Untitled'}</p>
                <p className="text-dark-400 text-xs mt-0.5 truncate">{course.course_name}</p>
                <div className="flex items-center gap-2 mt-2">
                  <span className="text-dark-500 text-[10px]">{course.credit_value || '?'} cr</span>
                  {course.term && <span className="text-dark-500 text-[10px]">{course.term}</span>}
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                    isCompleted ? 'bg-green-500/20 text-green-400'
                      : isInProgress ? 'bg-amber-500/20 text-amber-400'
                        : 'bg-dark-700 text-dark-400'
                  }`}>
                    {isCompleted ? 'Completed' : isInProgress ? 'In Progress' : 'Not Started'}
                  </span>
                </div>
              </button>

              {/* Grade selector — only when completed */}
              {isCompleted && (
                <div className="mt-3 pt-3 border-t border-white/5">
                  {/* Wraps rather than scrolling. This was a 468px strip inside
                      a 209px card with `scrollbar-hide`, so the grades below B
                      were cut off mid-letter with nothing on screen to suggest
                      more existed — an invisible scroll in a picker where you
                      have to see every option to choose one. */}
                  <div className="flex flex-wrap gap-1.5 pb-0.5">
                    {gradeOptions.map((g) => (
                      <button
                        key={g}
                        onClick={(e) => { e.stopPropagation(); updateCourse(i, 'grade', g); }}
                        className={`flex-shrink-0 px-2.5 py-1 rounded-lg text-xs font-semibold transition-all ${
                          course.grade === g
                            ? 'bg-green-500 text-white'
                            : 'bg-white/5 text-dark-300 hover:bg-white/10 hover:text-dark-50'
                        }`}
                      >
                        {g}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          );
        })}

        {/* Add Course tile */}
        <button
          onClick={() => setShowAddModal(true)}
          className="rounded-xl border-2 border-dashed border-white/10 hover:border-primary-500/40 bg-white/[0.02] hover:bg-primary-500/5 p-4 flex flex-col items-center justify-center gap-2 transition-all min-h-[100px]"
        >
          <svg className="w-6 h-6 text-dark-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 4v16m8-8H4" />
          </svg>
          <span className="text-dark-400 text-xs font-medium">Add Course</span>
        </button>
      </div>

      {/* Add Course Modal.
          Was a hand-rolled overlay: a click-to-close backdrop div (unreachable
          by keyboard), no focus trap, no Escape, no dialog role. The shared
          Modal already solves all four, and this is the only place in the app
          that had rebuilt it. */}
      <Modal
        isOpen={showAddModal}
        onClose={() => setShowAddModal(false)}
        title="Add a Course"
      >
        <div>
            <div className="space-y-3">
              <Input
                label="Course Code"
                value={newCourse.course_code}
                onChange={(e) => setNewCourse(p => ({ ...p, course_code: e.target.value }))}
                placeholder="e.g. EECS 3101"
                autoFocus
              />
              <Input
                label="Course Name"
                value={newCourse.course_name}
                onChange={(e) => setNewCourse(p => ({ ...p, course_name: e.target.value }))}
                placeholder="e.g. Design & Analysis of Algorithms"
              />
              <Input
                label="Credits"
                type="number"
                step="0.5"
                value={newCourse.credit_value}
                onChange={(e) => setNewCourse(p => ({ ...p, credit_value: e.target.value }))}
                placeholder="3.0"
              />
            </div>
            <div className="flex justify-end gap-3 mt-5">
              <button onClick={() => setShowAddModal(false)} className="px-4 py-2 text-dark-400 text-sm hover:text-dark-50 transition-colors">Cancel</button>
              <button
                onClick={handleAddManual}
                disabled={!newCourse.course_code.trim()}
                className={`px-4 py-2 rounded-xl text-sm font-semibold transition-all ${
                  newCourse.course_code.trim()
                    ? 'bg-primary-600 hover:bg-primary-700 text-white'
                    : 'bg-dark-700 text-dark-500 cursor-not-allowed'
                }`}
              >
                Add Course
              </button>
            </div>
        </div>
      </Modal>
    </div>
  );
}

function ProjectsPanel({ projects, updateProject, addProject, removeProject }) {
  return (
    <div className="w-full max-w-2xl text-left">
      <p className="text-dark-400 text-sm mb-4 text-center">
        Add projects you're working on or plan to build. You can skip this.
      </p>
      <div className="space-y-3 max-h-[40vh] overflow-y-auto pr-1">
        {projects.map((project, i) => (
          <div key={i} className="bg-dark-800/80 border border-dark-700 rounded-xl p-4 space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-xs text-dark-500 font-medium">Project {i + 1}</span>
              <button onClick={() => removeProject(i)} className="text-dark-500 hover:text-red-400 transition-colors">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Input label="Project Name" value={project.name} onChange={(e) => updateProject(i, 'name', e.target.value)} placeholder="My App" />
              <Select label="Priority" options={PRIORITY_OPTIONS} value={project.priority} onChange={(e) => updateProject(i, 'priority', e.target.value)} />
              <Input label="Tech Stack" value={project.tech_stack} onChange={(e) => updateProject(i, 'tech_stack', e.target.value)} placeholder="React, Python" />
              <Input label="Deadline" type="date" value={project.hard_deadline} onChange={(e) => updateProject(i, 'hard_deadline', e.target.value)} />
            </div>
            <textarea
              value={project.description}
              onChange={(e) => updateProject(i, 'description', e.target.value)}
              placeholder="What does this project do?"
              rows={2}
              className="w-full bg-dark-800 border border-dark-600 text-dark-50 rounded-lg px-3 py-2 text-sm placeholder-dark-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-colors resize-none"
            />
          </div>
        ))}
      </div>
      <button onClick={addProject} className="mt-3 text-sm text-primary-400 hover:text-primary-300 transition-colors font-medium">+ Add Project</button>
    </div>
  );
}

function TargetsPanel({ targets, updateTarget, addTarget, removeTarget }) {
  return (
    <div className="w-full max-w-2xl text-left">
      <p className="text-dark-400 text-sm mb-4 text-center">
        Add companies you're targeting for internships or full-time roles. You can skip this.
      </p>
      <div className="space-y-3 max-h-[40vh] overflow-y-auto pr-1">
        {targets.map((target, i) => (
          <div key={i} className="bg-dark-800/80 border border-dark-700 rounded-xl p-4">
            <div className="flex justify-between items-center mb-3">
              <span className="text-xs text-dark-500 font-medium">Target {i + 1}</span>
              <button onClick={() => removeTarget(i)} className="text-dark-500 hover:text-red-400 transition-colors">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <Input label="Company" value={target.company_name} onChange={(e) => updateTarget(i, 'company_name', e.target.value)} placeholder="Google" />
              <Input label="Role" value={target.role_type} onChange={(e) => updateTarget(i, 'role_type', e.target.value)} placeholder="SWE Intern" />
              <Input label="Location" value={target.location} onChange={(e) => updateTarget(i, 'location', e.target.value)} placeholder="Toronto" />
              <Input label="Target Term" value={target.target_term} onChange={(e) => updateTarget(i, 'target_term', e.target.value)} placeholder="Summer 2027" />
            </div>
          </div>
        ))}
      </div>
      <button onClick={addTarget} className="mt-3 text-sm text-primary-400 hover:text-primary-300 transition-colors font-medium">+ Add Target Company</button>
    </div>
  );
}

function ReviewPanel({ profile, buckets, courses, projects, targets, onEdit }) {
  const validBuckets = buckets.filter((b) => b.bucket_name);
  const validCourses = courses.filter((c) => c.course_code);
  const validProjects = projects.filter((p) => p.name);
  const validTargets = targets.filter((t) => t.company_name);

  return (
    <div className="w-full max-w-lg text-left space-y-4 max-h-[55vh] overflow-y-auto pr-1">
      <ReviewSection title="Profile" step={0} onEdit={onEdit}>
        <ReviewRow label="Name" value={profile.full_name} />
        <ReviewRow label="University" value={profile.university} />
        <ReviewRow label="Program" value={profile.program} />
        <ReviewRow label="Years" value={profile.start_year && profile.expected_graduation_year ? `${profile.start_year} – ${profile.expected_graduation_year}` : ''} />
        <ReviewRow label="City" value={profile.city} />
        {profile.career_target && <ReviewRow label="Career Goal" value={profile.career_target} />}
      </ReviewSection>

      <ReviewSection title={`Degree (${validBuckets.length} buckets, ${validCourses.length} courses)`} step={7} onEdit={onEdit}>
        {validBuckets.length === 0 && validCourses.length === 0 ? (
          <p className="text-dark-500 text-sm">No degree data — you can add it later</p>
        ) : (
          <>
            {validBuckets.slice(0, 3).map((b, i) => (
              <ReviewRow key={i} label={b.bucket_name} value={`${b.credits_required} cr`} />
            ))}
            {validBuckets.length > 3 && <p className="text-dark-500 text-xs">+{validBuckets.length - 3} more...</p>}
          </>
        )}
      </ReviewSection>

      <ReviewSection title={`Projects (${validProjects.length})`} step={9} onEdit={onEdit}>
        {validProjects.length === 0 ? (
          <p className="text-dark-500 text-sm">None added</p>
        ) : validProjects.map((p, i) => (
          <ReviewRow key={i} label={p.name} value={`P${p.priority}`} />
        ))}
      </ReviewSection>

      <ReviewSection title={`Career Targets (${validTargets.length})`} step={10} onEdit={onEdit}>
        {validTargets.length === 0 ? (
          <p className="text-dark-500 text-sm">None added</p>
        ) : validTargets.map((t, i) => (
          <ReviewRow key={i} label={`${t.company_name} — ${t.role_type || 'TBD'}`} value={t.target_term} />
        ))}
      </ReviewSection>
    </div>
  );
}

function ReviewSection({ title, step, onEdit, children }) {
  return (
    <div className="bg-dark-800/60 border border-dark-700 rounded-xl p-4 space-y-2">
      <div className="flex justify-between items-center">
        <h3 className="text-sm font-semibold text-dark-50">{title}</h3>
        <button onClick={() => onEdit(step)} className="text-xs text-primary-400 hover:text-primary-300 transition-colors">Edit</button>
      </div>
      {children}
    </div>
  );
}

function ReviewRow({ label, value }) {
  if (!value) return null;
  return (
    <div className="flex justify-between text-sm">
      <span className="text-dark-400">{label}</span>
      <span className="text-dark-200 text-right max-w-[60%] truncate">{value}</span>
    </div>
  );
}
