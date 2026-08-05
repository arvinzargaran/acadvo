import { useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router';
import { useAuth } from '../context/AuthContext';
import Button from '../components/ui/Button';
import Input from '../components/ui/Input';
import Select from '../components/ui/Select';
import AuthLayout from '../components/layout/AuthLayout';
import { CANADIAN_UNIVERSITIES } from '../data/universities';
import { PROGRAMS } from '../data/programs';
import { MIN_PASSWORD_LENGTH, PASSWORD_HINT } from '../utils/password';

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
    // The searchable university field only commits a value when an option is
    // picked — typing text without selecting leaves it blank. Guard so the form
    // can't submit with an empty/half-typed university.
    if (!form.university) {
      setError('Please select your university from the list.');
      return;
    }
    if (!form.program) {
      setError('Please select your program.');
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
    <AuthLayout eyebrow="Start your plan" title="Create account" wide>
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

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Input
            label="Password"
            type="password"
            value={form.password}
            onChange={update('password')}
            placeholder={PASSWORD_HINT}
            required
            minLength={MIN_PASSWORD_LENGTH}
          />

          <Input
            label="Confirm Password"
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            placeholder="Repeat"
            required
          />
        </div>

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

        <Button type="submit" variant="accent" loading={loading} className="w-full">
          Create account
        </Button>
      </form>

      <p className="mt-4 text-sm text-dark-400">
        Already have an account?{' '}
        <Link to="/login" className="text-primary-600 dark:text-primary-400 hover:underline font-medium">
          Sign in
        </Link>
      </p>
    </AuthLayout>
  );
}
