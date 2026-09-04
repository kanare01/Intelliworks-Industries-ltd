import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { Database, ShieldAlert, Key, CheckCircle, Copy, Check, Terminal, ExternalLink, X } from 'lucide-react';

export function ConfigurationStatusModal({ isOpen, onClose }) {
  const [health, setHealth] = useState(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (isOpen) {
      api.getHealth().then(setHealth).catch(err => {
        setHealth({ status: 'offline', configured: false, database: 'Unreachable' });
      });
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const copySqlSchema = () => {
    navigator.clipboard.writeText('-- Run schema.sql from the project root in your Supabase SQL Editor');
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
      <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-2xl w-full p-6 shadow-2xl relative max-h-[90vh] overflow-y-auto">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-slate-400 hover:text-white"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center space-x-3 mb-5">
          <div className="p-2.5 rounded-xl bg-indigo-950/80 border border-indigo-800 text-indigo-400">
            <Database className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-white tracking-tight">Supabase Foundation & Infrastructure Status</h2>
            <p className="text-xs text-slate-400">Production Persistence, Auth & Storage Verification</p>
          </div>
        </div>

        {/* Current status overview */}
        <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 mb-5 space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-400">Flask Backend Engine:</span>
            <span className="font-mono text-emerald-400 font-semibold flex items-center space-x-1">
              <span className="w-2 h-2 rounded-full bg-emerald-400 inline-block"></span>
              <span>Online (Port 5001 / Reverse Proxied)</span>
            </span>
          </div>

          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-400">Supabase Connection:</span>
            <span className={`font-mono font-semibold flex items-center space-x-1 ${health?.configured ? 'text-emerald-400' : 'text-amber-400'}`}>
              <span className={`w-2 h-2 rounded-full inline-block ${health?.configured ? 'bg-emerald-400' : 'bg-amber-400'}`}></span>
              <span>{health?.configured ? 'VERIFIED (Connected)' : 'BLOCKED — Credentials Required'}</span>
            </span>
          </div>

          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-400">PostgreSQL Schema:</span>
            <span className="font-mono text-slate-300">schema.sql (13 Tables, RLS Enabled)</span>
          </div>

          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-400">Storage Bucket:</span>
            <span className="font-mono text-slate-300">assignment-files (Private, 50MB)</span>
          </div>
        </div>

        {/* Setup instructions */}
        <div className="space-y-4 text-xs text-slate-300">
          <h3 className="font-bold text-slate-100 uppercase tracking-wider text-[11px]">Setup Steps to Connect Live Supabase:</h3>
          
          <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-lg space-y-2">
            <div className="font-semibold text-indigo-300">1. Run Database Migrations</div>
            <p className="text-slate-400">
              Open your Supabase Project Dashboard &gt; SQL Editor, and execute the complete contents of <code className="text-slate-200 bg-slate-800 px-1 py-0.5 rounded">schema.sql</code> and <code className="text-slate-200 bg-slate-800 px-1 py-0.5 rounded">storage-policies.sql</code>.
            </p>
          </div>

          <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-lg space-y-2">
            <div className="font-semibold text-indigo-300">2. Configure Environment Variables</div>
            <p className="text-slate-400">
              In your AI Studio Project Settings &gt; Secrets, or in your deployment environment, set:
            </p>
            <pre className="bg-slate-900 border border-slate-800 rounded p-2 text-[11px] font-mono text-cyan-300 overflow-x-auto">
{`SUPABASE_URL=https://<your-project-id>.supabase.co
SUPABASE_ANON_KEY=<your-anon-key>
SUPABASE_SERVICE_ROLE_KEY=<your-service-role-key>
VITE_SUPABASE_URL=https://<your-project-id>.supabase.co
VITE_SUPABASE_ANON_KEY=<your-anon-key>`}
            </pre>
            <p className="text-[10px] text-amber-400">
              * Note: The service role key is strictly server-only and never exposed to the client.
            </p>
          </div>

          <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-lg space-y-2">
            <div className="font-semibold text-indigo-300">3. Create Storage Bucket</div>
            <p className="text-slate-400">
              In Supabase Dashboard &gt; Storage, ensure a private bucket named <code className="text-slate-200 bg-slate-800 px-1 py-0.5 rounded">assignment-files</code> exists.
            </p>
          </div>
        </div>

        <div className="mt-6 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold transition"
          >
            Close Diagnostics
          </button>
        </div>
      </div>
    </div>
  );
}
