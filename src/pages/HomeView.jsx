import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';
import { 
  ShieldCheck, 
  ArrowRight, 
  CheckCircle2, 
  BookOpen, 
  Lock, 
  Award, 
  Users, 
  FileText, 
  DollarSign, 
  Database,
  Briefcase
} from 'lucide-react';

export function HomeView({ onOpenAuth, onOpenPolicy, onOpenConfig, onSelectTab }) {
  const { user, profile } = useAuth();
  const [openProjects, setOpenProjects] = useState([]);

  useEffect(() => {
    api.listAssignments({ view: 'open' })
      .then(res => setOpenProjects((res.assignments || []).slice(0, 3)))
      .catch(() => {});
  }, []);

  return (
    <div className="space-y-16 py-8">
      {/* Hero Section */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center pt-8 pb-4">
        <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-indigo-950/60 border border-indigo-800/60 text-indigo-300 text-xs font-semibold mb-6">
          <ShieldCheck className="w-3.5 h-3.5 text-cyan-400" />
          <span>Institutional Honor Code & Escrow-Protected Marketplace</span>
        </div>

        <h1 className="text-3xl sm:text-5xl font-extrabold text-white tracking-tight max-w-3xl mx-auto leading-tight">
          Rigorous Academic Assistance, Powered by Guaranteed Escrow
        </h1>

        <p className="mt-4 text-sm sm:text-base text-slate-400 max-w-2xl mx-auto leading-relaxed">
          Intelliworks Industries connects researchers, faculty, and scholars with verified subject-matter specialists for literature synthesis, statistical data analysis, editing, and technical typesetting.
        </p>

        {/* CTA Buttons */}
        <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-3">
          {user ? (
            <button
              onClick={() => {
                if (profile?.role === 'Client') onSelectTab('client-create');
                else if (profile?.role === 'Writer') onSelectTab('writer-marketplace');
                else onSelectTab('admin-metrics');
              }}
              className="w-full sm:w-auto px-6 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs sm:text-sm font-bold shadow-lg shadow-indigo-500/25 transition flex items-center justify-center space-x-2"
            >
              <span>Go to Your Workspace</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          ) : (
            <>
              <button
                onClick={() => onOpenAuth('register')}
                className="w-full sm:w-auto px-6 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs sm:text-sm font-bold shadow-lg shadow-indigo-500/25 transition flex items-center justify-center space-x-2"
              >
                <span>Commission a Project</span>
                <ArrowRight className="w-4 h-4" />
              </button>
              <button
                onClick={() => onOpenAuth('register')}
                className="w-full sm:w-auto px-6 py-3 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs sm:text-sm font-bold transition"
              >
                Apply as Specialist Writer
              </button>
            </>
          )}

          <button
            onClick={onOpenPolicy}
            className="w-full sm:w-auto px-5 py-3 rounded-xl bg-slate-900/80 hover:bg-slate-800 text-cyan-400 border border-slate-800 text-xs sm:text-sm font-semibold transition flex items-center justify-center space-x-2"
          >
            <BookOpen className="w-4 h-4 text-cyan-400" />
            <span>Academic Policy</span>
          </button>
        </div>
      </section>

      {/* 3 Value Pillars */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 relative overflow-hidden">
            <div className="w-10 h-10 rounded-xl bg-indigo-950 border border-indigo-800 text-indigo-400 flex items-center justify-center mb-4">
              <Lock className="w-5 h-5" />
            </div>
            <h3 className="text-base font-bold text-white mb-2">Automated 80/20 Escrow</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Client funds are held in state-authoritative PostgreSQL escrow upon project commissioning. Specialists are guaranteed 80% payout immediately upon deliverable milestone approval.
            </p>
          </div>

          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 relative overflow-hidden">
            <div className="w-10 h-10 rounded-xl bg-cyan-950 border border-cyan-800 text-cyan-400 flex items-center justify-center mb-4">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <h3 className="text-base font-bold text-white mb-2">Institutional Integrity</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Strictly prohibited contract cheating and ghostwriting filters. All projects are audited against university honor codes, focusing on developmental tutoring and scientific editing.
            </p>
          </div>

          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 relative overflow-hidden">
            <div className="w-10 h-10 rounded-xl bg-amber-950 border border-amber-800 text-amber-400 flex items-center justify-center mb-4">
              <Award className="w-5 h-5" />
            </div>
            <h3 className="text-base font-bold text-white mb-2">Administrative Arbitration</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Disputes are arbitrated by executive administrators with access to timestamped chat transcripts, deliverable revisions, and immutable cryptographic audit logs.
            </p>
          </div>
        </div>
      </section>

      {/* Live Marketplace Highlights */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-lg font-bold text-white tracking-tight">Active Academic Commissions</h2>
            <p className="text-xs text-slate-400">Sample opportunities currently awaiting specialist claiming</p>
          </div>

          <button
            onClick={() => {
              if (user && profile?.role === 'Writer') onSelectTab('writer-marketplace');
              else onOpenAuth('register');
            }}
            className="text-xs font-semibold text-cyan-400 hover:text-cyan-300 flex items-center space-x-1"
          >
            <span>Explore All</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {openProjects.length > 0 ? (
            openProjects.map(p => (
              <div key={p.id} className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-indigo-950 text-indigo-300 border border-indigo-800/60">
                      {p.category}
                    </span>
                    <span className="text-xs font-mono font-bold text-emerald-400">
                      ${(p.budget * 0.8).toFixed(2)} Specialist Net
                    </span>
                  </div>
                  <h4 className="text-xs font-bold text-white">{p.title}</h4>
                  <p className="text-[11px] text-slate-400 mt-1 line-clamp-2">{p.description}</p>
                </div>
                <div className="mt-3 pt-3 border-t border-slate-800/60 flex items-center justify-between text-[11px] text-slate-500">
                  <span>{p.subject}</span>
                  <span>Due: {new Date(p.deadline).toLocaleDateString()}</span>
                </div>
              </div>
            ))
          ) : (
            [
              { title: 'Systematic Review of LLM Fine-Tuning Benchmarks', cat: 'Literature Review', sub: 'Computer Science', payout: '$160.00' },
              { title: 'Empirical Econometric Estimation in Stata / R', cat: 'Data Analysis & Code', sub: 'Applied Economics', payout: '$240.00' },
              { title: 'Substantive LaTeX Typesetting for Annals of Math', cat: 'LaTeX Typesetting', sub: 'Pure Mathematics', payout: '$120.00' }
            ].map((p, idx) => (
              <div key={idx} className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-indigo-950 text-indigo-300 border border-indigo-800/60">
                      {p.cat}
                    </span>
                    <span className="text-xs font-mono font-bold text-emerald-400">
                      {p.payout} Net
                    </span>
                  </div>
                  <h4 className="text-xs font-bold text-white">{p.title}</h4>
                  <p className="text-[11px] text-slate-400 mt-1">Structured methodological research synthesis and review assistance.</p>
                </div>
                <div className="mt-3 pt-3 border-t border-slate-800/60 flex items-center justify-between text-[11px] text-slate-500">
                  <span>{p.sub}</span>
                  <span>7 Day Horizon</span>
                </div>
              </div>
            ))
          )}
        </div>
      </section>
    </div>
  );
}
