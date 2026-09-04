import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';
import { supabase } from '../services/supabase';
import {
  FolderPlus,
  Clock,
  DollarSign,
  FileCheck,
  AlertTriangle,
  Send,
  MessageSquare,
  ChevronRight,
  Upload,
  CheckCircle,
  X,
  Star,
  RefreshCw,
  Eye,
  Paperclip,
  Check,
  ShieldCheck,
  Calendar,
  Layers
} from 'lucide-react';

export function ClientDashboard({ initialSubTab = 'overview', onSwitchToCreate }) {
  const { profile, refreshProfile } = useAuth();
  const [subTab, setSubTab] = useState(initialSubTab);
  const [assignments, setAssignments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedAssignment, setSelectedAssignment] = useState(null);
  const [statusFilter, setStatusFilter] = useState('All');

  // Modals
  const [showRevisionModal, setShowRevisionModal] = useState(false);
  const [showDisputeModal, setShowDisputeModal] = useState(false);
  const [showReviewModal, setShowReviewModal] = useState(false);
  const [revisionNotes, setRevisionNotes] = useState('');
  const [disputeReason, setDisputeReason] = useState('');
  const [reviewRating, setReviewRating] = useState(5);
  const [reviewComment, setReviewComment] = useState('');
  const [actionLoading, setActionLoading] = useState(false);

  // Messaging drawer
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');
  const [messagingLoading, setMessagingLoading] = useState(false);

  // New project creation state (4 steps)
  const [step, setStep] = useState(1);
  const [formData, setFormData] = useState({
    title: '',
    category: 'Research Assistance',
    subject: 'Computer Science',
    academic_level: 'Undergraduate',
    description: '',
    instructions: '',
    word_count: 2000,
    citation_style: 'IEEE',
    deadline: '',
    budget: 150,
    academic_integrity_declaration: false,
  });
  const [uploadFile, setUploadFile] = useState(null);
  const [createError, setCreateError] = useState('');
  const [createSuccess, setCreateSuccess] = useState(false);

  const fetchAssignments = async () => {
    setLoading(true);
    try {
      const res = await api.listAssignments({ view: 'mine' });
      setAssignments(res.assignments || []);
      if (selectedAssignment) {
        const updated = (res.assignments || []).find(a => a.id === selectedAssignment.id);
        if (updated) setSelectedAssignment(updated);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAssignments();
  }, []);

  // Fetch messages when assignment is selected
  useEffect(() => {
    if (selectedAssignment) {
      api.getMessages(selectedAssignment.id)
        .then(res => setMessages(res.messages || []))
        .catch(console.error);
    }
  }, [selectedAssignment]);

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!newMessage.trim() || !selectedAssignment) return;
    setMessagingLoading(true);
    try {
      const res = await api.sendMessage(selectedAssignment.id, newMessage);
      setMessages(prev => [...prev, res.message]);
      setNewMessage('');
    } catch (err) {
      alert(err.message);
    } finally {
      setMessagingLoading(false);
    }
  };

  const handleApprove = async () => {
    if (!confirm('Approve this deliverable and release the 80% writer escrow payout?')) return;
    setActionLoading(true);
    try {
      await api.approveAssignment(selectedAssignment.id);
      await fetchAssignments();
      setShowReviewModal(true);
      await refreshProfile();
    } catch (err) {
      alert(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleRequestRevision = async (e) => {
    e.preventDefault();
    if (!revisionNotes.trim()) return;
    setActionLoading(true);
    try {
      await api.requestRevision(selectedAssignment.id, { revision_notes: revisionNotes });
      setShowRevisionModal(false);
      setRevisionNotes('');
      await fetchAssignments();
    } catch (err) {
      alert(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleOpenDispute = async (e) => {
    e.preventDefault();
    if (!disputeReason.trim()) return;
    setActionLoading(true);
    try {
      await api.openDispute(selectedAssignment.id, { reason: disputeReason });
      setShowDisputeModal(false);
      setDisputeReason('');
      await fetchAssignments();
    } catch (err) {
      alert(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleSubmitReview = async (e) => {
    e.preventDefault();
    setActionLoading(true);
    try {
      await api.submitReview({
        assignment_id: selectedAssignment.id,
        rating: reviewRating,
        comment: reviewComment
      });
      setShowReviewModal(false);
      setReviewComment('');
      await fetchAssignments();
    } catch (err) {
      alert(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  // Creation submission
  const handleCreateAssignment = async (e) => {
    e.preventDefault();
    setCreateError('');
    setActionLoading(true);

    try {
      if (!formData.deadline) {
        throw new Error('Please specify a target delivery deadline.');
      }
      if (!formData.academic_integrity_declaration) {
        throw new Error('You must accept the Academic Integrity Declaration.');
      }

      // 1. Create assignment record in Flask
      const res = await api.createAssignment(formData);
      const assignmentId = res.assignment.id;

      // 2. Upload reference file to Supabase storage if provided
      if (uploadFile && supabase) {
        const fileExt = uploadFile.name.split('.').pop();
        const filePath = `${assignmentId}/references/${Date.now()}_${uploadFile.name}`;
        
        const { error: uploadError } = await supabase.storage
          .from('assignment-files')
          .upload(filePath, uploadFile);

        if (uploadError) {
          console.warn('Storage upload error:', uploadError.message);
        }
      }

      setCreateSuccess(true);
      await fetchAssignments();
      await refreshProfile();
      setTimeout(() => {
        setCreateSuccess(false);
        setStep(1);
        setSubTab('overview');
      }, 1500);
    } catch (err) {
      setCreateError(err.message || 'Failed to initialize project escrow.');
    } finally {
      setActionLoading(false);
    }
  };

  const writerPayout = (Number(formData.budget || 0) * 0.8).toFixed(2);
  const platformFee = (Number(formData.budget || 0) * 0.2).toFixed(2);

  const filteredAssignments = assignments.filter(a => {
    if (statusFilter === 'All') return true;
    return a.status === statusFilter;
  });

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Subnav */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-4 mb-6">
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight">Client Project Management</h1>
          <p className="text-xs text-slate-400">Escrow-backed academic & professional project commissions</p>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={() => setSubTab('overview')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
              subTab === 'overview' ? 'bg-slate-800 text-white' : 'text-slate-400 hover:text-white'
            }`}
          >
            My Projects ({assignments.length})
          </button>
          <button
            onClick={() => setSubTab('create')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
              subTab === 'create' ? 'bg-indigo-600 text-white shadow' : 'bg-slate-800/80 text-indigo-300 hover:bg-indigo-900/40'
            }`}
          >
            + Commission New Project
          </button>
        </div>
      </div>

      {subTab === 'create' ? (
        /* CREATE NEW PROJECT WIZARD */
        <div className="max-w-3xl mx-auto bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl">
          {/* Progress bar */}
          <div className="flex items-center justify-between mb-6 border-b border-slate-800 pb-4">
            {[1, 2, 3, 4].map(s => (
              <div key={s} className="flex items-center space-x-2">
                <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${
                  step === s 
                    ? 'bg-indigo-600 text-white' 
                    : step > s 
                    ? 'bg-emerald-600 text-white' 
                    : 'bg-slate-800 text-slate-500'
                }`}>
                  {step > s ? '✓' : s}
                </div>
                <span className={`text-xs font-medium hidden sm:inline ${step === s ? 'text-white' : 'text-slate-500'}`}>
                  {s === 1 ? 'Scope' : s === 2 ? 'Specifications' : s === 3 ? 'Materials' : 'Escrow Deposit'}
                </span>
              </div>
            ))}
          </div>

          {createSuccess ? (
            <div className="p-8 text-center space-y-3">
              <div className="w-12 h-12 rounded-full bg-emerald-950 border border-emerald-700 text-emerald-400 flex items-center justify-center mx-auto">
                <Check className="w-6 h-6" />
              </div>
              <h3 className="text-base font-bold text-white">Project Commissioned & Escrow Funded!</h3>
              <p className="text-xs text-slate-400">
                Your project is now open in the specialist marketplace. Writers will review requirements and claim it shortly.
              </p>
            </div>
          ) : (
            <form onSubmit={step === 4 ? handleCreateAssignment : (e) => { e.preventDefault(); setStep(step + 1); }}>
              {createError && (
                <div className="p-3 mb-4 rounded-xl bg-red-950/50 border border-red-800 text-red-200 text-xs">
                  {createError}
                </div>
              )}

              {/* STEP 1: SCOPE */}
              {step === 1 && (
                <div className="space-y-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1">Project Title</label>
                    <input
                      type="text"
                      required
                      value={formData.title}
                      onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                      placeholder="e.g. Comparative Analysis of High-Throughput RNA-Seq Pipelines"
                      className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                    />
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div>
                      <label className="block text-xs font-semibold text-slate-300 mb-1">Category</label>
                      <select
                        value={formData.category}
                        onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                        className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
                      >
                        <option>Research Assistance</option>
                        <option>Literature Review</option>
                        <option>Data Analysis & Code</option>
                        <option>Editing & Proofreading</option>
                        <option>LaTeX & BibTeX Typesetting</option>
                        <option>Curriculum Consultation</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-xs font-semibold text-slate-300 mb-1">Subject Discipline</label>
                      <input
                        type="text"
                        required
                        value={formData.subject}
                        onChange={(e) => setFormData({ ...formData, subject: e.target.value })}
                        placeholder="e.g. Bioinformatics, Economics"
                        className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-semibold text-slate-300 mb-1">Academic Level</label>
                      <select
                        value={formData.academic_level}
                        onChange={(e) => setFormData({ ...formData, academic_level: e.target.value })}
                        className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
                      >
                        <option>Undergraduate</option>
                        <option>Master's</option>
                        <option>Doctoral / PhD</option>
                        <option>Professional / Faculty</option>
                      </select>
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1">Executive Summary / Scope</label>
                    <textarea
                      required
                      rows={3}
                      value={formData.description}
                      onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                      placeholder="Outline the core research objectives and intended outcomes..."
                      className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                    />
                  </div>
                </div>
              )}

              {/* STEP 2: SPECIFICATIONS */}
              {step === 2 && (
                <div className="space-y-4">
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div>
                      <label className="block text-xs font-semibold text-slate-300 mb-1">Estimated Word / Page Count</label>
                      <input
                        type="number"
                        min={100}
                        value={formData.word_count}
                        onChange={(e) => setFormData({ ...formData, word_count: parseInt(e.target.value) || 0 })}
                        className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-semibold text-slate-300 mb-1">Citation Format</label>
                      <select
                        value={formData.citation_style}
                        onChange={(e) => setFormData({ ...formData, citation_style: e.target.value })}
                        className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
                      >
                        <option>IEEE</option>
                        <option>APA 7th</option>
                        <option>Chicago / Turabian</option>
                        <option>Harvard</option>
                        <option>MLA 9th</option>
                        <option>ACM</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-xs font-semibold text-slate-300 mb-1">Target Delivery Deadline</label>
                      <input
                        type="datetime-local"
                        required
                        value={formData.deadline}
                        onChange={(e) => setFormData({ ...formData, deadline: e.target.value })}
                        className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
                      >
                      </input>
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1">Detailed Specialist Instructions</label>
                    <textarea
                      required
                      rows={5}
                      value={formData.instructions}
                      onChange={(e) => setFormData({ ...formData, instructions: e.target.value })}
                      placeholder="Provide detailed formatting, analytical methods, datasets, or literature guidelines..."
                      className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                    />
                  </div>
                </div>
              )}

              {/* STEP 3: MATERIALS */}
              {step === 3 && (
                <div className="space-y-4">
                  <div className="p-6 border-2 border-dashed border-slate-700 rounded-xl bg-slate-950/40 text-center">
                    <Upload className="w-8 h-8 text-slate-400 mx-auto mb-2" />
                    <p className="text-xs font-semibold text-white">Upload Research Datasets or Rubric Files</p>
                    <p className="text-[11px] text-slate-500 mt-1">PDF, DOCX, ZIP, CSV, LaTeX up to 50MB</p>
                    <input
                      type="file"
                      id="project-file-upload"
                      onChange={(e) => setUploadFile(e.target.files[0])}
                      className="mt-4 text-xs text-slate-400 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-slate-800 file:text-slate-200 hover:file:bg-slate-700"
                    />
                    {uploadFile && (
                      <p className="text-xs text-emerald-400 mt-2 font-mono">Selected: {uploadFile.name}</p>
                    )}
                  </div>
                </div>
              )}

              {/* STEP 4: ESCROW DEPOSIT & INTEGRITY DECLARATION */}
              {step === 4 && (
                <div className="space-y-4">
                  <div className="bg-slate-950 border border-slate-800 rounded-xl p-4">
                    <label className="block text-xs font-semibold text-slate-300 mb-1">Total Project Budget ($USD)</label>
                    <div className="relative">
                      <DollarSign className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
                      <input
                        type="number"
                        min={10}
                        step={5}
                        required
                        value={formData.budget}
                        onChange={(e) => setFormData({ ...formData, budget: parseFloat(e.target.value) || 0 })}
                        className="w-full bg-slate-900 border border-slate-700 rounded-lg pl-9 pr-3 py-2 text-sm font-mono text-white focus:outline-none focus:border-indigo-500"
                      />
                    </div>

                    {/* 80/20 Escrow Math Breakdown */}
                    <div className="mt-4 pt-3 border-t border-slate-800 grid grid-cols-2 gap-3 text-xs">
                      <div className="p-2.5 rounded-lg bg-indigo-950/30 border border-indigo-800/40">
                        <span className="text-slate-400 block text-[11px]">Specialist Writer Payout (80%)</span>
                        <span className="text-indigo-300 font-mono font-bold text-sm">${writerPayout}</span>
                      </div>
                      <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800">
                        <span className="text-slate-400 block text-[11px]">Platform Assurance & Escrow (20%)</span>
                        <span className="text-slate-300 font-mono font-bold text-sm">${platformFee}</span>
                      </div>
                    </div>
                  </div>

                  {/* Academic Integrity Declaration */}
                  <div className="p-4 rounded-xl bg-cyan-950/20 border border-cyan-800/40">
                    <label className="flex items-start space-x-2.5 cursor-pointer">
                      <input
                        type="checkbox"
                        required
                        checked={formData.academic_integrity_declaration}
                        onChange={(e) => setFormData({ ...formData, academic_integrity_declaration: e.target.checked })}
                        className="mt-0.5 rounded border-slate-700 text-indigo-600 focus:ring-indigo-500"
                      />
                      <span className="text-xs text-slate-300 leading-relaxed">
                        <span className="font-bold text-cyan-300">Academic Integrity Binding Commitment:</span> I verify that this commission is for legitimate research assistance, editing, tutoring, or analytical support. I will not submit deliverables directly as uncredited academic coursework.
                      </span>
                    </label>
                  </div>
                </div>
              )}

              {/* Navigation buttons */}
              <div className="mt-6 flex items-center justify-between border-t border-slate-800 pt-4">
                {step > 1 ? (
                  <button
                    type="button"
                    onClick={() => setStep(step - 1)}
                    className="px-4 py-2 rounded-lg bg-slate-800 text-slate-300 text-xs font-semibold hover:bg-slate-700 transition"
                  >
                    Back
                  </button>
                ) : <div />}

                {step < 4 ? (
                  <button
                    type="button"
                    onClick={() => setStep(step + 1)}
                    className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-xs font-semibold hover:bg-indigo-500 transition"
                  >
                    Continue to {step === 1 ? 'Specifications' : step === 2 ? 'Materials' : 'Escrow Deposit'}
                  </button>
                ) : (
                  <button
                    type="submit"
                    disabled={actionLoading}
                    className="px-5 py-2.5 rounded-lg bg-indigo-600 text-white text-xs font-bold hover:bg-indigo-500 shadow-lg transition disabled:opacity-50"
                  >
                    {actionLoading ? 'Initializing Escrow...' : `Fund Escrow ($${formData.budget}) & Commission`}
                  </button>
                )}
              </div>
            </form>
          )}
        </div>
      ) : (
        /* PROJECTS LIST & DETAIL DRAWER */
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left: Projects list */}
          <div className="lg:col-span-2 space-y-4">
            {/* Filter */}
            <div className="flex items-center space-x-2 overflow-x-auto pb-1 text-xs">
              {['All', 'Open', 'Claimed', 'In Progress', 'Submitted', 'Approved', 'Disputed'].map(status => (
                <button
                  key={status}
                  onClick={() => setStatusFilter(status)}
                  className={`px-3 py-1 rounded-full border transition whitespace-nowrap ${
                    statusFilter === status 
                      ? 'bg-indigo-600 border-indigo-500 text-white font-semibold' 
                      : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-white'
                  }`}
                >
                  {status}
                </button>
              ))}
            </div>

            {loading ? (
              <div className="p-8 text-center text-xs text-slate-500">Loading assignments...</div>
            ) : filteredAssignments.length === 0 ? (
              <div className="p-12 text-center bg-slate-900/60 border border-slate-800 rounded-2xl">
                <FileCheck className="w-10 h-10 text-slate-600 mx-auto mb-2" />
                <h3 className="text-sm font-semibold text-slate-300">No Projects Found</h3>
                <p className="text-xs text-slate-500 mt-1">You haven't commissioned any projects matching this filter.</p>
                <button
                  onClick={() => setSubTab('create')}
                  className="mt-4 px-4 py-2 rounded-lg bg-indigo-600 text-white text-xs font-bold hover:bg-indigo-500 transition"
                >
                  Commission a Project Now
                </button>
              </div>
            ) : (
              filteredAssignments.map(a => (
                <div
                  key={a.id}
                  onClick={() => setSelectedAssignment(a)}
                  className={`p-4 rounded-xl border transition cursor-pointer ${
                    selectedAssignment?.id === a.id
                      ? 'bg-slate-850 border-indigo-500 shadow-lg'
                      : 'bg-slate-900/80 border-slate-800 hover:border-slate-700'
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center space-x-2">
                        <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full ${
                          a.status === 'Open' ? 'bg-amber-950 text-amber-300 border border-amber-800/60' :
                          a.status === 'Claimed' || a.status === 'In Progress' ? 'bg-cyan-950 text-cyan-300 border border-cyan-800/60' :
                          a.status === 'Submitted' ? 'bg-purple-950 text-purple-300 border border-purple-800/60' :
                          a.status === 'Approved' ? 'bg-emerald-950 text-emerald-300 border border-emerald-800/60' :
                          'bg-red-950 text-red-300 border border-red-800/60'
                        }`}>
                          {a.status}
                        </span>
                        <span className="text-xs text-slate-400">{a.category}</span>
                      </div>
                      <h3 className="text-sm font-bold text-white mt-1.5">{a.title}</h3>
                    </div>

                    <div className="text-right">
                      <span className="text-base font-mono font-bold text-white">${a.budget}</span>
                      <span className="block text-[10px] text-slate-500">Escrow Locked</span>
                    </div>
                  </div>

                  <div className="mt-3 pt-3 border-t border-slate-800/60 flex items-center justify-between text-[11px] text-slate-400">
                    <span className="flex items-center space-x-1">
                      <Clock className="w-3.5 h-3.5 text-slate-500" />
                      <span>Due: {new Date(a.deadline).toLocaleDateString()}</span>
                    </span>
                    <span>Revisions: {a.revision_count || 0}</span>
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Right: Selected Assignment Details & Workspace */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl">
            {selectedAssignment ? (
              <div className="space-y-4">
                <div>
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold text-indigo-400 uppercase tracking-wider">Project Dossier</span>
                    <span className="text-xs font-mono text-emerald-400 font-semibold">${selectedAssignment.budget} Escrowed</span>
                  </div>
                  <h2 className="text-base font-bold text-white mt-1">{selectedAssignment.title}</h2>
                  <p className="text-xs text-slate-400 mt-1">{selectedAssignment.description}</p>
                </div>

                {/* Instructions & Specs */}
                <div className="p-3 bg-slate-950 border border-slate-800 rounded-xl space-y-1.5 text-xs text-slate-300">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Subject:</span>
                    <span className="font-semibold text-slate-200">{selectedAssignment.subject}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Citation Style:</span>
                    <span className="font-semibold text-slate-200">{selectedAssignment.citation_style}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Academic Level:</span>
                    <span className="font-semibold text-slate-200">{selectedAssignment.academic_level}</span>
                  </div>
                </div>

                {/* Deliverable Review Section (If Submitted) */}
                {selectedAssignment.status === 'Submitted' && (
                  <div className="p-4 bg-purple-950/30 border border-purple-800/50 rounded-xl space-y-3">
                    <div className="flex items-center space-x-2 text-purple-300">
                      <CheckCircle className="w-4 h-4" />
                      <span className="text-xs font-bold uppercase tracking-wider">Deliverable Ready for Review</span>
                    </div>
                    {selectedAssignment.deliverable_notes && (
                      <p className="text-xs text-slate-300 bg-slate-950/60 p-2.5 rounded-lg border border-purple-900/40">
                        "{selectedAssignment.deliverable_notes}"
                      </p>
                    )}

                    <div className="grid grid-cols-2 gap-2 pt-1">
                      <button
                        onClick={handleApprove}
                        disabled={actionLoading}
                        className="py-2 px-3 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition shadow"
                      >
                        Approve & Pay Specialist
                      </button>
                      <button
                        onClick={() => setShowRevisionModal(true)}
                        className="py-2 px-3 rounded-lg bg-amber-600/30 border border-amber-600/50 hover:bg-amber-600/40 text-amber-200 text-xs font-bold transition"
                      >
                        Request Revision
                      </button>
                    </div>
                  </div>
                )}

                {/* Dispute Button */}
                {['Claimed', 'In Progress', 'Submitted'].includes(selectedAssignment.status) && (
                  <button
                    onClick={() => setShowDisputeModal(true)}
                    className="w-full py-1.5 rounded-lg border border-red-900/60 bg-red-950/20 hover:bg-red-950/40 text-red-400 text-xs font-semibold transition"
                  >
                    Raise Arbitration / Dispute
                  </button>
                )}

                {/* In-project messaging */}
                <div className="pt-3 border-t border-slate-800">
                  <h3 className="text-xs font-bold text-slate-300 mb-2 flex items-center space-x-1.5">
                    <MessageSquare className="w-3.5 h-3.5 text-indigo-400" />
                    <span>Project Discussion</span>
                  </h3>

                  <div className="h-44 overflow-y-auto space-y-2 p-2 bg-slate-950 rounded-xl border border-slate-800 text-xs">
                    {messages.length === 0 ? (
                      <p className="text-slate-500 text-center py-6 text-[11px]">No messages yet. Direct writer communications are logged for dispute safety.</p>
                    ) : (
                      messages.map(m => (
                        <div
                          key={m.id}
                          className={`p-2 rounded-lg max-w-[85%] ${
                            m.sender_id === profile?.id
                              ? 'bg-indigo-600/30 border border-indigo-500/40 text-slate-200 ml-auto'
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
                      placeholder="Send message to specialist..."
                      className="flex-1 bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                    />
                    <button
                      type="submit"
                      disabled={messagingLoading}
                      className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold transition"
                    >
                      <Send className="w-3.5 h-3.5" />
                    </button>
                  </form>
                </div>
              </div>
            ) : (
              <div className="p-8 text-center text-xs text-slate-500">
                Select a project from the left to view deliverable status, audit logs, and specialist chat.
              </div>
            )}
          </div>
        </div>
      )}

      {/* REVISION MODAL */}
      {showRevisionModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-700 rounded-xl p-5 max-w-md w-full">
            <h3 className="text-sm font-bold text-white mb-2">Request Deliverable Revision</h3>
            <p className="text-xs text-slate-400 mb-3">Provide specific feedback and points requiring refinement.</p>
            <textarea
              rows={4}
              required
              value={revisionNotes}
              onChange={(e) => setRevisionNotes(e.target.value)}
              placeholder="e.g. Please expand section 3 literature citations and verify IEEE format..."
              className="w-full bg-slate-950 border border-slate-700 rounded-lg p-3 text-xs text-white focus:outline-none focus:border-indigo-500 mb-3"
            />
            <div className="flex justify-end space-x-2">
              <button
                onClick={() => setShowRevisionModal(false)}
                className="px-3 py-1.5 rounded-lg bg-slate-800 text-slate-400 text-xs font-semibold"
              >
                Cancel
              </button>
              <button
                onClick={handleRequestRevision}
                disabled={actionLoading}
                className="px-3 py-1.5 rounded-lg bg-amber-600 text-white text-xs font-bold"
              >
                Submit Revision Request
              </button>
            </div>
          </div>
        </div>
      )}

      {/* DISPUTE MODAL */}
      {showDisputeModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-700 rounded-xl p-5 max-w-md w-full">
            <h3 className="text-sm font-bold text-white mb-1">Open Formal Dispute</h3>
            <p className="text-xs text-slate-400 mb-3">
              This locks escrow and escalates this project to Intelliworks Administration for objective review.
            </p>
            <textarea
              rows={4}
              required
              value={disputeReason}
              onChange={(e) => setDisputeReason(e.target.value)}
              placeholder="Describe the contractual violation, missed deadline, or quality defect..."
              className="w-full bg-slate-950 border border-slate-700 rounded-lg p-3 text-xs text-white focus:outline-none focus:border-red-500 mb-3"
            />
            <div className="flex justify-end space-x-2">
              <button
                onClick={() => setShowDisputeModal(false)}
                className="px-3 py-1.5 rounded-lg bg-slate-800 text-slate-400 text-xs font-semibold"
              >
                Cancel
              </button>
              <button
                onClick={handleOpenDispute}
                disabled={actionLoading}
                className="px-3 py-1.5 rounded-lg bg-red-600 text-white text-xs font-bold"
              >
                Escalate to Admin Arbitration
              </button>
            </div>
          </div>
        </div>
      )}

      {/* REVIEW SPECIALIST MODAL */}
      {showReviewModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-700 rounded-xl p-5 max-w-md w-full text-center">
            <h3 className="text-sm font-bold text-white mb-1">Rate Specialist Deliverable</h3>
            <p className="text-xs text-slate-400 mb-4">Your rating contributes to the specialist's marketplace standing.</p>
            
            <div className="flex justify-center space-x-2 mb-4">
              {[1, 2, 3, 4, 5].map(star => (
                <button
                  key={star}
                  type="button"
                  onClick={() => setReviewRating(star)}
                  className="text-2xl transition"
                >
                  <Star className={`w-6 h-6 ${star <= reviewRating ? 'text-amber-400 fill-amber-400' : 'text-slate-600'}`} />
                </button>
              ))}
            </div>

            <textarea
              rows={3}
              value={reviewComment}
              onChange={(e) => setReviewComment(e.target.value)}
              placeholder="Exceptional research rigor, delivered ahead of schedule..."
              className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2.5 text-xs text-white focus:outline-none focus:border-indigo-500 mb-4"
            />

            <button
              onClick={handleSubmitReview}
              className="w-full py-2 rounded-lg bg-indigo-600 text-white text-xs font-bold"
            >
              Submit Review & Complete
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
