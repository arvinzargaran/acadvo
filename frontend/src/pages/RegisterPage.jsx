import { useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import Button from '../components/ui/Button';
import Input from '../components/ui/Input';
import Select from '../components/ui/Select';
import { CANADIAN_UNIVERSITIES } from '../data/universities';
import { PROGRAMS } from '../data/programs';

export default function RegisterPage() {
  const { register, user } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({
    full_name: '',
    email: '',
    password: '',
    university: '',
    program: '',
  });
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const update = (field) => (e) =>
    setForm((prev) => ({ ...prev, [field]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (form.password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }
    setLoading(true);
    try {
      await register(form);
      navigate('/onboarding', { replace: true });
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map(d => d.msg).join(', ') : 'Registration failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  if (user) {
    return <Navigate to={user.onboarding_complete ? '/dashboard' : '/onboarding'} replace />;
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 bg-dark-950">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold font-display text-primary-600">Acadvo</h1>
          <p className="text-gray-400 mt-1">Create your account</p>
        </div>

        <div className="bg-white/5 border border-white/10 rounded-xl p-6 shadow-sm">
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3 text-sm text-red-600 dark:text-red-400">
                {error}
              </div>
            )}

            <Input
              label="Full Name"
              value={form.full_name}
              onChange={update('full_name')}
              placeholder="Jane Doe"
              required
            />

            <Input
              label="Email"
              type="email"
              value={form.email}
              onChange={update('email')}
              placeholder="you@example.com"
              required
            />

            <Input
              label="Password"
              type="password"
              value={form.password}
              onChange={update('password')}
              placeholder="Min 8 characters"
              required
              minLength={8}
            />

            <Input
              label="Confirm Password"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Repeat your password"
              required
            />

            <Select
              label="University"
              searchable
              options={CANADIAN_UNIVERSITIES}
              value={form.university}
              onChange={update('university')}
              placeholder="Search your university..."
            />

            <Select
              label="Program"
              options={PROGRAMS}
              value={form.program}
              onChange={update('program')}
              placeholder="Select your program"
            />

            <Button type="submit" loading={loading} className="w-full">
              Create account
            </Button>
          </form>

          <p className="mt-4 text-center text-sm text-gray-400">
            Already have an account?{' '}
            <Link to="/login" className="text-primary-400 hover:text-primary-300">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
