import { motion } from 'framer-motion';
import MilestoneList from './MilestoneList';
import Badge from '../ui/Badge';
import { safeExternalUrl } from '../../utils/urls';

const STATUS_CONFIG = {
  not_started: { label: 'Not Started', color: 'gray' },
  in_progress: { label: 'In Progress', color: 'yellow' },
  deployed: { label: 'Deployed', color: 'green' },
  interview_ready: { label: 'Interview Ready', color: 'green' },
};

const PRIORITY_CONFIG = {
  1: { label: 'P1', color: 'red' },
  2: { label: 'P2', color: 'yellow' },
  3: { label: 'P3', color: 'gray' },
};

export default function ProjectCard({ project, index = 0, onUpdateMilestone, onEdit, onDelete }) {
  const status = STATUS_CONFIG[project.status] || STATUS_CONFIG.not_started;
  const priority = PRIORITY_CONFIG[project.priority] || PRIORITY_CONFIG[3];

  const daysLeft = project.hard_deadline
    ? Math.ceil((new Date(project.hard_deadline) - new Date()) / (1000 * 60 * 60 * 24))
    : null;

  const techItems = project.tech_stack
    ? project.tech_stack.split(',').map(t => t.trim()).filter(Boolean)
    : [];

  // Whether the card body has any content between the header and footer. When it
  // doesn't, the equal-height grid would otherwise leave a large empty gap.
  const hasBody = Boolean(
    project.description ||
    project.product_framing ||
    (project.milestones && project.milestones.length > 0) ||
    techItems.length > 0
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, delay: index * 0.08, ease: [0.25, 0.46, 0.45, 0.94] }}
      className="card-rich shadow-editorial ring-1 ring-black/5 dark:ring-white/10 rounded-2xl p-6 relative overflow-hidden flex flex-col"
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <h3 className="font-display text-xl tracking-tight leading-snug text-dark-50">{project.name}</h3>
        <div className="flex items-center gap-1.5 flex-shrink-0">
          <Badge color={priority.color} variant="label">{priority.label}</Badge>
          <Badge color={status.color} variant="label" dot>{status.label}</Badge>
        </div>
      </div>

      {/* Description */}
      {project.description && (
        <p className="text-dark-300 text-sm leading-relaxed line-clamp-3 mb-4">{project.description}</p>
      )}

      {/* Product Framing */}
      {project.product_framing && (
        <div className="bg-dark-700/50 rounded-lg p-3 mb-4">
          <p className="eyebrow text-[10px] mb-1">Product Framing</p>
          <p className="text-dark-400 text-xs leading-relaxed line-clamp-2">{project.product_framing}</p>
        </div>
      )}

      {/* Milestones */}
      {project.milestones && project.milestones.length > 0 && (
        <div className="mb-4">
          <MilestoneList milestones={project.milestones} onUpdate={onUpdateMilestone} />
        </div>
      )}

      {/* Tech Stack Pills */}
      {techItems.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-4 mt-auto">
          {techItems.map((tech, i) => (
            <Badge key={i} color="gray" variant="label">{tech}</Badge>
          ))}
        </div>
      )}

      {/* Empty-body hint — keeps sparse cards from showing a blank gap */}
      {!hasBody && (
        <p className="text-dark-400 text-sm italic mb-4">
          No details yet — edit to add a description, milestones, or tech stack.
        </p>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between pt-3 border-t border-dark-600 mt-auto">
        <div className="flex items-center gap-3 text-xs">
          {project.hard_deadline && (
            <span className={`flex items-center gap-1 ${daysLeft <= 7 ? 'text-red-400' : daysLeft <= 30 ? 'text-yellow-400' : 'text-dark-400'}`}>
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5" />
              </svg>
              {project.hard_deadline}{daysLeft !== null && ` (${daysLeft}d)`}
            </span>
          )}
          {safeExternalUrl(project.repo_url) && (
            <a href={safeExternalUrl(project.repo_url)} target="_blank" rel="noopener noreferrer" className="text-dark-400 hover:text-dark-50 transition-colors">
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M12 .3a12 12 0 00-3.8 23.38c.6.11.82-.26.82-.58v-2.02c-3.34.73-4.04-1.61-4.04-1.61a3.18 3.18 0 00-1.33-1.76c-1.09-.74.08-.73.08-.73a2.52 2.52 0 011.84 1.24 2.56 2.56 0 003.5 1 2.56 2.56 0 01.76-1.6c-2.67-.3-5.47-1.33-5.47-5.93a4.64 4.64 0 011.24-3.22 4.3 4.3 0 01.12-3.18s1-.33 3.3 1.23a11.38 11.38 0 016 0c2.28-1.56 3.29-1.23 3.29-1.23a4.3 4.3 0 01.12 3.18 4.64 4.64 0 011.23 3.22c0 4.61-2.81 5.63-5.48 5.92a2.87 2.87 0 01.82 2.23v3.29c0 .32.21.7.82.58A12 12 0 0012 .3z"/></svg>
            </a>
          )}
          {safeExternalUrl(project.live_url) && (
            <a href={safeExternalUrl(project.live_url)} target="_blank" rel="noopener noreferrer" className="text-dark-400 hover:text-dark-50 transition-colors">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
              </svg>
            </a>
          )}
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => onEdit(project)}
            aria-label={`Edit ${project.name}`}
            className="p-1.5 rounded-lg text-dark-400 hover:text-dark-50 hover:bg-dark-700 transition-all"
            title="Edit"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10" />
            </svg>
          </button>
          <button
            onClick={() => onDelete(project.id)}
            aria-label={`Delete ${project.name}`}
            className="p-1.5 rounded-lg text-dark-400 hover:text-red-400 hover:bg-red-500/10 transition-all"
            title="Delete"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
            </svg>
          </button>
        </div>
      </div>
    </motion.div>
  );
}
