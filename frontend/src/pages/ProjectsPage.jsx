import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import ProjectCard from '../components/projects/ProjectCard';
import Button from '../components/ui/Button';
import Modal from '../components/ui/Modal';
import Input from '../components/ui/Input';
import PageHeader from '../components/ui/PageHeader';
import Stat from '../components/ui/Stat';
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

  const deployedCount = projects.filter(p => p.status === 'deployed' || p.status === 'interview_ready').length;
  const inProgressCount = projects.filter(p => p.status === 'in_progress').length;
  const isEmpty = projects.length === 0;

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="PROJECTS"
        title="Projects"
        subtitle="Build the portfolio that proves what you can ship."
        actions={<Button variant="accent" onClick={openCreate}>New project</Button>}
      />
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 text-sm px-4 py-3 rounded-lg flex items-center justify-between">
          {error}
          <button onClick={() => setError('')} className="ml-3 hover:text-red-300">✕</button>
        </div>
      )}

      {!isEmpty && (
        <div className="grid grid-cols-3 gap-4 max-w-md">
          <Stat value={projects.length} label="Projects" />
          <Stat value={inProgressCount} label="In Progress" />
          <Stat value={deployedCount} label="Shipped" />
        </div>
      )}

      {isEmpty ? (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <span className="icon-chip w-16 h-16 rounded-2xl flex items-center justify-center text-primary-500 mb-5">
            <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" />
            </svg>
          </span>
          <h2 className="font-display text-2xl tracking-tight text-dark-50">Nothing shipped yet</h2>
          <p className="text-dark-400 text-sm mt-2 max-w-sm">
            Every strong portfolio starts with one project. Frame the problem, set milestones, and start building.
          </p>
          <Button variant="accent" onClick={openCreate} className="mt-6">Create your first project</Button>
        </div>
      ) : (
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
          className="flex flex-col items-center justify-center gap-3 min-h-[240px] border-2 border-dashed border-dark-600 rounded-2xl bg-dark-800/40 transition-colors duration-300 hover:bg-dark-800 cursor-pointer group"
        >
          <div className="w-12 h-12 rounded-full border-2 border-dark-500 flex items-center justify-center group-hover:border-primary-500/50 group-hover:bg-primary-500/5 transition-all">
            <svg className="w-6 h-6 text-dark-400 group-hover:text-primary-500 transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 4.5v15m7.5-7.5h-15" />
            </svg>
          </div>
          <span className="text-dark-400 text-sm font-medium group-hover:text-dark-200 transition-colors">Add New Project</span>
        </motion.button>
      </div>
      )}

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
                className="w-full bg-dark-800 border border-dark-600 text-dark-50 rounded-lg px-3 py-2"
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
              className="w-full bg-dark-800 border border-dark-600 text-dark-50 rounded-lg px-3 py-2 h-20 resize-none"
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
