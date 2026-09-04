import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';
import { 
  ShieldCheck, 
  Bell, 
  User, 
  LogOut, 
  CheckCircle2, 
  AlertCircle, 
  Layers, 
  FileText, 
  DollarSign, 
  HelpCircle,
  Database
} from 'lucide-react';

export function Navbar({ 
  currentTab, 
  setCurrentTab, 
  onOpenAuth, 
  onOpenPolicy, 
  onOpenConfig 
}) {
  const { user, profile, logout, isSupabaseConfigured } = useAuth();
  const [notifications, setNotifications] = useState([]);
  const [showNotifications, setShowNotifications] = useState(false);
  const [systemHealth, setSystemHealth] = useState({ online: false, configured: false });

  useEffect(() => {
    // Check backend health
    api.getHealth()
      .then(res => {
        setSystemHealth({ online: res.status === 'online', configured: res.configured });
      })
      .catch(() => {
        setSystemHealth({ online: false, configured: false });
      });

    if (user) {
      api.getNotifications()
        .then(res => setNotifications(res.notifications || []))
        .catch(() => {});
    }
  }, [user]);

  const unreadCount = notifications.filter(n => !n.is_read).length;

  const handleMarkAllRead = async () => {
    try {
      await api.markAllNotificationsRead();
      setNotifications(prev => prev.map(n => ({ ...n, is_read: true })));
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <header className="sticky top-0 z-40 w-full border-b border-slate-800 bg-slate-950/90 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        
        {/* Brand */}
        <div className="flex items-center space-x-3 cursor-pointer" onClick={() => setCurrentTab('home')}>
          <div className="w-9 h-9 rounded-lg bg-gradient-to-tr from-indigo-600 to-cyan-500 flex items-center justify-center shadow-lg shadow-indigo-500/20">
            <span className="font-extrabold text-white text-base tracking-tighter">IW</span>
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-bold text-base text-slate-100 tracking-tight font-sans">
                INTELLIWORKS
              </span>
              <span className="text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
                Industries
              </span>
            </div>
            <p className="text-[11px] text-slate-400 hidden sm:block">Academic & Professional Marketplace</p>
          </div>
        </div>

        {/* Center Nav Items */}
        <nav className="hidden md:flex items-center space-x-1 text-sm font-medium">
          {profile?.role === 'Client' && (
            <>
              <button
                onClick={() => setCurrentTab('client-overview')}
                className={`px-3 py-1.5 rounded-md transition ${currentTab === 'client-overview' ? 'bg-slate-800 text-white font-semibold' : 'text-slate-400 hover:text-white'}`}
              >
                My Projects
              </button>
              <button
                onClick={() => setCurrentTab('client-create')}
                className={`px-3 py-1.5 rounded-md transition ${currentTab === 'client-create' ? 'bg-indigo-600 text-white font-semibold' : 'text-indigo-400 hover:bg-indigo-950/40'}`}
              >
                + New Project
              </button>
            </>
          )}

          {profile?.role === 'Writer' && (
            <>
              <button
                onClick={() => setCurrentTab('writer-marketplace')}
                className={`px-3 py-1.5 rounded-md transition ${currentTab === 'writer-marketplace' ? 'bg-slate-800 text-white font-semibold' : 'text-slate-400 hover:text-white'}`}
              >
                Marketplace
              </button>
              <button
                onClick={() => setCurrentTab('writer-workspace')}
                className={`px-3 py-1.5 rounded-md transition ${currentTab === 'writer-workspace' ? 'bg-slate-800 text-white font-semibold' : 'text-slate-400 hover:text-white'}`}
              >
                Workspace
              </button>
            </>
          )}

          {profile?.role === 'Admin' && (
            <>
              <button
                onClick={() => setCurrentTab('admin-metrics')}
                className={`px-3 py-1.5 rounded-md transition ${currentTab.startsWith('admin') ? 'bg-amber-500/20 text-amber-300 font-semibold border border-amber-500/30' : 'text-amber-400 hover:text-white'}`}
              >
                Command Center
              </button>
            </>
          )}

          {user && (
            <>
              <button
                onClick={() => setCurrentTab('transactions')}
                className={`px-3 py-1.5 rounded-md transition ${currentTab === 'transactions' ? 'bg-slate-800 text-white' : 'text-slate-400 hover:text-white'}`}
              >
                Ledger
              </button>
              <button
                onClick={() => setCurrentTab('disputes')}
                className={`px-3 py-1.5 rounded-md transition ${currentTab === 'disputes' ? 'bg-slate-800 text-white' : 'text-slate-400 hover:text-white'}`}
              >
                Disputes
              </button>
            </>
          )}

          <button
            onClick={onOpenPolicy}
            className="flex items-center space-x-1 text-slate-400 hover:text-cyan-400 px-3 py-1.5 rounded-md transition text-xs font-semibold"
          >
            <ShieldCheck className="w-3.5 h-3.5 text-cyan-400" />
            <span>Integrity Policy</span>
          </button>
        </nav>

        {/* Right side actions */}
        <div className="flex items-center space-x-3">
          {/* Status Indicator */}
          <button 
            onClick={onOpenConfig}
            className={`flex items-center space-x-1.5 text-xs px-2.5 py-1 rounded-full border transition ${
              systemHealth.configured 
                ? 'bg-emerald-950/40 text-emerald-300 border-emerald-800/60 hover:bg-emerald-900/30' 
                : 'bg-amber-950/40 text-amber-300 border-amber-800/60 hover:bg-amber-900/30'
            }`}
            title="System & Supabase Connectivity Status"
          >
            <span className={`w-2 h-2 rounded-full ${systemHealth.configured ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'}`}></span>
            <span className="hidden sm:inline font-mono">
              {systemHealth.configured ? 'Supabase Connected' : 'Supabase Setup'}
            </span>
          </button>

          {user ? (
            <div className="flex items-center space-x-2">
              {/* Notifications */}
              <div className="relative">
                <button
                  onClick={() => setShowNotifications(!showNotifications)}
                  className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition relative"
                >
                  <Bell className="w-5 h-5" />
                  {unreadCount > 0 && (
                    <span className="absolute top-1 right-1 w-4 h-4 bg-indigo-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center">
                      {unreadCount}
                    </span>
                  )}
                </button>

                {showNotifications && (
                  <div className="absolute right-0 mt-2 w-80 bg-slate-900 border border-slate-800 rounded-xl shadow-2xl z-50 p-3">
                    <div className="flex items-center justify-between border-b border-slate-800 pb-2 mb-2">
                      <span className="text-xs font-bold text-slate-200 uppercase tracking-wider">Notifications</span>
                      {unreadCount > 0 && (
                        <button onClick={handleMarkAllRead} className="text-[11px] text-indigo-400 hover:underline">
                          Mark all read
                        </button>
                      )}
                    </div>
                    <div className="max-h-64 overflow-y-auto space-y-2">
                      {notifications.length === 0 ? (
                        <p className="text-xs text-slate-500 text-center py-4">No notifications yet.</p>
                      ) : (
                        notifications.map(n => (
                          <div 
                            key={n.id} 
                            className={`p-2 rounded-lg text-xs border ${n.is_read ? 'bg-slate-950/40 border-slate-800/40 text-slate-400' : 'bg-indigo-950/30 border-indigo-800/50 text-slate-200'}`}
                          >
                            <p className="font-semibold text-slate-200">{n.notification_type}</p>
                            <p className="mt-0.5">{n.message}</p>
                            <span className="text-[10px] text-slate-500 mt-1 block">
                              {new Date(n.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                            </span>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* Balance & Role Info */}
              <div className="hidden sm:flex flex-col text-right pr-1">
                <span className="text-xs font-bold text-slate-200">
                  {profile?.full_name || user.email?.split('@')[0]}
                </span>
                <div className="flex items-center justify-end space-x-1 text-[11px]">
                  <span className={`px-1.5 py-0.2 rounded font-medium ${
                    profile?.role === 'Admin' ? 'bg-amber-900/60 text-amber-300' :
                    profile?.role === 'Writer' ? 'bg-cyan-900/60 text-cyan-300' :
                    'bg-indigo-900/60 text-indigo-300'
                  }`}>
                    {profile?.role || 'Member'}
                  </span>
                  <span className="text-emerald-400 font-mono font-semibold">
                    ${Number(profile?.available_balance || 0).toFixed(2)}
                  </span>
                </div>
              </div>

              {/* Logout */}
              <button
                onClick={logout}
                className="p-2 text-slate-400 hover:text-red-400 hover:bg-slate-800 rounded-lg transition"
                title="Sign Out"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          ) : (
            <div className="flex items-center space-x-2">
              <button
                onClick={() => onOpenAuth('login')}
                className="text-xs font-semibold text-slate-300 hover:text-white px-3 py-1.5 rounded-lg border border-slate-700 hover:border-slate-600 transition"
              >
                Sign In
              </button>
              <button
                onClick={() => onOpenAuth('register')}
                className="text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-500 px-3 py-1.5 rounded-lg shadow transition"
              >
                Register
              </button>
            </div>
          )}
        </div>

      </div>
    </header>
  );
}
