'use client';

import { useRouter } from 'next/navigation';

import type { AuthUser } from '@/lib/api';
import { logout } from '@/lib/api';

interface NavBarProps {
  user: AuthUser | null;
  onUserChange?: (user: AuthUser | null) => void;
  showTemplatesLink?: boolean;
}

export function NavBar({ user, onUserChange, showTemplatesLink = false }: NavBarProps) {
  const router = useRouter();

  function handleLogout() {
    logout();
    onUserChange?.(null);
  }

  return (
    <nav className="mx-auto flex w-full max-w-5xl items-center justify-between">
      <div className="flex items-center gap-2">
        <span className="h-5 w-5 rounded-[4px] bg-accent" aria-hidden />
        <span className="text-[15px] font-semibold tracking-[-0.02em]">Pixel2Layer</span>
      </div>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => router.push('/')}
          className="h-9 rounded-[10px] border border-bordered px-4 text-[13px] font-medium text-secondary transition-colors hover:bg-raised"
        >
          New from image
        </button>
        {showTemplatesLink && (
          <button
            type="button"
            onClick={() => router.push('/templates')}
            className="h-9 rounded-[10px] border border-bordered px-4 text-[13px] font-medium text-secondary transition-colors hover:bg-raised"
          >
            Templates
          </button>
        )}
        {user ? (
          <>
            <button
              type="button"
              onClick={() => router.push('/dashboard')}
              className="h-9 rounded-[10px] border border-bordered px-4 text-[13px] font-medium text-secondary transition-colors hover:bg-raised"
            >
              My projects
            </button>
            <button
              type="button"
              onClick={handleLogout}
              className="h-9 rounded-[10px] px-3 text-[13px] font-medium text-secondary transition-colors hover:bg-raised"
            >
              Log out
            </button>
          </>
        ) : (
          <button
            type="button"
            onClick={() => router.push('/login')}
            className="h-9 rounded-[10px] border border-bordered px-4 text-[13px] font-medium text-secondary transition-colors hover:bg-raised"
          >
            Sign in
          </button>
        )}
      </div>
    </nav>
  );
}
