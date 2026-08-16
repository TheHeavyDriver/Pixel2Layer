'use client';

import { Suspense, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';

import { login } from '@/lib/api';

const inputCls =
  'h-10 w-full rounded-[10px] border border-bordered bg-raised px-3 text-[13px] text-primary outline-none transition-colors placeholder:text-muted focus:border-accent';

function LoginForm() {
  const router = useRouter();
  const redirect = useSearchParams().get('redirect') ?? '/dashboard';
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login({ email, password });
      router.replace(redirect);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="w-full max-w-[380px] rounded-[16px] border border-bordered bg-surface p-6">
      <h1 className="text-[20px] font-semibold tracking-[-0.02em]">Welcome back</h1>
      <p className="mt-1 text-[13px] text-secondary">Sign in to your projects.</p>
      <form className="mt-5 flex flex-col gap-3" onSubmit={onSubmit} data-testid="login-form">
        <input
          type="email"
          required
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className={inputCls}
          autoComplete="email"
        />
        <input
          type="password"
          required
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className={inputCls}
          autoComplete="current-password"
        />
        {error && <p className="text-[12px] text-danger" role="alert">{error}</p>}
        <button
          type="submit"
          disabled={busy}
          className="h-10 rounded-[10px] bg-accent text-[13px] font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
        >
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
      <p className="mt-4 text-center text-[12px] text-secondary">
        No account?{' '}
        <Link href={`/signup${redirect !== '/dashboard' ? `?redirect=${encodeURIComponent(redirect)}` : ''}`} className="text-accent hover:text-accent-hover">
          Create one
        </Link>
      </p>
    </div>
  );
}

export default function LoginPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-base px-4">
      <Suspense fallback={null}>
        <LoginForm />
      </Suspense>
    </main>
  );
}