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
import { MINIMUM_AGE, TERMS_VERSION } from '../legal/config';

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
  const [acceptedTerms, setAcceptedTerms] = useState(false);
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
    if (!acceptedTerms) {
      // `required` on the input already blocks submission in a browser; this
      // catches a programmatic submit and keeps the rule in one readable place.
      setError('Please confirm your age and accept the terms to continue.');
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
      // The server requires the acceptance and stamps its own timestamp; the
      // version travels with it so the record says WHAT was accepted.
      await register({ ...form, accepted_terms: true, terms_version: TERMS_VERSION });
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
        {/* Announced, not just shown: every failure this form can produce — a
            password mismatch, an unticked consent box, a rejected email — writes
            here and nowhere else, so without a live region a screen-reader user
            submits and is told nothing at all. */}
        {error && (
          <div role="alert" className="bg-red-500/10 border border-red-500/20 rounded-lg p-3 text-sm text-red-600 dark:text-red-400">
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

        {/* An explicit tick, not a "by clicking Create account you agree" line.
            Consent is only meaningful if the person took an action knowing what
            it meant, and the age declaration has to be made rather than assumed
            — the OPC treats an unstated age as no consent at all. */}
        <div className="flex items-start gap-2.5">
          <input
            id="accept-terms"
            type="checkbox"
            required
            checked={acceptedTerms}
            onChange={(e) => setAcceptedTerms(e.target.checked)}
            className="mt-1 h-4 w-4 shrink-0 accent-accent-500"
          />
          <label htmlFor="accept-terms" className="text-sm text-dark-400 leading-relaxed">
            I am {MINIMUM_AGE} or older, and I agree to the{' '}
            <Link to="/terms" className="text-primary-600 dark:text-primary-400 hover:underline">
              Terms of Use
            </Link>{' '}
            and the{' '}
            <Link to="/privacy" className="text-primary-600 dark:text-primary-400 hover:underline">
              Privacy Policy
            </Link>
            , including that AI features send parts of my academic record to a provider in the
            United States.
          </label>
        </div>

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
