import { useState } from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import Topbar from './Topbar';
import ChatWidget from '../chat/ChatWidget';
import OnboardingTour from '../tour/OnboardingTour';

export default function AppShell() {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="min-h-screen">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

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
        <main className="flex-1 p-5 sm:p-8 lg:p-12">
          <Outlet />
        </main>
      </div>
      <ChatWidget />
      <OnboardingTour />
    </div>
  );
}
