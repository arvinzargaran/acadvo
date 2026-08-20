import { useEffect, useState } from 'react';
import TargetCard from '../components/career/TargetCard';
import CareerTimeline from '../components/career/CareerTimeline';
import ApplicationPipeline from '../components/career/ApplicationPipeline';
import ResumeReview from '../components/career/ResumeReview';
import CareerAIChat from '../components/career/CareerAIChat';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import Modal from '../components/ui/Modal';
import Input from '../components/ui/Input';
import Skeleton from '../components/ui/Skeleton';
import PageHeader from '../components/ui/PageHeader';
import Stat from '../components/ui/Stat';
import { getErrorMessage } from '../utils/errors';
import { listCareerTargets, createCareerTarget, updateCareerTarget, deleteCareerTarget, listTimelineEvents } from '../api/career';

const RECOMMENDED_TARGETS = [
  { company_name: 'Shopify', role_type: 'SWE Intern', location: 'Remote / Ottawa' },
  { company_name: 'Amazon', role_type: 'SWE Intern', location: 'Remote' },
  { company_name: 'Google', role_type: 'SWE Intern', location: 'Remote' },
  { company_name: 'Microsoft', role_type: 'SWE Intern', location: 'Remote' },
  { company_name: 'Wealthsimple', role_type: 'SWE Intern', location: 'Remote / Toronto' },
  { company_name: 'RBC (Tech)', role_type: 'SWE Intern', location: 'Remote / Toronto' },
];

