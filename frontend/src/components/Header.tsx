import { BellIcon } from '@heroicons/react/24/outline';

interface HeaderProps {
  title: string;
  subtitle?: string;
}

export default function Header({ title, subtitle }: HeaderProps) {
  return (
    <div className="h-16 bg-[var(--color-bg-primary)] border-b border-[var(--color-border)] px-6 flex items-center justify-between">
      <div>
        <h1 className="text-xl font-semibold text-[var(--color-text-primary)]">{title}</h1>
        {subtitle && (
          <p className="text-sm text-[var(--color-text-secondary)]">{subtitle}</p>
        )}
      </div>

      <div className="flex items-center space-x-4">
        <button className="p-2 rounded-lg text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-secondary)] transition-colors duration-200 relative">
          <BellIcon className="h-5 w-5" aria-hidden="true" />
          <span className="absolute top-1.5 right-1.5 h-2 w-2 bg-red-500 rounded-full"></span>
        </button>
      </div>
    </div>
  );
}
