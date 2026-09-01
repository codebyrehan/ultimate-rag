import { BellIcon, ArrowRightOnRectangleIcon, UserCircleIcon, SunIcon, MoonIcon } from '@heroicons/react/24/outline';
import { useAuth } from '../hooks/useAuth';
import { useTheme } from '../hooks/useTheme';
import Dropdown from './ui/Dropdown';

interface HeaderProps {
  title: string;
  subtitle?: string;
}

export default function Header({ title, subtitle }: HeaderProps) {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();

  return (
    <header className="h-16 bg-[var(--color-bg-primary)]/80 backdrop-blur-xl border-b border-[var(--color-border)] px-6 flex items-center justify-between sticky top-0 z-30">
      <div>
        <h1 className="text-xl font-semibold text-[var(--color-text-primary)] tracking-tight">{title}</h1>
        {subtitle && (
          <p className="text-sm text-[var(--color-text-secondary)]">{subtitle}</p>
        )}
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={toggleTheme}
          className="p-2 rounded-lg text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-secondary)] transition-colors duration-200"
          title={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
        >
          {theme === 'light' ? (
            <MoonIcon className="h-5 w-5" aria-hidden="true" />
          ) : (
            <SunIcon className="h-5 w-5" aria-hidden="true" />
          )}
        </button>

        <button className="p-2 rounded-lg text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-secondary)] transition-colors duration-200 relative">
          <BellIcon className="h-5 w-5" aria-hidden="true" />
          <span className="absolute top-1.5 right-1.5 h-2 w-2 bg-red-500 rounded-full ring-2 ring-[var(--color-bg-primary)]" />
        </button>

        <Dropdown
          align="right"
          trigger={
            <div className="flex items-center gap-3 p-1.5 rounded-lg hover:bg-[var(--color-bg-secondary)] transition-colors duration-200 cursor-pointer">
              <div className="h-8 w-8 rounded-full bg-[var(--color-accent)] flex items-center justify-center text-white text-sm font-medium">
                {user?.email?.charAt(0).toUpperCase() || 'U'}
              </div>
              <div className="hidden sm:block">
                <p className="text-sm font-medium text-[var(--color-text-primary)]">{user?.email}</p>
              </div>
            </div>
          }
          items={[
            {
              label: 'Profile',
              icon: <UserCircleIcon className="h-4 w-4" />,
              onClick: () => {},
            },
            {
              label: 'Settings',
              icon: <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>,
              onClick: () => window.location.href = '/settings',
            },
            {
              label: 'Sign out',
              icon: <ArrowRightOnRectangleIcon className="h-4 w-4" />,
              onClick: logout,
              danger: true,
            },
          ]}
        />
      </div>
    </header>
  );
}
