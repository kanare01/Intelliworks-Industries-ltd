import React from 'react';
import { ShieldCheck, AlertTriangle, BookOpen, Check, X } from 'lucide-react';

export function AcademicIntegrityBanner({ isOpen, onClose }) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm">
      <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-2xl w-full p-6 shadow-2xl relative max-h-[90vh] overflow-y-auto">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-slate-400 hover:text-white"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center space-x-3 mb-4">
          <div className="p-2.5 rounded-xl bg-cyan-950/80 border border-cyan-800 text-cyan-400">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-white tracking-tight">Academic Integrity & Ethical Standards</h2>
            <p className="text-xs text-slate-400">Intelliworks Industries Institutional Honor Code</p>
          </div>
        </div>

        <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-4 mb-5 text-xs leading-relaxed text-slate-300">
          <p className="font-semibold text-cyan-300 mb-1">Our Mission Statement:</p>
          Intelliworks Industries operates strictly as an academic and professional services marketplace. We empower students, researchers, faculty, and institutions through ethical collaboration, subject-matter expertise, and rigorous research support. We enforce a zero-tolerance policy against academic dishonesty.
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          {/* Permitted */}
          <div className="bg-emerald-950/20 border border-emerald-800/40 rounded-xl p-4">
            <h3 className="text-xs font-bold text-emerald-400 flex items-center space-x-1.5 mb-2.5 uppercase tracking-wider">
              <Check className="w-4 h-4 text-emerald-400" />
              <span>Permitted Services</span>
            </h3>
            <ul className="space-y-1.5 text-xs text-slate-300">
              <li className="flex items-start space-x-1.5">
                <span className="text-emerald-400">•</span>
                <span>Subject tutoring & concept clarification</span>
              </li>
              <li className="flex items-start space-x-1.5">
                <span className="text-emerald-400">•</span>
                <span>Literature reviews & source compilation</span>
              </li>
              <li className="flex items-start space-x-1.5">
                <span className="text-emerald-400">•</span>
                <span>Statistical, dataset & code analysis</span>
              </li>
              <li className="flex items-start space-x-1.5">
                <span className="text-emerald-400">•</span>
                <span>Substantive editing, syntax & grammar polishing</span>
              </li>
              <li className="flex items-start space-x-1.5">
                <span className="text-emerald-400">•</span>
                <span>LaTeX formatting, bibtex & citation indexing</span>
              </li>
            </ul>
          </div>

          {/* Prohibited */}
          <div className="bg-red-950/20 border border-red-800/40 rounded-xl p-4">
            <h3 className="text-xs font-bold text-red-400 flex items-center space-x-1.5 mb-2.5 uppercase tracking-wider">
              <AlertTriangle className="w-4 h-4 text-red-400" />
              <span>Strictly Prohibited</span>
            </h3>
            <ul className="space-y-1.5 text-xs text-slate-300">
              <li className="flex items-start space-x-1.5">
                <span className="text-red-400">•</span>
                <span>Contract cheating or proxy exam taking</span>
              </li>
              <li className="flex items-start space-x-1.5">
                <span className="text-red-400">•</span>
                <span>Submitting deliverables as original student coursework</span>
              </li>
              <li className="flex items-start space-x-1.5">
                <span className="text-red-400">•</span>
                <span>Data falsification or fabricated experiments</span>
              </li>
              <li className="flex items-start space-x-1.5">
                <span className="text-red-400">•</span>
                <span>Plagiarism or bypass of plagiarism scanners</span>
              </li>
            </ul>
          </div>
        </div>

        <div className="flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold transition"
          >
            I Acknowledge & Understand
          </button>
        </div>
      </div>
    </div>
  );
}
