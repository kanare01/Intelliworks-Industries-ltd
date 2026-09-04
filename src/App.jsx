import React, { useState } from 'react';
import { useAuth } from './context/AuthContext';
import { Navbar } from './components/Navbar';
import { AcademicIntegrityBanner } from './components/AcademicIntegrityBanner';
import { ConfigurationStatusModal } from './components/ConfigurationStatusModal';
import { AuthModal } from './pages/AuthModal';
import { HomeView } from './pages/HomeView';
import { ClientDashboard } from './pages/ClientDashboard';
import { WriterDashboard } from './pages/WriterDashboard';
import { AdminDashboard } from './pages/AdminDashboard';
import { TransactionsView } from './pages/TransactionsView';
import { DisputesView } from './pages/DisputesView';
import { ShieldCheck, Heart, Database, BookOpen } from 'lucide-react';

export function App() {
  const { user, profile } = useAuth();
  const [currentTab, setCurrentTab] = useState('home');

  // Modals
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [authMode, setAuthMode] = useState('login');
  const [policyModalOpen, setPolicyModalOpen] = useState(false);
  const [configModalOpen, setConfigModalOpen] = useState(false);

  const openAuth = (mode = 'login') => {
    setAuthMode(mode);
    setAuthModalOpen(true);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col selection:bg-indigo-600 selection:text-white font-sans antialiased">
      {/* Navigation */}
      <Navbar
        currentTab={currentTab}
        setCurrentTab={setCurrentTab}
        onOpenAuth={openAuth}
        onOpenPolicy={() => setPolicyModalOpen(true)}
        onOpenConfig={() => setConfigModalOpen(true)}
      />

      {/* Main Content Area */}
      <main className="flex-1">
        {currentTab === 'home' && (
          <HomeView
            onOpenAuth={openAuth}
            onOpenPolicy={() => setPolicyModalOpen(true)}
            onOpenConfig={() => setConfigModalOpen(true)}
            onSelectTab={setCurrentTab}
          />
        )}

        {/* Client Routes */}
        {currentTab === 'client-overview' && (
          <ClientDashboard initialSubTab="overview" />
        )}
        {currentTab === 'client-create' && (
          <ClientDashboard initialSubTab="create" />
        )}

        {/* Writer Routes */}
        {currentTab === 'writer-marketplace' && (
          <WriterDashboard initialSubTab="marketplace" />
        )}
        {currentTab === 'writer-workspace' && (
          <WriterDashboard initialSubTab="workspace" />
        )}

        {/* Admin Route */}
        {currentTab.startsWith('admin') && (
          <AdminDashboard />
        )}

        {/* Shared Financial & Dispute Views */}
        {currentTab === 'transactions' && (
          <TransactionsView />
        )}
        {currentTab === 'disputes' && (
          <DisputesView />
        )}
      </main>

      {/* Institutional Footer */}
      <footer className="border-t border-slate-900 bg-slate-950/80 py-8 text-xs text-slate-500">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center space-x-2">
            <span className="font-bold text-slate-300">INTELLIWORKS INDUSTRIES</span>
            <span>—</span>
            <span>Institutional Academic & Specialist Marketplace</span>
          </div>

          <div className="flex items-center space-x-4">
            <button
              onClick={() => setPolicyModalOpen(true)}
              className="hover:text-cyan-400 flex items-center space-x-1"
            >
              <ShieldCheck className="w-3.5 h-3.5 text-cyan-400" />
              <span>Honor Code</span>
            </button>
            <button
              onClick={() => setConfigModalOpen(true)}
              className="hover:text-indigo-400 flex items-center space-x-1"
            >
              <Database className="w-3.5 h-3.5 text-indigo-400" />
              <span>Supabase Infrastructure</span>
            </button>
          </div>
        </div>
      </footer>

      {/* Global Modals */}
      <AuthModal
        isOpen={authModalOpen}
        onClose={() => setAuthModalOpen(false)}
        initialMode={authMode}
      />

      <AcademicIntegrityBanner
        isOpen={policyModalOpen}
        onClose={() => setPolicyModalOpen(false)}
      />

      <ConfigurationStatusModal
        isOpen={configModalOpen}
        onClose={() => setConfigModalOpen(false)}
      />
    </div>
  );
}

export default App;
