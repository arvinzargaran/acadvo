import { useEffect, useState } from 'react';
import RequirementBucketCard from '../components/degree/RequirementBucketCard';
import CourseTable from '../components/degree/CourseTable';
import SemesterPlanner from '../components/degree/SemesterPlanner';
import PrerequisiteFlow from '../components/degree/PrerequisiteFlow';
import ExportPDF from '../components/degree/ExportPDF';
import FileUploadZone from '../components/degree/FileUploadZone';
import ParsedDataReview from '../components/degree/ParsedDataReview';
import CredentialsSection from '../components/degree/CredentialsSection';
import CatalogStatus from '../components/degree/CatalogStatus';
import RequirementForm from '../components/degree/RequirementForm';
import GPACalculator from '../components/dashboard/GPACalculator';
import GPATrendGoal from '../components/degree/GPATrendGoal';
import AssessmentsPanel from '../components/degree/AssessmentsPanel';
import Modal from '../components/ui/Modal';
import Skeleton from '../components/ui/Skeleton';
import PageHeader from '../components/ui/PageHeader';
import Stat from '../components/ui/Stat';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import ProgressBar from '../components/ui/ProgressBar';

const VIEWS = [
  { key: 'courses', label: 'Courses' },
  { key: 'buckets', label: 'Requirements' },
  { key: 'planner', label: 'Planner' },
  { key: 'credentials', label: 'Credentials' },
  { key: 'gpa', label: 'GPA' },
  { key: 'assessments', label: 'Assessments' },
  { key: 'flow', label: 'Flow' },
];
import { getDegreeSummary, listRequirements, listCourses, listCredentials, createRequirement, createCourse, updateCourse, deleteCourse } from '../api/degree';
import { getErrorMessage } from '../utils/errors';

