import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { DollarSign, ArrowUpRight, ArrowDownLeft, ShieldCheck, Clock, CheckCircle } from 'lucide-react';

export function TransactionsView() {
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getTransactions()
      .then(res => setTransactions(res.transactions || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="border-b border-slate-800 pb-4 mb-6">
        <h1 className="text-xl font-bold text-white tracking-tight">Institutional Financial Ledger</h1>
        <p className="text-xs text-slate-400">Cryptographically tracked escrow settlements, payouts, and balances</p>
      </div>

      {loading ? (
        <div className="p-8 text-center text-xs text-slate-500">Querying transaction ledger...</div>
      ) : transactions.length === 0 ? (
        <div className="p-12 text-center bg-slate-900/60 border border-slate-800 rounded-2xl">
          <DollarSign className="w-10 h-10 text-slate-600 mx-auto mb-2" />
          <h3 className="text-sm font-semibold text-slate-300">No Ledger Entries Yet</h3>
          <p className="text-xs text-slate-500 mt-1">Escrow deposits, releases, and withdrawals will appear here as transactions execute.</p>
        </div>
      ) : (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-950 text-slate-400 font-semibold border-b border-slate-800">
              <tr>
                <th className="p-3">Timestamp</th>
                <th className="p-3">Type</th>
                <th className="p-3">Amount</th>
                <th className="p-3">Balance After</th>
                <th className="p-3">Reference / Project</th>
                <th className="p-3">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {transactions.map(t => (
                <tr key={t.id} className="hover:bg-slate-850">
                  <td className="p-3 font-mono text-[11px] text-slate-400">
                    {new Date(t.created_at).toLocaleDateString()} {new Date(t.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </td>
                  <td className="p-3">
                    <span className={`inline-flex items-center space-x-1 font-semibold ${
                      t.transaction_type.includes('Deposit') || t.transaction_type.includes('Payout') ? 'text-emerald-400' :
                      t.transaction_type.includes('Fee') ? 'text-slate-400' : 'text-amber-400'
                    }`}>
                      {t.transaction_type.includes('Payout') ? <ArrowDownLeft className="w-3.5 h-3.5" /> : <ArrowUpRight className="w-3.5 h-3.5" />}
                      <span>{t.transaction_type}</span>
                    </span>
                  </td>
                  <td className="p-3 font-mono font-bold text-white">
                    ${Number(t.amount).toFixed(2)}
                  </td>
                  <td className="p-3 font-mono text-slate-400">
                    ${Number(t.balance_after || 0).toFixed(2)}
                  </td>
                  <td className="p-3 text-slate-400 truncate max-w-xs font-mono text-[11px]">
                    {t.reference_id || 'Direct Ledger'}
                  </td>
                  <td className="p-3">
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-950 text-emerald-300 border border-emerald-800/60">
                      {t.status || 'Completed'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
