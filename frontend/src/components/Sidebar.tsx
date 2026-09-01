import { NavLink } from 'react-router-dom';
import {
  HomeIcon,
  ChatBubbleLeftRightIcon,
  DocumentTextIcon,
  MagnifyingGlassIcon,
  Cog6ToothIcon,
  ArrowRightOnRectangleIcon,
  SunIcon,
  MoonIcon,
  ChatBubbleOvalLeftEllipsisIcon,
} from '@heroicons/react/24/outline';
import { useAuth } from '../hooks/useAuth';
import { useTheme } from '../hooks/useTheme';

const navigation = [
  { name: 'Dashboard', href: '/', icon: HomeIcon },
  { name: 'Documents', href: '/documents', icon: DocumentTextIcon },
  { name: 'Chat', href: '/chat', icon: ChatBubbleLeftRightIcon },
  { name: 'Conversations', href: '/conversations', icon: ChatBubbleOvalLeftEllipsisIcon },
  { name: 'Search', href: '/search', icon: MagnifyingGlassIcon },
  { name: 'Settings', href: '/settings', icon: Cog6ToothIcon },
];

export default function Sidebar() {
  const { logout } = useAuth();
  const { theme, toggleTheme } = useTheme();

  return (
    <div className="flex flex-col w-64 h-screen bg-[var(--color-bg-secondary)] border-r border-[var(--color-border)]">
      <div className="flex items-center h-16 px-6 border-b border-[var(--color-border)]">
        <h1 className="text-xl font-bold text-[var(--color-text-primary)]">Ultimate RAG</h1>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto scrollbar-thin">
        {navigation.map((item) => (
          <NavLink
            key={item.name}
            to={item.href}
            className={({ isActive }) =>
              `sidebar-link ${isActive ? 'sidebar-link-active' : 'sidebar-link-inactive'}`
            }
          >
            <item.icon className="mr-3 h-5 w-5 flex-shrink-0" aria-hidden="true" />
            {item.name}
          </NavLink>
        ))}
      </nav>

      <div className="p-4 border-t border-[var(--color-border)] space-y-2">
        <button
          onClick={toggleTheme}
          className="sidebar-link sidebar-link-inactive w-full"
        >
          {theme === 'light' ? (
            <MoonIcon className="mr-3 h-5 w-5 flex-shrink-0" aria-hidden="true" />
          ) : (
            <SunIcon className="mr-3 h-5 w-5 flex-shrink-0" aria-hidden="true" />
          )}
          {theme === 'light' ? 'Dark Mode' : 'Light Mode'}
        </button>

        <button
          onClick={logout}
          className="sidebar-link sidebar-link-inactive w-full text-red-600 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-900/20"
        >
          <ArrowRightOnRectangleIcon className="mr-3 h-5 w-5 flex-shrink-0" aria-hidden="true" />
          Logout
        </button>
      </div>
    </div>
  );
}
