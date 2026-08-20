import { useState } from 'react';
import { Outlet } from 'react-router';
import Sidebar from './Sidebar';
import Topbar from './Topbar';
import VerifyEmailBanner from './VerifyEmailBanner';
import ChatWidget from '../chat/ChatWidget';
import OnboardingTour from '../tour/OnboardingTour';

export default function AppShell() {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="min-h-screen">
      {/* Mobile overlay — decorative dismiss layer, hidden from assistive tech:
          the sidebar carries its own labelled close button, and exposing this
          would put an unlabelled full-screen tab stop in front of it. */}
      {sidebarOpen && (
        <div
          aria-hidden="true"
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Skip link — the first thing a keyboard user reaches.
          The sidebar is ~15 links, and it renders before <main> in the DOM, so
          without this every page change costs fifteen tabs before reaching any
          content. Visually hidden until focused. */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:z-[60] focus:top-3 focus:left-3 focus:bg-primary-600 focus:text-white focus:px-4 focus:py-2 focus:text-sm focus:font-medium"
      >
        Skip to main content
      </a>

      {/* Sidebar: hidden on mobile by default, shown via sidebarOpen */}
      <div className={`
        fixed inset-y-0 left-0 z-50 transform transition-transform duration-200 ease-in-out
        lg:translate-x-0
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
        <Sidebar onClose={() => setSidebarOpen(false)} />
      </div>

      <div className="lg:ml-64 flex flex-col min-h-screen">
        <Topbar onMenuToggle={() => setSidebarOpen(true)} />
        <VerifyEmailBanner />
        <main id="main-content" tabIndex={-1} className="flex-1 p-5 sm:p-8 lg:p-12">
          <Outlet />
        </main>
      </div>
      <ChatWidget />
      <OnboardingTour />
    </div>
  );
}
