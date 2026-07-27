import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import ProjectCard from '../components/projects/ProjectCard';
import Button from '../components/ui/Button';
import Modal from '../components/ui/Modal';
import Input from '../components/ui/Input';
import { listProjects, createProject, updateProject, deleteProject, updateMilestone } from '../api/projects';
import { getErrorMessage } from '../utils/errors';

const EMPTY_FORM = { name: '', description: '', priority: 1, tech_stack: '', hard_deadline: '', product_framing: '' };

export default function ProjectsPage() {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingProject, setEditingProject] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [error, setError] = useState('');
  const [formError, setFormError] = useState('');

  const loadProjects = async () => {
    try {
      const res = await listProjects();
      setProjects(res.data);
    } catch {
      setError('Failed to load projects.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadProjects(); }, []);

  const openCreate = () => {
    setEditingProject(null);
    setForm(EMPTY_FORM);
    setFormError('');
    setShowModal(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setFormError('');
    const data = { ...form, priority: parseInt(form.priority) };
    if (!data.hard_deadline) delete data.hard_deadline;
    if (!data.product_framing) delete data.product_framing;

    try {
      if (editingProject) {
        await updateProject(editingProject.id, data);
      } else {
        await createProject(data);
      }
      setShowModal(false);
      setEditingProject(null);
      setForm(EMPTY_FORM);
      loadProjects();
    } catch (err) {
      setFormError(getErrorMessage(err, 'Failed to save project.'));
    }
  };

  const handleEdit = (project) => {
    setEditingProject(project);
    setForm({
      name: project.name,
      description: project.description || '',
      priority: project.priority,
      tech_stack: project.tech_stack || '',
      hard_deadline: project.hard_deadline || '',
      product_framing: project.product_framing || '',
    });
    setFormError('');
    setShowModal(true);
  };

  const handleDelete = async (id) => {
    try {
      await deleteProject(id);
      loadProjects();
    } catch {
      setError('Failed to delete project.');
    }
  };

  const handleMilestoneUpdate = async (milestoneId, data) => {
    try {
      await updateMilestone(milestoneId, data);
      loadProjects();
    } catch {
      setError('Failed to update milestone.');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Projects</h1>
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 text-sm px-4 py-3 rounded-lg flex items-center justify-between">
          {error}
          <button onClick={() => setError('')} className="ml-3 hover:text-red-300">✕</button>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
        {projects.map((p, i) => (
          <ProjectCard
            key={p.id}
            project={p}
            index={i}
            onUpdateMilestone={handleMilestoneUpdate}
            onEdit={handleEdit}
            onDelete={handleDelete}
          />
        ))}

        {/* Add New Project card */}
        <motion.button
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45, delay: projects.length * 0.08, ease: [0.25, 0.46, 0.45, 0.94] }}
          onClick={openCreate}
          className="flex flex-col items-center justify-center gap-3 min-h-[240px] border-2 border-dashed border-white/20 rounded-2xl bg-white/[0.02] transition-colors duration-300 hover:bg-white/5 cursor-pointer group"
        >
          <div className="w-12 h-12 rounded-full border-2 border-white/15 flex items-center justify-center group-hover:border-white/40 group-hover:bg-white/5 transition-all">
            <svg className="w-6 h-6 text-white/30 group-hover:text-white/60 transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 4.5v15m7.5-7.5h-15" />
            </svg>
          </div>
          <span className="text-white/30 text-sm font-medium group-hover:text-white/60 transition-colors">Add New Project</span>
        </motion.button>
      </div>

      <Modal isOpen={showModal} onClose={() => setShowModal(false)} title={editingProject ? 'Edit Project' : 'New Project'}>
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input label="Project Name" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} required />
          <Input label="Description" value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} />
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-dark-300 mb-1">Priority</label>
              <select
                value={form.priority}
                onChange={e => setForm(f => ({ ...f, priority: e.target.value }))}
                className="w-full bg-dark-800 border border-dark-600 text-white rounded-lg px-3 py-2"
              >
                <option value={1}>1 — High</option>
                <option value={2}>2 — Medium</option>
                <option value={3}>3 — Low</option>
              </select>
            </div>
            <Input label="Hard Deadline" type="date" value={form.hard_deadline} onChange={e => setForm(f => ({ ...f, hard_deadline: e.target.value }))} />
          </div>
          <Input label="Tech Stack (comma-separated)" value={form.tech_stack} onChange={e => setForm(f => ({ ...f, tech_stack: e.target.value }))} />
          <div>
            <label className="block text-sm text-dark-300 mb-1">Product Framing</label>
            <textarea
              value={form.product_framing}
              onChange={e => setForm(f => ({ ...f, product_framing: e.target.value }))}
              className="w-full bg-dark-800 border border-dark-600 text-white rounded-lg px-3 py-2 h-20 resize-none"
              placeholder="What problem does it solve? Who is the user?"
            />
          </div>
          {formError && <p className="text-red-400 text-sm">{formError}</p>}
          <div className="flex justify-end gap-3">
            <Button variant="secondary" type="button" onClick={() => setShowModal(false)}>Cancel</Button>
            <Button variant="primary" type="submit">{editingProject ? 'Save' : 'Create'}</Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