export default function DegreePage() {
  const [requirements, setRequirements] = useState([]);
  const [courses, setCourses] = useState([]);
  const [credentials, setCredentials] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [view, setView] = useState('courses');
  const [importOpen, setImportOpen] = useState(false);
  const [parsedData, setParsedData] = useState(null);
  const [importSaving, setImportSaving] = useState(false);
  const [selectedCourseId, setSelectedCourseId] = useState(null);
  const [reqModalOpen, setReqModalOpen] = useState(false);

  const refreshData = async () => {
    const [reqRes, courseRes, credRes, summaryRes] = await Promise.all([
      listRequirements(),
      listCourses(),
      listCredentials(),
      getDegreeSummary().catch(() => null),
    ]);
    setRequirements(reqRes.data);
    setCourses(courseRes.data);
    setCredentials(credRes.data);
    setSummary(summaryRes?.data);
  };

  useEffect(() => {
    async function load() {
      try {
        await refreshData();
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const handleUpdate = async (courseId, data) => {
    try {
      await updateCourse(courseId, data);
      const res = await listCourses();
      setCourses(res.data);
      const summaryRes = await getDegreeSummary().catch(() => null);
      setSummary(summaryRes?.data);
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to update course.'));
    }
  };

  const handleDelete = async (courseId) => {
    try {
      await deleteCourse(courseId);
      setCourses(prev => prev.filter(c => c.id !== courseId));
      const summaryRes = await getDegreeSummary().catch(() => null);
      setSummary(summaryRes?.data);
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to delete course.'));
    }
  };

  const handleCreate = async (data) => {
    try {
      await createCourse(data);
      const [courseRes, summaryRes] = await Promise.all([
        listCourses(),
        getDegreeSummary().catch(() => null),
      ]);
      setCourses(courseRes.data);
      setSummary(summaryRes?.data);
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to create course.'));
    }
  };

  const handleCreateRequirement = async (data) => {
    try {
      await createRequirement(data);
      const [reqRes, summaryRes] = await Promise.all([
        listRequirements(),
        getDegreeSummary().catch(() => null),
      ]);
      setRequirements(reqRes.data);
      setSummary(summaryRes?.data);
      setReqModalOpen(false);
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to create requirement.'));
    }
  };

  const handleImportConfirm = async ({ requirements: reqs, courses: crs }) => {
    setImportSaving(true);
    try {
      const bucketMap = {};
      for (const req of reqs) {
        const { data } = await createRequirement({
          bucket_name: req.bucket_name,
          credits_required: req.credits_required,
          description: req.description || null,
        });
        bucketMap[req.bucket_name] = data.id;
      }
      for (const course of crs) {
        await createCourse({
          course_code: course.course_code,
          course_name: course.course_name,
          credit_value: course.credit_value,
          requirement_bucket_id: bucketMap[course.requirement_bucket] || null,
          term: course.term || null,
          status: course.status || 'planned',
          grade: course.grade || null,
        });
      }
      // Refresh data
      const [reqRes, courseRes, summaryRes] = await Promise.all([
        listRequirements(),
        listCourses(),
        getDegreeSummary().catch(() => null),
      ]);
      setRequirements(reqRes.data);
      setCourses(courseRes.data);
      setSummary(summaryRes?.data);
      setParsedData(null);
      setImportOpen(false);
    } finally {
      setImportSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-9 w-64" />
        </div>
        {/* Summary bar placeholder */}
        <Skeleton className="h-20 w-full rounded-xl" />
        {/* Toolbar placeholder */}
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div className="flex items-center gap-2 flex-wrap">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-6 w-20" />
            ))}
          </div>
          <Skeleton className="h-8 w-48" />
        </div>
        {/* Table / list placeholder */}
        <div className="bg-dark-800 border border-dark-700 rounded-xl p-4 space-y-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 text-sm px-4 py-3 rounded-lg flex items-center justify-between">
          {error}
          <button onClick={() => setError('')} className="ml-3 hover:text-red-300">✕</button>
        </div>
      )}
      <PageHeader
        eyebrow="Your degree"
        title="Degree Plan"
        subtitle="Requirements, courses, GPA, and the path to your credential — in one place."
        actions={
          <>
            <ExportPDF courses={courses} requirements={requirements} summary={summary} />
            <Button variant="accent" onClick={() => setImportOpen(true)}>
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
              </svg>
              Import Document
            </Button>
          </>
        }
      />

      {/* View switcher */}
      <div className="flex flex-wrap items-center gap-1 rounded-xl bg-dark-800 ring-1 ring-black/5 dark:ring-white/10 p-1">
        {VIEWS.map(v => (
          <button
            key={v.key}
            onClick={() => setView(v.key)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition ${
              view === v.key ? 'bg-primary-600 text-white shadow-sm' : 'text-dark-400 hover:text-dark-50'
            }`}
          >
            {v.label}
          </button>
        ))}
        {/* Chat widget available in bottom-right corner */}
      </div>

      <CatalogStatus />

      {summary && (
        <Card className="flex flex-col gap-5 sm:flex-row sm:items-center sm:gap-10">
          <Stat
            label="Overall progress"
            value={`${summary.overall_percentage}%`}
            className="shrink-0"
          />
          <div className="flex-1">
            <ProgressBar value={summary.overall_percentage} />
          </div>
          <Stat
            label="Credits"
            value={summary.total_credits_completed}
            unit={`/ ${summary.total_credits_required}`}
            className="shrink-0"
          />
        </Card>
      )}

      {view === 'courses' ? (
        <CourseTable
          courses={courses}
          requirements={requirements}
          credentials={credentials}
          onUpdate={handleUpdate}
          onDelete={handleDelete}
          onCreate={handleCreate}
        />
      ) : view === 'buckets' ? (
        <div className="space-y-4">
          {requirements.length > 0 && (
            <div className="flex justify-end">
              <Button variant="secondary" onClick={() => setReqModalOpen(true)}>
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                Add requirement
              </Button>
            </div>
          )}
          {requirements.map(req => (
            <RequirementBucketCard key={req.id} requirement={req} courses={courses} />
          ))}
          {requirements.length === 0 && (
            <Card className="text-center py-14">
              <p className="font-display text-2xl text-dark-50">No requirements yet</p>
              <p className="text-dark-400 text-sm mt-2 max-w-md mx-auto">
                Map out your degree's requirement buckets to watch progress build toward each one — or ask the chat widget to set them up for you.
              </p>
              <div className="mt-6">
                <Button variant="accent" onClick={() => setReqModalOpen(true)}>Add your first requirement</Button>
              </div>
            </Card>
          )}
        </div>
      ) : view === 'credentials' ? (
        <CredentialsSection credentials={credentials} courses={courses} onRefresh={refreshData} />
      ) : view === 'gpa' ? (
        <div className="space-y-6">
          <GPACalculator />
          <GPATrendGoal />
        </div>
      ) : view === 'assessments' ? (
        <div className="space-y-4">
          {/* Course selector */}
          <Card>
            <p className="eyebrow mb-3">Select a course to view or upload assessments</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
              {courses.map(c => (
                <button
                  key={c.id}
                  onClick={() => setSelectedCourseId(selectedCourseId === c.id ? null : c.id)}
                  className={`text-left px-3 py-2 rounded-lg border text-sm transition-all ${
                    selectedCourseId === c.id
                      ? 'border-primary-500 bg-primary-500/10 text-dark-50'
                      : 'border-dark-600 hover:border-dark-500 text-dark-300 hover:text-dark-50'
                  }`}
                >
                  <span className="font-medium">{c.course_code}</span>
                  <span className="text-dark-400 ml-1.5 text-xs">{c.course_name}</span>
                </button>
              ))}
            </div>
            {courses.length === 0 && (
              <div className="text-center py-8">
                <p className="font-display text-xl text-dark-50">Nothing to grade yet</p>
                <p className="text-dark-400 text-sm mt-1.5">Add courses to start tracking assessments and weighted grades.</p>
              </div>
            )}
          </Card>

          {/* Assessments panel for selected course */}
          {selectedCourseId && (
            <Card>
              <AssessmentsPanel course={courses.find(c => c.id === selectedCourseId)} />
            </Card>
          )}
        </div>
      ) : view === 'planner' ? (
        <SemesterPlanner courses={courses} onRefresh={refreshData} />
      ) : (
        <PrerequisiteFlow courses={courses} />
      )}

      {/* Add Requirement Modal */}
      <Modal isOpen={reqModalOpen} onClose={() => setReqModalOpen(false)} title="Add requirement">
        {reqModalOpen && (
          <RequirementForm
            onSave={handleCreateRequirement}
            onCancel={() => setReqModalOpen(false)}
          />
        )}
      </Modal>

      {/* Import Document Modal */}
      {/* Was a hand-rolled overlay with a click-to-close backdrop, no focus trap
          and no Escape. Modal supplies all three; widthClass keeps the wide
          layout this one needs for the parsed-data review table. */}
      {importOpen && (
        <Modal
          isOpen
          onClose={() => { setImportOpen(false); setParsedData(null); }}
          title="Import Degree Document"
          widthClass="max-w-4xl"
        >
          <div>
            {parsedData ? (
              <ParsedDataReview
                data={parsedData}
                onConfirm={handleImportConfirm}
                onCancel={() => setParsedData(null)}
              />
            ) : (
              <FileUploadZone onParsed={setParsedData} />
            )}
            {importSaving && (
              <div className="absolute inset-0 bg-dark-800/80 flex items-center justify-center rounded-xl">
                <div className="flex flex-col items-center gap-3">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500" />
                  <p className="text-dark-300 text-sm">Saving imported data...</p>
                </div>
              </div>
            )}
          </div>
        </Modal>
      )}
    </div>
  );
}
