import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { ShieldAlert, Clock, CheckCircle, AlertTriangle } from 'lucide-react';

export function DisputesView() {
  const [disputes, setDisputes] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.listDisputes()
      .then(res => setDisputes(res.disputes || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="border-b border-slate-800 pb-4 mb-6">
        <h1 className="text-xl font-bold text-white tracking-tight">Contractual Disputes & Arbitration</h1>
        <p className="text-xs text-slate-400">Status of escalated commissions under executive administrative arbitration</p>
      </div>

      {loading ? (
        <div className="p-8 text-center text-xs text-slate-500">Loading disputes...</div>
      ) : disputes.length === 0 ? (
        <div className="p-12 text-center bg-slate-900/60 border border-slate-800 rounded-2xl">
          <ShieldAlert className="w-10 h-10 text-slate-600 mx-auto mb-2" />
          <h3 className="text-sm font-semibold text-slate-300">No Active Disputes</h3>
          <p className="text-xs text-slate-500 mt-1">You have zero contested projects or unresolved grievances.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {disputes.map(d => (
            <div key={d.id} className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow">
              <div className="flex items-center justify-between mb-2">
                <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full ${
                  d.status === 'Resolved' ? 'bg-emerald-950 text-emerald-300 border border-emerald-800/60' :
                  'bg-red-950 text-red-300 border border-red-800/60'
                }`}>
                  {d.status}
                </span>
                <span className="text-xs font-mono font-bold text-white">${d.budget} Under Escrow Hold</span>
              </div>

              <h3 className="text-sm font-bold text-white">{d.assignment_title}</h3>
              <p className="text-xs text-slate-300 bg-slate-950 p-3 rounded-xl border border-slate-800 mt-3">
                <span className="font-semibold text-red-400 block mb-1">Reason Stated:</span>
                "{d.reason}"
              </p>

              {d.resolution_notes && (
                <div className="mt-3 p-3 bg-indigo-950/40 border border-indigo-800/40 rounded-xl text-xs text-indigo-200">
                  <span className="font-bold block mb-1">Administrative Ruling & Judgment:</span>
                  <p>{d.resolution_notes}</p>
                  <span className="text-[10px] text-indigo-400 block mt-1 font-semibold">
                    Action Taken: {d.resolution_action}
                  </span>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
