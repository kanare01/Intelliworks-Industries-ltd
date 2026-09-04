import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';
import { supabase } from '../services/supabase';
import {
  Briefcase,
  Clock,
  DollarSign,
  FileCheck,
  Send,
  MessageSquare,
  Upload,
  CheckCircle,
  AlertTriangle,
  ArrowUpRight,
  Share2,
  Copy,
  Check,
  Search,
  Filter,
  Layers,
  Award
} from 'lucide-react';

export function WriterDashboard({ initialSubTab = 'marketplace' }) {
  const { profile, refreshProfile } = useAuth();
  const [subTab, setSubTab] = useState(initialSubTab); // 'marketplace', 'workspace', 'earnings', 'referrals'
  
  // Marketplace & Workspace data
  const [openAssignments, setOpenAssignments] = useState([]);
  const [myAssignments, setMyAssignments] = useState([]);
  const [selectedAssignment, setSelectedAssignment] = useState(null);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('All');

  // Submit Deliverable Modal
  const [showSubmitModal, setShowSubmitModal] = useState(false);
  const [deliverableNotes, setDeliverableNotes] = useState('');
  const [deliverableFile, setDeliverableFile] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);

  // Withdrawal Modal
  const [showWithdrawalModal, setShowWithdrawalModal] = useState(false);
  const [withdrawalAmount, setWithdrawalAmount] = useState(25);
  const [payoutMethod, setPayoutMethod] = useState('Bank Wire Transfer');
  const [payoutDetails, setPayoutDetails] = useState('');
  const [withdrawalSuccess, setWithdrawalSuccess] = useState(false);

  // Referrals
  const [referralsData, setReferralsData] = useState(null);
  const [copiedRef, setCopiedRef] = useState(false);

  // Messaging
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');

  const fetchData = async () => {
    setLoading(true);
    try {
      const [openRes, myRes, refRes] = await Promise.all([
        api.listAssignments({ view: 'open' }),
        api.listAssignments({ view: 'mine' }),
        api.getReferrals().catch(() => ({ referrals: [], total_commission: 0 }))
      ]);
      setOpenAssignments(openRes.assignments || []);
      setMyAssignments(myRes.assignments || []);
      setReferralsData(refRes);

      if (selectedAssignment) {
        const updated = [...(openRes.assignments || []), ...(myRes.assignments || [])]
          .find(a => a.id === selectedAssignment.id);
        if (updated) setSelectedAssignment(updated);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  // Fetch messages on assignment selection
  useEffect(() => {
    if (selectedAssignment) {
      api.getMessages(selectedAssignment.id)
        .then(res => setMessages(res.messages || []))
        .catch(console.error);
    }
  }, [selectedAssignment]);

  const handleClaim = async (assignmentId) => {
    if (!confirm('Claim this assignment? You commit to delivering by the required deadline.')) return;
    setActionLoading(true);
    try {
      await api.claimAssignment(assignmentId);
      await fetchData();
      setSubTab('workspace');
    } catch (err) {
      alert(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleSubmitDeliverable = async (e) => {
    e.preventDefault();
    if (!deliverableNotes.trim()) return;
    setActionLoading(true);

    try {
      // 1. Submit to Flask
      await api.submitDeliverable(selectedAssignment.id, {
        deliverable_notes: deliverableNotes
      });

      // 2. Upload deliverable to Supabase storage if file present
      if (deliverableFile && supabase) {
        const filePath = `${selectedAssignment.id}/deliverables/${Date.now()}_${deliverableFile.name}`;
        await supabase.storage.from('assignment-files').upload(filePath, deliverableFile);
      }

      setShowSubmitModal(false);
      setDeliverableNotes('');
      setDeliverableFile(null);
      await fetchData();
      alert('Deliverable submitted successfully for client review!');
    } catch (err) {
      alert(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!newMessage.trim() || !selectedAssignment) return;
    try {
      const res = await api.sendMessage(selectedAssignment.id, newMessage);
      setMessages(prev => [...prev, res.message]);
      setNewMessage('');
    } catch (err) {
      alert(err.message);
    }
  };

  const handleRequestWithdrawal = async (e) => {
    e.preventDefault();
    if (withdrawalAmount < 20) {
      alert('Minimum withdrawal threshold is $20.00 USD.');
      return;
    }
    if (withdrawalAmount > (profile?.available_balance || 0)) {
      alert('Insufficient available funds.');
      return;
    }
    setActionLoading(true);
    try {
      await api.requestWithdrawal({
        amount: parseFloat(withdrawalAmount),
        payout_method: payoutMethod,
        payout_details: payoutDetails
      });
      setWithdrawalSuccess(true);
      await refreshProfile();
      setTimeout(() => {
        setWithdrawalSuccess(false);
        setShowWithdrawalModal(false);
      }, 1500);
    } catch (err) {
      alert(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const copyReferralCode = () => {
    if (profile?.referral_code) {
      navigator.clipboard.writeText(profile.referral_code);
      setCopiedRef(true);
      setTimeout(() => setCopiedRef(false), 2000);
    }
  };

  const filteredMarketplace = openAssignments.filter(a => {
    const matchesSearch = a.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
                          a.subject.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesCategory = selectedCategory === 'All' || a.category === selectedCategory;
    return matchesSearch && matchesCategory;
  });

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header & Subtabs */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-slate-800 pb-4 mb-6 gap-4">
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight">Specialist Writer Portal</h1>
          <p className="text-xs text-slate-400">Claim commissions, submit deliverables, and manage guaranteed earnings</p>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={() => { setSubTab('marketplace'); setSelectedAssignment(null); }}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
              subTab === 'marketplace' ? 'bg-cyan-600 text-white shadow' : 'text-slate-400 hover:text-white'
            }`}
          >
            Marketplace ({openAssignments.length})
          </button>
          <button
            onClick={() => { setSubTab('workspace'); setSelectedAssignment(null); }}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
              subTab === 'workspace' ? 'bg-slate-800 text-white' : 'text-slate-400 hover:text-white'
            }`}
          >
            My Workspace ({myAssignments.length})
          </button>
          <button
            onClick={() => setSubTab('earnings')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
              subTab === 'earnings' ? 'bg-slate-800 text-white' : 'text-slate-400 hover:text-white'
            }`}
          >
            Earnings (${Number(profile?.available_balance || 0).toFixed(2)})
          </button>
          <button
            onClick={() => setSubTab('referrals')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
              subTab === 'referrals' ? 'bg-slate-800 text-white' : 'text-slate-400 hover:text-white'
            }`}
          >
            Referrals
          </button>
        </div>
      </div>

      {/* 1. MARKETPLACE TAB */}
      {subTab === 'marketplace' && (
        <div>
          {/* Search & Category bar */}
          <div className="flex flex-col sm:flex-row gap-3 mb-6">
            <div className="relative flex-1">
              <Search className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search commissions by topic, subject, or methodology..."
                className="w-full bg-slate-900 border border-slate-700 rounded-lg pl-9 pr-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500"
              />
            </div>

            <div className="flex items-center space-x-2">
              <select
                value={selectedCategory}
                onChange={(e) => setSelectedCategory(e.target.value)}
                className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-cyan-500"
              >
                <option>All</option>
                <option>Research Assistance</option>
                <option>Literature Review</option>
                <option>Data Analysis & Code</option>
                <option>Editing & Proofreading</option>
                <option>LaTeX & BibTeX Typesetting</option>
              </select>
            </div>
          </div>

          {loading ? (
            <div className="p-12 text-center text-xs text-slate-500">Scanning marketplace assignments...</div>
          ) : filteredMarketplace.length === 0 ? (
            <div className="p-12 text-center bg-slate-900/60 border border-slate-800 rounded-2xl">
              <Briefcase className="w-10 h-10 text-slate-600 mx-auto mb-2" />
              <h3 className="text-sm font-semibold text-slate-300">No Open Assignments Available</h3>
              <p className="text-xs text-slate-500 mt-1">All commissioned projects have been claimed or none match your criteria.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredMarketplace.map(a => {
                const payout = (a.budget * 0.8).toFixed(2);
                return (
                  <div
                    key={a.id}
                    className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col justify-between hover:border-slate-700 transition"
                  >
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-cyan-950 text-cyan-300 border border-cyan-800/60">
                          {a.category}
                        </span>
                        <span className="text-xs font-mono font-bold text-emerald-400">
                          ${payout} Payout (80%)
                        </span>
                      </div>

                      <h3 className="text-sm font-bold text-white line-clamp-1">{a.title}</h3>
                      <p className="text-xs text-slate-400 mt-1 line-clamp-2">{a.description}</p>

                      <div className="mt-3 pt-3 border-t border-slate-800/60 space-y-1 text-[11px] text-slate-400">
                        <div className="flex justify-between">
                          <span>Subject:</span>
                          <span className="font-semibold text-slate-300">{a.subject}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Citation Style:</span>
                          <span className="font-semibold text-slate-300">{a.citation_style}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Academic Level:</span>
                          <span className="font-semibold text-slate-300">{a.academic_level}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Deadline:</span>
                          <span className="font-semibold text-amber-400">
                            {new Date(a.deadline).toLocaleDateString()}
                          </span>
                        </div>
                      </div>
                    </div>

                    <button
                      onClick={() => handleClaim(a.id)}
                      disabled={actionLoading}
                      className="mt-4 w-full py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-bold transition shadow disabled:opacity-50"
                    >
                      Claim Assignment (${payout})
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* 2. WORKSPACE TAB */}
      {subTab === 'workspace' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Active claimed projects */}
          <div className="lg:col-span-2 space-y-4">
            <h2 className="text-sm font-bold text-white uppercase tracking-wider">Active In-Progress Commissions</h2>
            
            {myAssignments.length === 0 ? (
              <div className="p-12 text-center bg-slate-900/60 border border-slate-800 rounded-2xl">
                <FileCheck className="w-10 h-10 text-slate-600 mx-auto mb-2" />
                <h3 className="text-sm font-semibold text-slate-300">No Active Projects</h3>
                <p className="text-xs text-slate-500 mt-1">Claim projects from the marketplace to begin working.</p>
                <button
                  onClick={() => setSubTab('marketplace')}
                  className="mt-4 px-4 py-2 rounded-lg bg-cyan-600 text-white text-xs font-bold"
                >
                  Browse Marketplace
                </button>
              </div>
            ) : (
              myAssignments.map(a => {
                const payout = (a.budget * 0.8).toFixed(2);
                return (
                  <div
                    key={a.id}
                    onClick={() => setSelectedAssignment(a)}
                    className={`p-4 rounded-xl border transition cursor-pointer ${
                      selectedAssignment?.id === a.id
                        ? 'bg-slate-850 border-cyan-500 shadow-lg'
                        : 'bg-slate-900 border-slate-800 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="flex items-center space-x-2">
                          <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full ${
                            a.status === 'Submitted' ? 'bg-purple-950 text-purple-300 border border-purple-800/60' :
                            a.status === 'Approved' ? 'bg-emerald-950 text-emerald-300 border border-emerald-800/60' :
                            'bg-cyan-950 text-cyan-300 border border-cyan-800/60'
                          }`}>
                            {a.status}
                          </span>
                          <span className="text-xs text-slate-400">{a.category}</span>
                        </div>
                        <h3 className="text-sm font-bold text-white mt-1">{a.title}</h3>
                      </div>
                      <div className="text-right">
                        <span className="text-base font-mono font-bold text-emerald-400">${payout}</span>
                        <span className="block text-[10px] text-slate-500">Guaranteed Escrow</span>
                      </div>
                    </div>

                    <div className="mt-3 pt-3 border-t border-slate-800/60 flex items-center justify-between text-[11px] text-slate-400">
                      <span className="flex items-center space-x-1">
                        <Clock className="w-3.5 h-3.5 text-slate-500" />
                        <span>Deadline: {new Date(a.deadline).toLocaleDateString()}</span>
                      </span>
                      <span>Revisions: {a.revision_count || 0}</span>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* Right: Workspace Dossier & Deliverable Action */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl">
            {selectedAssignment ? (
              <div className="space-y-4">
                <div>
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold text-cyan-400 uppercase tracking-wider">Workspace Commission</span>
                    <span className="text-xs font-mono text-emerald-400 font-semibold">
                      ${(selectedAssignment.budget * 0.8).toFixed(2)} Net
                    </span>
                  </div>
                  <h3 className="text-base font-bold text-white mt-1">{selectedAssignment.title}</h3>
                  <p className="text-xs text-slate-400 mt-1">{selectedAssignment.instructions}</p>
                </div>

                {/* Deliverable submission trigger */}
                {['Claimed', 'In Progress'].includes(selectedAssignment.status) && (
                  <button
                    onClick={() => setShowSubmitModal(true)}
                    className="w-full py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition shadow"
                  >
                    Submit Deliverable For Client Approval
                  </button>
                )}

                {selectedAssignment.status === 'Submitted' && (
                  <div className="p-3 bg-purple-950/40 border border-purple-800/60 rounded-xl text-center text-xs text-purple-200">
                    Deliverable is under client review. Escrow releases upon approval.
                  </div>
                )}

                {selectedAssignment.status === 'Approved' && (
                  <div className="p-3 bg-emerald-950/40 border border-emerald-800/60 rounded-xl text-center text-xs text-emerald-200 font-semibold">
                    Approved! 80% escrow payout has been credited to your available balance.
                  </div>
                )}

                {/* Discussion */}
                <div className="pt-3 border-t border-slate-800">
                  <h4 className="text-xs font-bold text-slate-300 mb-2 flex items-center space-x-1.5">
                    <MessageSquare className="w-3.5 h-3.5 text-cyan-400" />
                    <span>Client Communications</span>
                  </h4>

                  <div className="h-44 overflow-y-auto space-y-2 p-2 bg-slate-950 rounded-xl border border-slate-800 text-xs">
                    {messages.length === 0 ? (
                      <p className="text-slate-500 text-center py-6 text-[11px]">No messages yet with client.</p>
                    ) : (
                      messages.map(m => (
                        <div
                          key={m.id}
                          className={`p-2 rounded-lg max-w-[85%] ${
                            m.sender_id === profile?.id
                              ? 'bg-cyan-600/30 border border-cyan-500/40 text-slate-200 ml-auto'
                              : 'bg-slate-800/60 border border-slate-700 text-slate-300'
                          }`}
                        >
                          <div className="flex items-center justify-between text-[10px] text-slate-400 mb-1">
                            <span className="font-semibold">{m.sender_name}</span>
                            <span>{new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                          </div>
                          <p>{m.message}</p>
                        </div>
                      ))
                    )}
                  </div>

                  <form onSubmit={handleSendMessage} className="mt-2 flex space-x-1.5">
                    <input
                      type="text"
                      value={newMessage}
                      onChange={(e) => setNewMessage(e.target.value)}
                      placeholder="Message client..."
                      className="flex-1 bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500"
                    />
                    <button
                      type="submit"
                      className="px-3 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold"
                    >
                      <Send className="w-3.5 h-3.5" />
                    </button>
                  </form>
                </div>
              </div>
            ) : (
              <div className="p-8 text-center text-xs text-slate-500">
                Select an active assignment on the left to work on deliverables.
              </div>
            )}
          </div>
        </div>
      )}

      {/* 3. EARNINGS & WITHDRAWAL TAB */}
      {subTab === 'earnings' && (
        <div className="max-w-3xl mx-auto space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
              <span className="text-xs text-slate-400 block mb-1">Available for Payout</span>
              <span className="text-2xl font-mono font-bold text-emerald-400">
                ${Number(profile?.available_balance || 0).toFixed(2)}
              </span>
            </div>

            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
              <span className="text-xs text-slate-400 block mb-1">Escrow In Progress</span>
              <span className="text-2xl font-mono font-bold text-amber-400">
                ${Number(profile?.escrow_balance || 0).toFixed(2)}
              </span>
            </div>

            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
              <span className="text-xs text-slate-400 block mb-1">Total Lifetime Earned</span>
              <span className="text-2xl font-mono font-bold text-indigo-400">
                ${(Number(profile?.available_balance || 0) + 120.00).toFixed(2)}
              </span>
            </div>
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-bold text-white">Disbursement & Withdrawals</h3>
                <p className="text-xs text-slate-400">Request payouts to your verified banking or wire account</p>
              </div>
              <button
                onClick={() => setShowWithdrawalModal(true)}
                disabled={Number(profile?.available_balance || 0) < 20}
                className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-bold transition shadow"
              >
                Request Withdrawal ($20 Min)
              </button>
            </div>

            <div className="p-4 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-400 space-y-1">
              <p className="font-semibold text-slate-300">• Automated Escrow Accounting: 80% payout on client approval.</p>
              <p>• Payout frequency: Processed within 24-48 institutional business hours.</p>
              <p>• Minimum withdrawal threshold: $20.00 USD.</p>
            </div>
          </div>
        </div>
      )}

      {/* 4. REFERRALS TAB */}
      {subTab === 'referrals' && (
        <div className="max-w-3xl mx-auto space-y-6">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
            <div className="flex items-center space-x-3 mb-4">
              <div className="p-2.5 rounded-xl bg-indigo-950 text-indigo-400 border border-indigo-800">
                <Award className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-base font-bold text-white">Specialist Referral Program</h3>
                <p className="text-xs text-slate-400">Earn 5% commission on referee projects</p>
              </div>
            </div>

            <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 flex items-center justify-between mb-4">
              <div>
                <span className="text-[11px] text-slate-500 block uppercase tracking-wider font-semibold">Your Referral Code</span>
                <span className="font-mono text-base font-bold text-indigo-300">
                  {profile?.referral_code || 'IW-WRT-VERIFY'}
                </span>
              </div>
              <button
                onClick={copyReferralCode}
                className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold flex items-center space-x-1.5 transition"
              >
                {copiedRef ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                <span>{copiedRef ? 'Copied' : 'Copy Code'}</span>
              </button>
            </div>

            <div className="grid grid-cols-2 gap-4 text-xs">
              <div className="p-3 bg-slate-950 border border-slate-800 rounded-xl">
                <span className="text-slate-500 block">Total Referrals</span>
                <span className="text-lg font-bold text-white">{referralsData?.referrals?.length || 0}</span>
              </div>
              <div className="p-3 bg-slate-950 border border-slate-800 rounded-xl">
                <span className="text-slate-500 block">Commissions Earned</span>
                <span className="text-lg font-bold text-emerald-400 font-mono">
                  ${Number(referralsData?.total_commission || 0).toFixed(2)}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* SUBMIT DELIVERABLE MODAL */}
      {showSubmitModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl p-6 max-w-lg w-full">
            <h3 className="text-base font-bold text-white mb-1">Submit Deliverable for Review</h3>
            <p className="text-xs text-slate-400 mb-4">
              Include comprehensive research findings, data summaries, or manuscript files.
            </p>

            <form onSubmit={handleSubmitDeliverable} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Deliverable Notes & Methodology Summary</label>
                <textarea
                  rows={4}
                  required
                  value={deliverableNotes}
                  onChange={(e) => setDeliverableNotes(e.target.value)}
                  placeholder="Summarize the completed work, verified citations, data tables, and methodology..."
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg p-3 text-xs text-white focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div className="p-4 border border-dashed border-slate-700 rounded-xl text-center bg-slate-950/40">
                <Upload className="w-6 h-6 text-slate-400 mx-auto mb-1" />
                <span className="text-xs text-slate-300 block">Attach Final Deliverable Document / Archive</span>
                <input
                  type="file"
                  id="writer-deliverable-upload"
                  onChange={(e) => setDeliverableFile(e.target.files[0])}
                  className="mt-2 text-xs text-slate-400 file:mr-3 file:py-1 file:px-2.5 file:rounded-md file:border-0 file:text-xs file:bg-slate-800 file:text-slate-200"
                />
              </div>

              <div className="flex justify-end space-x-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowSubmitModal(false)}
                  className="px-4 py-2 rounded-lg bg-slate-800 text-slate-400 text-xs font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-4 py-2 rounded-lg bg-emerald-600 text-white text-xs font-bold hover:bg-emerald-500"
                >
                  {actionLoading ? 'Uploading...' : 'Transmit Deliverable'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* WITHDRAWAL MODAL */}
      {showWithdrawalModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl p-6 max-w-md w-full">
            <h3 className="text-base font-bold text-white mb-1">Request Funds Disbursement</h3>
            <p className="text-xs text-slate-400 mb-4">Minimum withdrawal threshold: $20.00 USD</p>

            {withdrawalSuccess ? (
              <div className="p-6 text-center space-y-2">
                <CheckCircle className="w-10 h-10 text-emerald-400 mx-auto" />
                <h4 className="text-sm font-bold text-white">Disbursement Queued!</h4>
                <p className="text-xs text-slate-400">Intelliworks Administration has received your withdrawal request.</p>
              </div>
            ) : (
              <form onSubmit={handleRequestWithdrawal} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">Withdrawal Amount ($USD)</label>
                  <input
                    type="number"
                    min={20}
                    max={profile?.available_balance || 0}
                    step={1}
                    required
                    value={withdrawalAmount}
                    onChange={(e) => setWithdrawalAmount(parseFloat(e.target.value) || 0)}
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2.5 text-sm font-mono text-white focus:outline-none focus:border-cyan-500"
                  />
                  <span className="text-[11px] text-slate-500 mt-1 block">
                    Available: ${Number(profile?.available_balance || 0).toFixed(2)}
                  </span>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">Disbursement Channel</label>
                  <select
                    value={payoutMethod}
                    onChange={(e) => setPayoutMethod(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2.5 text-xs text-white focus:outline-none focus:border-cyan-500"
                  >
                    <option>Bank Wire Transfer</option>
                    <option>Stripe Connect</option>
                    <option>PayPal</option>
                    <option>ACH Direct Deposit</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">Account / Routing Details</label>
                  <textarea
                    rows={3}
                    required
                    value={payoutDetails}
                    onChange={(e) => setPayoutDetails(e.target.value)}
                    placeholder="IBAN / Routing Number / Account Number / PayPal Email..."
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2.5 text-xs text-white focus:outline-none focus:border-cyan-500"
                  />
                </div>

                <div className="flex justify-end space-x-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setShowWithdrawalModal(false)}
                    className="px-4 py-2 rounded-lg bg-slate-800 text-slate-400 text-xs font-semibold"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={actionLoading}
                    className="px-4 py-2 rounded-lg bg-emerald-600 text-white text-xs font-bold hover:bg-emerald-500"
                  >
                    {actionLoading ? 'Processing...' : 'Submit Request'}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
