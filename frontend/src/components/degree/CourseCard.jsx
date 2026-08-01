import Badge from '../ui/Badge';

const statusColors = {
  completed: 'green',
  in_progress: 'yellow',
  planned: 'blue',
  not_scheduled: 'gray',
};

// Stacked card representation of a course for small screens, where the wide
// multi-column table becomes cramped.
export default function CourseCard({ course, bucketName, credentialName, onEdit, onDelete }) {
  return (
    <div className="bg-dark-800 border border-dark-700 rounded-xl p-4 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-display text-base text-dark-50">{course.course_code}</p>
          <p className="text-dark-300 text-sm truncate">{course.course_name}</p>
        </div>
        <Badge color={statusColors[course.status]} variant="label" dot>{course.status.replace('_', ' ')}</Badge>
      </div>

      <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
        <div>
          <p className="text-dark-500 text-xs">Credits</p>
          <p className="text-dark-300">{course.credit_value}</p>
        </div>
        <div>
          <p className="text-dark-500 text-xs">Semester</p>
          <p className="text-dark-300">{course.term || '--'}</p>
        </div>
        <div>
          <p className="text-dark-500 text-xs">Grade</p>
          <p className="text-dark-300">{course.grade || '--'}</p>
        </div>
        <div>
          <p className="text-dark-500 text-xs">Requirement</p>
          <p className="text-dark-300 truncate">{bucketName || '--'}</p>
        </div>
        {credentialName && (
          <div className="col-span-2">
            <p className="text-dark-500 text-xs">Credential</p>
            <p className="text-dark-300 truncate">{credentialName}</p>
          </div>
        )}
      </div>

      <div className="flex items-center justify-end gap-4 border-t border-dark-700/50 pt-3">
        <button onClick={onEdit} className="text-primary-400 hover:text-primary-300 text-sm font-medium">
          Edit
        </button>
        <button onClick={onDelete} className="text-red-400 hover:text-red-300 text-sm font-medium">
          Delete
        </button>
      </div>
    </div>
  );
}