export default function CareerPage() {
  const [targets, setTargets] = useState([]);
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ company_name: '', role_type: '', location: '', target_term: '', status: 'researching', notes: '' });
  const [view, setView] = useState('pipeline');
  const [aiChatOpen, setAiChatOpen] = useState(false);
  const [addingRec, setAddingRec] = useState(null);
  const [error, setError] = useState('');
  const [formError, setFormError] = useState('');

  const load = async () => {
    try {
      const [targetsRes, eventsRes] = await Promise.all([
        listCareerTargets(),
        listTimelineEvents(),
      ]);
      setTargets(targetsRes.data);
      setEvents(eventsRes.data);
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to load career data.'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setFormError('');
    try {
      if (editing) {
        await updateCareerTarget(editing.id, form);
      } else {
        await createCareerTarget(form);
      }
      setShowModal(false);
      setEditing(null);
      setForm({ company_name: '', role_type: '', location: '', target_term: '', status: 'researching', notes: '' });
      load();
    } catch (err) {
      setFormError(getErrorMessage(err, 'Failed to save target.'));
    }
  };

  const handleEdit = (target) => {
    setEditing(target);
    setForm({
      company_name: target.company_name,
      role_type: target.role_type || '',
      location: target.location || '',
      target_term: target.target_term || '',
      status: target.status,
      notes: target.notes || '',
    });
    setFormError('');
    setShowModal(true);
  };

  const handleDelete = async (id) => {
    try {
      await deleteCareerTarget(id);
      load();
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to delete target.'));
    }
  };

  const handleStatusChange = async (id, newStatus) => {
    try {
      await updateCareerTarget(id, { status: newStatus });
      load();
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to update status.'));
    }
  };

  const [pendingAdds, setPendingAdds] = useState(new Set());

  const handleAddRecommended = async (rec) => {
    if (pendingAdds.has(rec.company_name) || addedCompanies.has(rec.company_name)) return;
    setPendingAdds(prev => new Set(prev).add(rec.company_name));
    setAddingRec(rec.company_name);
    try {
      await createCareerTarget({ company_name: rec.company_name, role_type: rec.role_type, location: rec.location, status: 'researching' });
      await load();
    } finally {
      setAddingRec(null);
    }
  };

  const addedCompanies = new Set(targets.map(t => t.company_name));

  // Full-screen AI chat
  if (aiChatOpen) {
    return (
      <CareerAIChat
        targets={targets}
        events={events}
        onClose={() => { setAiChatOpen(false); load(); }}
        onDataChanged={load}
      />
    );
  }

  if (loading) {
    return (
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <Skeleton className="h-8 w-32" />
          <div className="hidden sm:flex items-center gap-3">
            <Skeleton className="h-9 w-40" />
            <Skeleton className="h-9 w-28" />
            <Skeleton className="h-9 w-24" />
          </div>
        </div>

        {/* Recommended employers row */}
        <div className="space-y-2">
          <Skeleton className="h-3 w-56" />
          <div className="flex gap-2.5 overflow-hidden">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-14 w-40 flex-shrink-0" />
            ))}
          </div>
        </div>

        {/* Pipeline columns */}
        <div className="flex md:grid md:grid-cols-3 lg:grid-cols-5 gap-3 overflow-hidden">
          {Array.from({ length: 5 }).map((_, i) => (
            <div
              key={i}
              className="bg-dark-800 rounded-xl border-t-2 border-dark-600 min-h-[200px] w-[80%] sm:w-[46%] shrink-0 md:w-auto md:shrink p-3 space-y-2"
            >
              <Skeleton className="h-3 w-24 mb-3" />
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
            </div>
          ))}
        </div>

        {/* Resume review card */}
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  const isEmpty = targets.length === 0 && events.length === 0;

  // Empty state — AI-driven prompt
  if (isEmpty) {
    return (
      <div className="space-y-8">
        <PageHeader eyebrow="CAREER" title="Career" />

        <div className="flex flex-col items-center justify-center py-12">
          <Card className="max-w-lg text-center" gradient>
            <div className="space-y-5">
              <div className="icon-chip mx-auto w-16 h-16 rounded-2xl flex items-center justify-center text-primary-500">
                <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
              </div>
              <div>
                <h2 className="font-display text-2xl tracking-tight text-dark-50">Let your advisor chart the path</h2>
                <p className="text-dark-400 text-sm mt-2 leading-relaxed">
                  Based on your profile, degree progress, and projects, your AI advisor suggests target companies, roles, and a timeline to get there.
                </p>
              </div>
              <Button variant="accent" onClick={() => setAiChatOpen(true)}>
                Build my career plan
              </Button>
              <p className="text-dark-500 text-xs">
                or{' '}
                <button
                  onClick={() => { setEditing(null); setForm({ company_name: '', role_type: '', location: '', target_term: '', status: 'researching', notes: '' }); setShowModal(true); }}
                  className="text-primary-500 hover:text-primary-400 transition-colors"
                >
                  add a target manually
                </button>
              </p>
            </div>
          </Card>

          {/* Quick-add recommendations in empty state */}
          <div className="mt-8 max-w-lg mx-auto w-full">
            <p className="eyebrow mb-2 text-center">Or quick-add a top employer</p>
            <div className="flex flex-wrap justify-center gap-2">
              {RECOMMENDED_TARGETS.map((rec) => {
                const alreadyAdded = addedCompanies.has(rec.company_name);
                const isAdding = addingRec === rec.company_name;
                return (
                  <button
                    key={rec.company_name}
                    onClick={() => !alreadyAdded && handleAddRecommended(rec)}
                    disabled={alreadyAdded || isAdding}
                    className={`bg-dark-800 border rounded-xl px-3 py-1.5 text-sm flex items-center gap-1.5 transition-all ${alreadyAdded ? 'border-green-500/30 text-green-500 cursor-default' : 'border-dark-600 text-dark-300 hover:border-dark-500 hover:text-dark-50'} disabled:opacity-60`}
                  >
                    {alreadyAdded ? (
                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
                    ) : isAdding ? (
                      <div className="animate-spin rounded-full h-3 w-3 border-b border-primary-400" />
                    ) : (
                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.5v15m7.5-7.5h-15" /></svg>
                    )}
                    {rec.company_name}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        <Modal isOpen={showModal} onClose={() => setShowModal(false)} title="Add Career Target">
          <form onSubmit={handleSubmit} className="space-y-4">
            <Input label="Company" value={form.company_name} onChange={e => setForm(f => ({ ...f, company_name: e.target.value }))} required />
            <Input label="Role Type" value={form.role_type} onChange={e => setForm(f => ({ ...f, role_type: e.target.value }))} placeholder="e.g. SWE Intern" />
            <div className="grid grid-cols-2 gap-4">
              <Input label="Location" value={form.location} onChange={e => setForm(f => ({ ...f, location: e.target.value }))} />
              <Input label="Target Term" value={form.target_term} onChange={e => setForm(f => ({ ...f, target_term: e.target.value }))} placeholder="e.g. Summer 2027" />
            </div>
            <div className="flex justify-end gap-3">
              <Button variant="secondary" type="button" onClick={() => setShowModal(false)}>Cancel</Button>
              <Button variant="primary" type="submit">Add</Button>
            </div>
          </form>
        </Modal>
      </div>
    );
  }

  // Populated state
  return (
    <div className="space-y-6">
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 text-sm px-4 py-3 rounded-lg flex items-center justify-between">
          {error}
          <button onClick={() => setError('')} className="ml-3 hover:text-red-300">✕</button>
        </div>
      )}
      <PageHeader
        eyebrow="CAREER"
        title="Career"
        subtitle="Track your target companies from first look to final offer."
        actions={
          <>
            <Button variant="accent" onClick={() => setAiChatOpen(true)}>
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
              </svg>
              AI Advisor
            </Button>
            <div className="flex bg-dark-800 ring-1 ring-black/5 dark:ring-white/10 rounded-lg p-0.5">
              <button
                onClick={() => setView('pipeline')}
                className={`px-3 py-1.5 rounded-md text-sm transition ${view === 'pipeline' ? 'bg-dark-50 text-dark-950' : 'text-dark-400 hover:text-dark-50'}`}
              >
                Pipeline
              </button>
              <button
                onClick={() => setView('list')}
                className={`px-3 py-1.5 rounded-md text-sm transition ${view === 'list' ? 'bg-dark-50 text-dark-950' : 'text-dark-400 hover:text-dark-50'}`}
              >
                List
              </button>
            </div>
            <Button variant="secondary" onClick={() => { setEditing(null); setForm({ company_name: '', role_type: '', location: '', target_term: '', status: 'researching', notes: '' }); setShowModal(true); }}>
              Add target
            </Button>
          </>
        }
      />

      {/* Pipeline metrics */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <Stat value={targets.length} label="Targets" />
        <Stat value={targets.filter(t => t.status === 'applied').length} label="Applied" />
        <Stat value={targets.filter(t => t.status === 'interviewing').length} label="Interviewing" />
        <Stat value={targets.filter(t => t.status === 'offer').length} label="Offers" />
      </div>

      {/* Recommended Tech Employers */}
      {RECOMMENDED_TARGETS.some(r => !addedCompanies.has(r.company_name)) && (
        <div>
          <p className="eyebrow mb-2">Recommended Tech Employers (Toronto)</p>
          <div className="flex gap-2.5 overflow-x-auto pb-1 scrollbar-hide">
            {RECOMMENDED_TARGETS.map((rec) => {
              const alreadyAdded = addedCompanies.has(rec.company_name);
              const isAdding = addingRec === rec.company_name;
              return (
                <div
                  key={rec.company_name}
                  className="bg-dark-800 border border-dark-600 rounded-xl px-4 py-2.5 flex items-center gap-3 flex-shrink-0"
                >
                  <div>
                    <p className="text-dark-50 text-sm font-medium leading-tight">{rec.company_name}</p>
                    <p className="text-dark-400 text-xs">{rec.role_type}</p>
                  </div>
                  {alreadyAdded ? (
                    <span className="text-green-500 text-xs font-medium flex items-center gap-1 flex-shrink-0">
                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
                      Added
                    </span>
                  ) : (
                    <button
                      onClick={() => handleAddRecommended(rec)}
                      disabled={isAdding}
                      className="text-primary-500 hover:text-primary-400 text-xs font-medium flex items-center gap-1 flex-shrink-0 disabled:opacity-50 transition-colors"
                    >
                      {isAdding ? (
                        <div className="animate-spin rounded-full h-3 w-3 border-b border-primary-400" />
                      ) : (
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.5v15m7.5-7.5h-15" /></svg>
                      )}
                      Add
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className="space-y-6">
        {view === 'pipeline' ? (
          <ApplicationPipeline targets={targets} onEdit={handleEdit} onStatusChange={handleStatusChange} />
        ) : (
          <Card>
            <div className="flex items-center gap-3 mb-4">
              <span className="icon-chip w-8 h-8 rounded-lg flex items-center justify-center text-primary-500">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0H5m14 0h2M5 21H3m4-14h2m-2 4h2m6-4h2m-2 4h2M9 21v-4a1 1 0 011-1h4a1 1 0 011 1v4" />
                </svg>
              </span>
              <h2 className="font-display text-xl tracking-tight text-dark-50">Target Companies</h2>
            </div>
            <div className="space-y-3">
              {targets.map(t => (
                <TargetCard key={t.id} target={t} onEdit={handleEdit} onDelete={handleDelete} />
              ))}
            </div>
          </Card>
        )}

        {events.length > 0 && (
          <Card>
            <div className="flex items-center gap-3 mb-4">
              <span className="icon-chip w-8 h-8 rounded-lg flex items-center justify-center text-primary-500">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6v6l4 2m6-2a10 10 0 11-20 0 10 10 0 0120 0z" />
                </svg>
              </span>
              <h2 className="font-display text-xl tracking-tight text-dark-50">Timeline</h2>
            </div>
            <CareerTimeline events={events} />
          </Card>
        )}
      </div>

      <ResumeReview />

      <Modal isOpen={showModal} onClose={() => setShowModal(false)} title={editing ? 'Edit Career Target' : 'Add Career Target'}>
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input label="Company" value={form.company_name} onChange={e => setForm(f => ({ ...f, company_name: e.target.value }))} required />
          <Input label="Role Type" value={form.role_type} onChange={e => setForm(f => ({ ...f, role_type: e.target.value }))} placeholder="e.g. SWE Intern" />
          <div className="grid grid-cols-2 gap-4">
            <Input label="Location" value={form.location} onChange={e => setForm(f => ({ ...f, location: e.target.value }))} />
            <Input label="Target Term" value={form.target_term} onChange={e => setForm(f => ({ ...f, target_term: e.target.value }))} placeholder="e.g. Summer 2027" />
          </div>
          <div>
            <label htmlFor="careerpage-status" className="block text-sm text-dark-300 mb-1">Status</label>
            <select id="careerpage-status"
              value={form.status}
              onChange={e => setForm(f => ({ ...f, status: e.target.value }))}
              className="w-full bg-dark-800 border border-dark-600 text-dark-50 rounded-lg px-3 py-2"
            >
              <option value="researching">Researching</option>
              <option value="applied">Applied</option>
              <option value="interviewing">Interviewing</option>
              <option value="offer">Offer</option>
              <option value="rejected">Rejected</option>
            </select>
          </div>
          <div>
            <label htmlFor="careerpage-notes" className="block text-sm text-dark-300 mb-1">Notes</label>
            <textarea id="careerpage-notes"
              value={form.notes}
              onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
              className="w-full bg-dark-800 border border-dark-600 text-dark-50 rounded-lg px-3 py-2 h-20 resize-none"
            />
          </div>
          {formError && <p className="text-red-400 text-sm">{formError}</p>}
          <div className="flex justify-end gap-3">
            <Button variant="secondary" type="button" onClick={() => setShowModal(false)}>Cancel</Button>
            <Button variant="primary" type="submit">{editing ? 'Save' : 'Add'}</Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
