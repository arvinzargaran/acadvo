import { useState, useEffect } from 'react';
import Badge from '../ui/Badge';
import Modal from '../ui/Modal';
import CourseEditRow from './CourseEditRow';
import CourseCard from './CourseCard';
import CourseForm from './CourseForm';

const statusColors = {
  completed: 'green',
  in_progress: 'yellow',
  planned: 'blue',
  not_scheduled: 'gray',
};

const EMPTY_COURSE = {
  course_code: '',
  course_name: '',
  credit_value: 0.5,
  status: 'planned',
  grade: '',
  term: '',
  requirement_bucket_id: '',
  credential_id: '',
};

// Below md we render stacked cards + a modal form; at md+ we keep the inline table.
function useIsMobile() {
  const query = '(max-width: 767px)';
  const [isMobile, setIsMobile] = useState(
    () => typeof window !== 'undefined' && window.matchMedia(query).matches
  );
  useEffect(() => {
    const mq = window.matchMedia(query);
    const handler = (e) => setIsMobile(e.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);
  return isMobile;
}

export default function CourseTable({ courses, requirements, credentials = [], onUpdate, onDelete, onCreate }) {
  const isMobile = useIsMobile();
  const [editingId, setEditingId] = useState(null);
  const [adding, setAdding] = useState(false);
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');
  // Modal-driven form for small screens: { mode: 'add' } or { mode: 'edit', course }
  const [modalForm, setModalForm] = useState(null);

  const bucketMap = {};
  requirements.forEach(r => { bucketMap[r.id] = r.bucket_name; });
  const credMap = {};
  credentials.forEach(c => { credMap[c.id] = c.name; });

  // Filter courses
  let filtered = courses;
  if (filter !== 'all') {
    filtered = filtered.filter(c => c.status === filter);
  }
  if (search) {
    const q = search.toLowerCase();
    filtered = filtered.filter(c =>
      c.course_code.toLowerCase().includes(q) ||
      c.course_name.toLowerCase().includes(q) ||
      (c.term || '').toLowerCase().includes(q)
    );
  }

  // Sort: by term then course code
  const sorted = [...filtered].sort((a, b) => {
    const termA = a.term || 'zzz';
    const termB = b.term || 'zzz';
    if (termA !== termB) return termA.localeCompare(termB);
    return a.course_code.localeCompare(b.course_code);
  });

  const statusCounts = {
    all: courses.length,
    completed: courses.filter(c => c.status === 'completed').length,
    in_progress: courses.filter(c => c.status === 'in_progress').length,
    planned: courses.filter(c => c.status === 'planned').length,
    not_scheduled: courses.filter(c => c.status === 'not_scheduled').length,
  };

  const handleAddSave = async (form) => {
    await onCreate(form);
    setAdding(false);
  };

  const handleAddClick = () => {
    if (isMobile) {
      setModalForm({ mode: 'add' });
    } else {
      setAdding(true);
      setEditingId(null);
    }
  };

  const handleModalSave = async (form) => {
    if (modalForm?.mode === 'edit') {
      await onUpdate(modalForm.course.id, form);
    } else {
      await onCreate(form);
    }
    setModalForm(null);
  };

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-2 flex-wrap">
          {[
            { key: 'all', label: 'All' },
            { key: 'completed', label: 'Completed' },
            { key: 'in_progress', label: 'In Progress' },
            { key: 'planned', label: 'Planned' },
            { key: 'not_scheduled', label: 'Unscheduled' },
          ].map(f => (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              className={`px-3 py-1 rounded-lg text-xs font-medium transition ${
                filter === f.key
                  ? 'bg-primary-600 text-white'
                  : 'bg-dark-800 text-dark-400 hover:text-dark-50 border border-dark-700'
              }`}
            >
              {f.label} ({statusCounts[f.key]})
            </button>
          ))}
        </div>
        <div className="flex items-center gap-3">
          <input
            type="text"
            placeholder="Search courses..."
            aria-label="Search your courses"
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="bg-dark-800 border border-dark-700 rounded-lg px-3 py-1.5 text-sm text-dark-50 placeholder-dark-500 w-48 focus:outline-none focus:border-primary-500"
          />
          <button
            onClick={handleAddClick}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-primary-600 hover:bg-primary-500 text-white text-sm font-medium rounded-lg transition whitespace-nowrap"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Add Course
          </button>
        </div>
      </div>

      {/* Mobile: stacked cards */}
      <div className="md:hidden space-y-3">
        {sorted.map(course => (
          <CourseCard
            key={course.id}
            course={course}
            bucketName={course.requirement_bucket_id ? bucketMap[course.requirement_bucket_id] : null}
            credentialName={course.credential_id ? credMap[course.credential_id] : null}
            onEdit={() => setModalForm({ mode: 'edit', course })}
            onDelete={() => onDelete(course.id)}
          />
        ))}
        {sorted.length === 0 && (
          <div className="bg-dark-800 border border-dark-700 rounded-xl px-4 py-8 text-center text-dark-500 text-sm">
            {search || filter !== 'all' ? 'No courses match your filters.' : 'No courses added yet.'}
          </div>
        )}
      </div>

      {/* Desktop: table with inline editing */}
      <div className="hidden md:block bg-dark-800 border border-dark-700 rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-dark-700">
                <th className="text-left text-dark-400 text-xs font-medium px-3 py-2.5">Code</th>
                <th className="text-left text-dark-400 text-xs font-medium px-3 py-2.5">Name</th>
                <th className="text-left text-dark-400 text-xs font-medium px-3 py-2.5">Credits</th>
                <th className="text-left text-dark-400 text-xs font-medium px-3 py-2.5">Semester</th>
                <th className="text-left text-dark-400 text-xs font-medium px-3 py-2.5">Status</th>
                <th className="text-left text-dark-400 text-xs font-medium px-3 py-2.5">Grade</th>
                <th className="text-left text-dark-400 text-xs font-medium px-3 py-2.5">Requirement</th>
                <th className="text-left text-dark-400 text-xs font-medium px-3 py-2.5">Credential</th>
                <th className="text-right text-dark-400 text-xs font-medium px-3 py-2.5">Actions</th>
              </tr>
            </thead>
            <tbody>
              {adding && (
                <CourseEditRow
                  course={EMPTY_COURSE}
                  requirements={requirements}
                  credentials={credentials}
                  onSave={handleAddSave}
                  onCancel={() => setAdding(false)}
                />
              )}
              {sorted.map(course =>
                editingId === course.id ? (
                  <CourseEditRow
                    key={course.id}
                    course={course}
                    requirements={requirements}
                    credentials={credentials}
                    onSave={(data) => { onUpdate(course.id, data); setEditingId(null); }}
                    onCancel={() => setEditingId(null)}
                  />
                ) : (
                  <tr key={course.id} className="border-b border-dark-700/50 last:border-0 hover:bg-dark-700/20 transition-colors">
                    <td className="px-3 py-2.5 text-dark-50 text-sm font-medium">{course.course_code}</td>
                    <td className="px-3 py-2.5 text-dark-300 text-sm">{course.course_name}</td>
                    <td className="px-3 py-2.5 text-dark-300 text-sm">{course.credit_value}</td>
                    <td className="px-3 py-2.5 text-dark-300 text-sm">{course.term || <span className="text-dark-500">--</span>}</td>
                    <td className="px-3 py-2.5">
                      <Badge color={statusColors[course.status]} variant="label" dot>{course.status.replace('_', ' ')}</Badge>
                    </td>
                    <td className="px-3 py-2.5 text-dark-300 text-sm">{course.grade || <span className="text-dark-500">--</span>}</td>
                    <td className="px-3 py-2.5 text-dark-400 text-xs">
                      {course.requirement_bucket_id ? (bucketMap[course.requirement_bucket_id] || '--') : <span className="text-dark-500">--</span>}
                    </td>
                    <td className="px-3 py-2.5 text-dark-400 text-xs">
                      {course.credential_id ? (credMap[course.credential_id] || '--') : <span className="text-dark-500">--</span>}
                    </td>
                    <td className="px-3 py-2.5 text-right whitespace-nowrap">
                      <button
                        onClick={() => { setEditingId(course.id); setAdding(false); }}
                        className="text-primary-400 hover:text-primary-300 text-sm mr-2"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => onDelete(course.id)}
                        className="text-red-400 hover:text-red-300 text-sm"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                )
              )}
              {sorted.length === 0 && !adding && (
                <tr>
                  <td colSpan={9} className="px-4 py-8 text-center text-dark-500 text-sm">
                    {search || filter !== 'all' ? 'No courses match your filters.' : 'No courses added yet.'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <p className="text-dark-500 text-xs">
        Showing {sorted.length} of {courses.length} courses
      </p>

      {/* Mobile add/edit modal */}
      <Modal
        isOpen={!!modalForm}
        onClose={() => setModalForm(null)}
        title={modalForm?.mode === 'edit' ? 'Edit course' : 'Add course'}
      >
        {modalForm && (
          <CourseForm
            course={modalForm.mode === 'edit' ? modalForm.course : EMPTY_COURSE}
            requirements={requirements}
            credentials={credentials}
            onSave={handleModalSave}
            onCancel={() => setModalForm(null)}
            submitLabel={modalForm.mode === 'edit' ? 'Save changes' : 'Add course'}
          />
        )}
      </Modal>
    </div>
  );
}
