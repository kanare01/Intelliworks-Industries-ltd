import React, { useState } from 'react';
import { useAuth, ProtectedRoute } from './context/AuthContext';
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
          <ProtectedRoute
            allowedRoles={['Client', 'Admin']}
            fallback={
              <div className="max-w-md mx-auto my-16 p-8 bg-slate-900/60 border border-slate-800 rounded-2xl text-center shadow-2xl">
                <div className="w-12 h-12 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 mx-auto flex items-center justify-center mb-4">
                  <ShieldCheck className="w-6 h-6" />
                </div>
                <h2 className="text-xl font-bold text-slate-100 mb-2">Authentication Required</h2>
                <p className="text-sm text-slate-400 mb-6">
                  Please sign in to access the Client Workspace and manage your projects.
                </p>
                <button
                  onClick={() => openAuth('login')}
                  className="w-full py-2.5 px-4 bg-indigo-600 hover:bg-indigo-500 text-white font-medium rounded-lg transition-colors shadow-lg shadow-indigo-600/20 cursor-pointer"
                >
                  Sign In to Continue
                </button>
              </div>
            }
          >
            <ClientDashboard initialSubTab="overview" />
          </ProtectedRoute>
        )}
        {currentTab === 'client-create' && (
          <ProtectedRoute
            allowedRoles={['Client', 'Admin']}
            fallback={
              <div className="max-w-md mx-auto my-16 p-8 bg-slate-900/60 border border-slate-800 rounded-2xl text-center shadow-2xl">
                <div className="w-12 h-12 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 mx-auto flex items-center justify-center mb-4">
                  <ShieldCheck className="w-6 h-6" />
                </div>
                <h2 className="text-xl font-bold text-slate-100 mb-2">Commission Assignment</h2>
                <p className="text-sm text-slate-400 mb-6">
                  Sign in or create an account to post assignments and deposit escrow safely.
                </p>
                <button
                  onClick={() => openAuth('login')}
                  className="w-full py-2.5 px-4 bg-indigo-600 hover:bg-indigo-500 text-white font-medium rounded-lg transition-colors shadow-lg shadow-indigo-600/20 cursor-pointer"
                >
                  Sign In to Post
                </button>
              </div>
            }
          >
            <ClientDashboard initialSubTab="create" />
          </ProtectedRoute>
        )}

        {/* Writer Routes */}
        {currentTab === 'writer-marketplace' && (
          <ProtectedRoute
            allowedRoles={['Writer', 'Admin']}
            fallback={
              <div className="max-w-md mx-auto my-16 p-8 bg-slate-900/60 border border-slate-800 rounded-2xl text-center shadow-2xl">
                <div className="w-12 h-12 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 mx-auto flex items-center justify-center mb-4">
                  <ShieldCheck className="w-6 h-6" />
                </div>
                <h2 className="text-xl font-bold text-slate-100 mb-2">Specialist Portal</h2>
                <p className="text-sm text-slate-400 mb-6">
                  Sign in with an approved Specialist or Writer account to browse assignments.
                </p>
                <button
                  onClick={() => openAuth('login')}
                  className="w-full py-2.5 px-4 bg-indigo-600 hover:bg-indigo-500 text-white font-medium rounded-lg transition-colors shadow-lg shadow-indigo-600/20 cursor-pointer"
                >
                  Sign In as Specialist
                </button>
              </div>
            }
          >
            <WriterDashboard initialSubTab="marketplace" />
          </ProtectedRoute>
        )}
        {currentTab === 'writer-workspace' && (
          <ProtectedRoute
            allowedRoles={['Writer', 'Admin']}
            fallback={
              <div className="max-w-md mx-auto my-16 p-8 bg-slate-900/60 border border-slate-800 rounded-2xl text-center shadow-2xl">
                <div className="w-12 h-12 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 mx-auto flex items-center justify-center mb-4">
                  <ShieldCheck className="w-6 h-6" />
                </div>
                <h2 className="text-xl font-bold text-slate-100 mb-2">Specialist Workspace</h2>
                <p className="text-sm text-slate-400 mb-6">
                  Sign in to view your active claimed contracts and deliver submissions.
                </p>
                <button
                  onClick={() => openAuth('login')}
                  className="w-full py-2.5 px-4 bg-indigo-600 hover:bg-indigo-500 text-white font-medium rounded-lg transition-colors shadow-lg shadow-indigo-600/20 cursor-pointer"
                >
                  Sign In to Continue
                </button>
              </div>
            }
          >
            <WriterDashboard initialSubTab="workspace" />
          </ProtectedRoute>
        )}

        {/* Admin Route */}
        {currentTab.startsWith('admin') && (
          <ProtectedRoute
            allowedRoles={['Admin']}
            fallback={
              <div className="max-w-md mx-auto my-16 p-8 bg-rose-950/20 border border-rose-900/40 rounded-2xl text-center shadow-2xl">
                <div className="w-12 h-12 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 mx-auto flex items-center justify-center mb-4">
                  <ShieldCheck className="w-6 h-6" />
                </div>
                <h2 className="text-xl font-bold text-rose-200 mb-2">Restricted Command Center</h2>
                <p className="text-sm text-slate-400 mb-6">
                  Access requires an active Administrator session with cryptographic JWT verification.
                </p>
                <button
                  onClick={() => openAuth('login')}
                  className="w-full py-2.5 px-4 bg-rose-600 hover:bg-rose-500 text-white font-medium rounded-lg transition-colors shadow-lg shadow-rose-600/20 cursor-pointer"
                >
                  Admin Sign In
                </button>
              </div>
            }
          >
            <AdminDashboard />
          </ProtectedRoute>
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
