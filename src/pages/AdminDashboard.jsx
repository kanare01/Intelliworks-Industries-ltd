import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import {
  Shield,
  Activity,
  DollarSign,
  Users,
  AlertTriangle,
  FileCheck,
  CheckCircle,
  XCircle,
  Clock,
  Search,
  Settings,
  Lock,
  RefreshCw,
  Sliders,
  Check
} from 'lucide-react';

export function AdminDashboard() {
  const [activeTab, setActiveTab] = useState('metrics'); // 'metrics', 'users', 'disputes', 'withdrawals', 'audit', 'settings'
  
  // Data states
  const [metrics, setMetrics] = useState(null);
  const [users, setUsers] = useState([]);
  const [disputes, setDisputes] = useState([]);
  const [withdrawals, setWithdrawals] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);

  // Filter states
  const [userSearch, setUserSearch] = useState('');
  const [selectedDispute, setSelectedDispute] = useState(null);
  const [resolutionAction, setResolutionAction] = useState('Full Release to Writer');
  const [resolutionNotes, setResolutionNotes] = useState('');

  // Settings state
  const [writerPercentage, setWriterPercentage] = useState(80);
  const [platformPercentage, setPlatformPercentage] = useState(20);
  const [minWithdrawal, setMinWithdrawal] = useState(20);
  const [settingsSaved, setSettingsSaved] = useState(false);

  const fetchAdminData = async () => {
    setLoading(true);
    try {
      const [mRes, uRes, dRes, wRes, aRes] = await Promise.all([
        api.getAdminMetrics().catch(() => ({ metrics: {} })),
        api.getAdminUsers().catch(() => ({ users: [] })),
        api.listDisputes().catch(() => ({ disputes: [] })),
        api.getWithdrawals().catch(() => ({ withdrawals: [] })),
        api.getAuditLogs(50).catch(() => ({ audit_logs: [] }))
      ]);
      setMetrics(mRes.metrics || {});
      setUsers(uRes.users || []);
      setDisputes(dRes.disputes || []);
      setWithdrawals(wRes.withdrawals || []);
      setAuditLogs(aRes.audit_logs || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAdminData();
  }, []);

  const handleUpdateUserStatus = async (userId, newStatus) => {
    setActionLoading(true);
    try {
      await api.updateUserStatus(userId, newStatus);
      await fetchAdminData();
    } catch (err) {
      alert(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleResolveDispute = async (e) => {
    e.preventDefault();
    if (!selectedDispute) return;
    setActionLoading(true);
    try {
      await api.resolveDispute(selectedDispute.id, {
        resolution_action: resolutionAction,
        notes: resolutionNotes
      });
      setSelectedDispute(null);
      setResolutionNotes('');
      await fetchAdminData();
      alert(`Dispute resolved: ${resolutionAction}`);
    } catch (err) {
      alert(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleApproveWithdrawal = async (id) => {
    if (!confirm('Authorize disbursement for this withdrawal?')) return;
    setActionLoading(true);
    try {
      await api.approveWithdrawal(id);
      await fetchAdminData();
    } catch (err) {
      alert(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleRejectWithdrawal = async (id) => {
    const reason = prompt('Specify rejection reason (balance will be restored):', 'Incorrect bank credentials');
    if (!reason) return;
    setActionLoading(true);
    try {
      await api.rejectWithdrawal(id, { reason });
      await fetchAdminData();
    } catch (err) {
      alert(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleSaveSettings = async (e) => {
    e.preventDefault();
    setActionLoading(true);
    try {
      await Promise.all([
        api.updateSettings('escrow_split', { writer_percentage: writerPercentage, platform_fee_percentage: platformPercentage }),
        api.updateSettings('min_withdrawal', minWithdrawal)
      ]);
      setSettingsSaved(true);
      setTimeout(() => setSettingsSaved(false), 2000);
    } catch (err) {
      alert(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const filteredUsers = users.filter(u => 
    u.email.toLowerCase().includes(userSearch.toLowerCase()) ||
    (u.full_name && u.full_name.toLowerCase().includes(userSearch.toLowerCase()))
  );

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-slate-800 pb-4 mb-6 gap-4">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 rounded-xl bg-amber-950/60 border border-amber-700/60 text-amber-400">
            <Shield className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white tracking-tight">Executive Command Center</h1>
            <p className="text-xs text-slate-400">Platform telemetry, escrow settlement, dispute arbitration & audit trails</p>
          </div>
        </div>

        {/* Tab switcher */}
        <div className="flex items-center space-x-1.5 overflow-x-auto text-xs font-semibold">
          {[
            { id: 'metrics', label: 'Financial Metrics' },
            { id: 'disputes', label: `Arbitration (${disputes.length})` },
            { id: 'withdrawals', label: `Payouts (${withdrawals.filter(w => w.status === 'Pending').length})` },
            { id: 'users', label: `Users (${users.length})` },
            { id: 'audit', label: 'Audit Trail' },
            { id: 'settings', label: 'Parameters' }
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-3 py-1.5 rounded-lg transition whitespace-nowrap ${
                activeTab === tab.id
                  ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* 1. METRICS TAB */}
      {activeTab === 'metrics' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
              <span className="text-xs text-slate-400 block mb-1">Gross Merchandise Value</span>
              <span className="text-2xl font-mono font-bold text-white">
                ${Number(metrics?.gmv || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </span>
              <span className="text-[10px] text-slate-500 block mt-1">Total escrow processed</span>
            </div>

            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
              <span className="text-xs text-slate-400 block mb-1">Platform Revenue (20%)</span>
              <span className="text-2xl font-mono font-bold text-emerald-400">
                ${Number(metrics?.platform_revenue || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </span>
              <span className="text-[10px] text-slate-500 block mt-1">Retained fee margin</span>
            </div>

            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
              <span className="text-xs text-slate-400 block mb-1">Escrow Currently Locked</span>
              <span className="text-2xl font-mono font-bold text-cyan-400">
                ${Number(metrics?.escrow_locked || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </span>
              <span className="text-[10px] text-slate-500 block mt-1">In active progress</span>
            </div>

            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
              <span className="text-xs text-slate-400 block mb-1">Pending Disbursements</span>
              <span className="text-2xl font-mono font-bold text-amber-400">
                ${Number(metrics?.pending_withdrawals_amount || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </span>
              <span className="text-[10px] text-slate-500 block mt-1">Awaiting bank wire approval</span>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="p-4 bg-slate-900/60 border border-slate-800 rounded-xl">
              <span className="text-xs text-slate-400">Total Registered Members</span>
              <div className="text-xl font-bold text-white mt-1">{metrics?.users_count || 0}</div>
            </div>
            <div className="p-4 bg-slate-900/60 border border-slate-800 rounded-xl">
              <span className="text-xs text-slate-400">Active Commissions</span>
              <div className="text-xl font-bold text-white mt-1">{metrics?.active_assignments || 0}</div>
            </div>
            <div className="p-4 bg-slate-900/60 border border-slate-800 rounded-xl">
              <span className="text-xs text-slate-400">Pending Disputes</span>
              <div className="text-xl font-bold text-amber-400 mt-1">{metrics?.disputes_count || 0}</div>
            </div>
          </div>
        </div>
      )}

      {/* 2. DISPUTE ARBITRATION TAB */}
      {activeTab === 'disputes' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-4">
            <h2 className="text-sm font-bold text-white uppercase tracking-wider">Active Contractual Disputes</h2>
            {disputes.length === 0 ? (
              <div className="p-12 text-center bg-slate-900/60 border border-slate-800 rounded-2xl text-xs text-slate-500">
                No active disputes. Escrow workflow is performing nominally.
              </div>
            ) : (
              disputes.map(d => (
                <div
                  key={d.id}
                  onClick={() => setSelectedDispute(d)}
                  className={`p-4 rounded-xl border transition cursor-pointer ${
                    selectedDispute?.id === d.id
                      ? 'bg-slate-850 border-amber-500 shadow'
                      : 'bg-slate-900 border-slate-800 hover:border-slate-700'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-red-950 text-red-300 border border-red-800/60">
                      Dispute #{d.id.slice(0, 8)}
                    </span>
                    <span className="text-xs font-mono font-bold text-white">${d.budget} Escrow</span>
                  </div>
                  <h3 className="text-sm font-bold text-white mt-2">{d.assignment_title}</h3>
                  <p className="text-xs text-slate-400 mt-1 line-clamp-2">"{d.reason}"</p>
                </div>
              ))
            )}
          </div>

          {/* Arbitration action drawer */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl">
            {selectedDispute ? (
              <form onSubmit={handleResolveDispute} className="space-y-4">
                <div>
                  <span className="text-[10px] font-bold text-amber-400 uppercase tracking-wider">Arbitration Dossier</span>
                  <h3 className="text-sm font-bold text-white mt-1">{selectedDispute.assignment_title}</h3>
                  <p className="text-xs text-slate-300 bg-slate-950 p-2.5 rounded-lg border border-slate-800 mt-2">
                    Dispute Reason: "{selectedDispute.reason}"
                  </p>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">Arbitration Settlement Action</label>
                  <select
                    value={resolutionAction}
                    onChange={(e) => setResolutionAction(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2.5 text-xs text-white focus:outline-none focus:border-amber-500"
                  >
                    <option>Full Release to Writer</option>
                    <option>Full Refund to Client</option>
                    <option>50/50 Settlement</option>
                    <option>Dismiss Dispute</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">Administrative Finding & Judgment</label>
                  <textarea
                    rows={4}
                    required
                    value={resolutionNotes}
                    onChange={(e) => setResolutionNotes(e.target.value)}
                    placeholder="Document institutional reasoning, evidence review, and resolution terms..."
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2.5 text-xs text-white focus:outline-none focus:border-amber-500"
                  />
                </div>

                <button
                  type="submit"
                  disabled={actionLoading}
                  className="w-full py-2.5 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-xs font-bold transition shadow"
                >
                  {actionLoading ? 'Executing Ruling...' : 'Enact Final Arbitration Ruling'}
                </button>
              </form>
            ) : (
              <div className="p-8 text-center text-xs text-slate-500">
                Select an escalated dispute on the left to arbitrate.
              </div>
            )}
          </div>
        </div>
      )}

      {/* 3. WITHDRAWALS APPROVAL TAB */}
      {activeTab === 'withdrawals' && (
        <div className="space-y-4">
          <h2 className="text-sm font-bold text-white uppercase tracking-wider">Disbursement Queue</h2>
          {withdrawals.length === 0 ? (
            <div className="p-12 text-center bg-slate-900/60 border border-slate-800 rounded-2xl text-xs text-slate-500">
              No withdrawal disbursements in queue.
            </div>
          ) : (
            <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
              <table className="w-full text-left text-xs text-slate-300">
                <thead className="bg-slate-950 text-slate-400 font-semibold border-b border-slate-800">
                  <tr>
                    <th className="p-3">User / Specialist</th>
                    <th className="p-3">Amount</th>
                    <th className="p-3">Method</th>
                    <th className="p-3">Details</th>
                    <th className="p-3">Status</th>
                    <th className="p-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {withdrawals.map(w => (
                    <tr key={w.id} className="hover:bg-slate-850">
                      <td className="p-3 font-medium text-white">{w.full_name || w.email}</td>
                      <td className="p-3 font-mono font-bold text-emerald-400">${Number(w.amount).toFixed(2)}</td>
                      <td className="p-3">{w.payout_method}</td>
                      <td className="p-3 font-mono text-[11px] text-slate-400 max-w-xs truncate">{w.payout_details}</td>
                      <td className="p-3">
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${
                          w.status === 'Approved' ? 'bg-emerald-950 text-emerald-300' :
                          w.status === 'Rejected' ? 'bg-red-950 text-red-300' :
                          'bg-amber-950 text-amber-300'
                        }`}>
                          {w.status}
                        </span>
                      </td>
                      <td className="p-3 text-right space-x-2">
                        {w.status === 'Pending' && (
                          <>
                            <button
                              onClick={() => handleApproveWithdrawal(w.id)}
                              className="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-500 text-white rounded font-bold text-[11px]"
                            >
                              Approve
                            </button>
                            <button
                              onClick={() => handleRejectWithdrawal(w.id)}
                              className="px-2.5 py-1 bg-red-600 hover:bg-red-500 text-white rounded font-bold text-[11px]"
                            >
                              Reject
                            </button>
                          </>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* 4. USER MANAGEMENT TAB */}
      {activeTab === 'users' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-white uppercase tracking-wider">Registered Marketplace Accounts</h2>
            <div className="relative w-64">
              <Search className="w-4 h-4 text-slate-500 absolute left-3 top-2" />
              <input
                type="text"
                value={userSearch}
                onChange={(e) => setUserSearch(e.target.value)}
                placeholder="Search accounts..."
                className="w-full bg-slate-950 border border-slate-700 rounded-lg pl-9 pr-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-amber-500"
              />
            </div>
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="bg-slate-950 text-slate-400 font-semibold border-b border-slate-800">
                <tr>
                  <th className="p-3">User</th>
                  <th className="p-3">Role</th>
                  <th className="p-3">Available Balance</th>
                  <th className="p-3">Escrow Balance</th>
                  <th className="p-3">Status</th>
                  <th className="p-3 text-right">Status Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {filteredUsers.map(u => (
                  <tr key={u.id} className="hover:bg-slate-850">
                    <td className="p-3">
                      <div className="font-semibold text-white">{u.full_name || 'Anonymous User'}</div>
                      <div className="text-[11px] text-slate-500">{u.email}</div>
                    </td>
                    <td className="p-3">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                        u.role === 'Admin' ? 'bg-amber-900/60 text-amber-300' :
                        u.role === 'Writer' ? 'bg-cyan-900/60 text-cyan-300' :
                        'bg-indigo-900/60 text-indigo-300'
                      }`}>
                        {u.role}
                      </span>
                    </td>
                    <td className="p-3 font-mono text-emerald-400 font-semibold">${Number(u.available_balance || 0).toFixed(2)}</td>
                    <td className="p-3 font-mono text-amber-400 font-semibold">${Number(u.escrow_balance || 0).toFixed(2)}</td>
                    <td className="p-3">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${
                        u.account_status === 'Active' ? 'bg-emerald-950 text-emerald-300' : 'bg-red-950 text-red-300'
                      }`}>
                        {u.account_status}
                      </span>
                    </td>
                    <td className="p-3 text-right">
                      {u.account_status === 'Active' ? (
                        <button
                          onClick={() => handleUpdateUserStatus(u.id, 'Suspended')}
                          className="px-2.5 py-1 rounded bg-red-950 hover:bg-red-900/80 text-red-300 border border-red-800 text-[11px] font-semibold"
                        >
                          Suspend
                        </button>
                      ) : (
                        <button
                          onClick={() => handleUpdateUserStatus(u.id, 'Active')}
                          className="px-2.5 py-1 rounded bg-emerald-950 hover:bg-emerald-900/80 text-emerald-300 border border-emerald-800 text-[11px] font-semibold"
                        >
                          Reactivate
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 5. AUDIT TRAIL TAB */}
      {activeTab === 'audit' && (
        <div className="space-y-4">
          <h2 className="text-sm font-bold text-white uppercase tracking-wider">Institutional Audit Trail</h2>
          <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="bg-slate-950 text-slate-400 font-semibold border-b border-slate-800">
                <tr>
                  <th className="p-3">Timestamp</th>
                  <th className="p-3">Action</th>
                  <th className="p-3">Actor</th>
                  <th className="p-3">Route</th>
                  <th className="p-3">IP Address</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {auditLogs.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="p-6 text-center text-slate-500">No audit logs recorded yet.</td>
                  </tr>
                ) : (
                  auditLogs.map(l => (
                    <tr key={l.id} className="hover:bg-slate-850 font-mono text-[11px]">
                      <td className="p-3 text-slate-400">{new Date(l.created_at).toLocaleString()}</td>
                      <td className="p-3 font-semibold text-white">{l.action}</td>
                      <td className="p-3 text-cyan-300">{l.user_email || 'System'}</td>
                      <td className="p-3 text-slate-400">{l.route}</td>
                      <td className="p-3 text-slate-500">{l.ip_address}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 6. SETTINGS TAB */}
      {activeTab === 'settings' && (
        <div className="max-w-2xl mx-auto bg-slate-900 border border-slate-800 rounded-2xl p-6">
          <h2 className="text-sm font-bold text-white uppercase tracking-wider mb-4">Platform Operational Parameters</h2>

          {settingsSaved && (
            <div className="p-3 mb-4 rounded-xl bg-emerald-950 border border-emerald-800 text-emerald-300 text-xs flex items-center space-x-2">
              <Check className="w-4 h-4 text-emerald-400" />
              <span>Operational parameters updated successfully!</span>
            </div>
          )}

          <form onSubmit={handleSaveSettings} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Writer Payout Ratio (%)</label>
                <input
                  type="number"
                  min={50}
                  max={95}
                  value={writerPercentage}
                  onChange={(e) => {
                    const val = parseFloat(e.target.value) || 0;
                    setWriterPercentage(val);
                    setPlatformPercentage(100 - val);
                  }}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2.5 text-xs text-white"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Platform Margin Ratio (%)</label>
                <input
                  type="number"
                  disabled
                  value={platformPercentage}
                  className="w-full bg-slate-950/50 border border-slate-800 rounded-lg p-2.5 text-xs text-slate-400"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Minimum Withdrawal Floor ($USD)</label>
              <input
                type="number"
                min={5}
                step={5}
                value={minWithdrawal}
                onChange={(e) => setMinWithdrawal(parseFloat(e.target.value) || 0)}
                className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2.5 text-xs text-white"
              />
            </div>

            <button
              type="submit"
              disabled={actionLoading}
              className="w-full py-2.5 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-xs font-bold transition shadow"
            >
              {actionLoading ? 'Updating Parameters...' : 'Save Parameters'}
            </button>
          </form>
        </div>
      )}
    </div>
  );
}
