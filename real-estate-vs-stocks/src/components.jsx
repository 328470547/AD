import React from 'react';
import { fmtILS } from './format.js';
import { CARD_META } from './insights.js';

export function Field({ label, value, min, max, step, unit, onChange, format }) {
  const display = format ? format(value) : `${value}${unit || ''}`;
  return (
    <div className="mb-4">
      <div className="flex items-center justify-between mb-1">
        <label className="text-sm font-medium text-slate-600">{label}</label>
        <span className="text-sm font-semibold text-brand-700 tabular-nums">{display}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="w-full"
      />
    </div>
  );
}

export function NumField({ label, value, onChange, prefix }) {
  return (
    <div className="mb-4">
      <label className="text-sm font-medium text-slate-600 block mb-1">{label}</label>
      <div className="relative">
        {prefix && <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-sm">{prefix}</span>}
        <input
          type="number"
          value={value}
          onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
          className={`w-full rounded-lg border border-slate-300 bg-slate-50 py-2 ${prefix ? 'pl-8' : 'pl-3'} pr-3 text-sm font-semibold text-slate-800 focus:border-brand-500 focus:ring-2 focus:ring-brand-100 outline-none`}
        />
      </div>
    </div>
  );
}

export function SectionTitle({ children, icon }) {
  return (
    <h3 className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-400 mt-6 mb-3 first:mt-0">
      <span>{icon}</span>{children}
    </h3>
  );
}

export function Toggle({ checked, onChange, label, sub }) {
  return (
    <div className="flex items-center justify-between rounded-lg bg-brand-50 border border-brand-100 px-3 py-2.5 mb-4">
      <div>
        <div className="text-sm font-semibold text-slate-700">{label}</div>
        {sub && <div className="text-xs text-slate-500">{sub}</div>}
      </div>
      <button
        type="button"
        onClick={() => onChange(!checked)}
        className={`relative w-11 h-6 rounded-full transition-colors shrink-0 ${checked ? 'bg-brand-600' : 'bg-slate-300'}`}
      >
        <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${checked ? 'translate-x-5' : ''}`} />
      </button>
    </div>
  );
}

export function SummaryCard({ id, value, initialCapital, isWinner, disabled }) {
  const meta = CARD_META[id];
  const profit = value - initialCapital;
  const multiple = initialCapital > 0 ? value / initialCapital : 0;
  return (
    <div className={`relative rounded-2xl bg-white p-5 shadow-sm border ${isWinner ? `ring-2 ${meta.ring} border-transparent shadow-md` : 'border-slate-200'} ${disabled ? 'opacity-40' : ''}`}>
      {isWinner && !disabled && (
        <span className="absolute -top-3 right-4 text-[11px] font-bold text-white px-2.5 py-1 rounded-full bg-gradient-to-r from-amber-400 to-amber-500 shadow">
          🏆 Best Outcome
        </span>
      )}
      <div className="flex items-center gap-2 mb-3">
        <div className={`w-9 h-9 rounded-xl flex items-center justify-center text-white text-base ${meta.bg}`}>{meta.icon}</div>
        <div className="text-sm font-semibold text-slate-600">{meta.title}</div>
      </div>
      <div className="text-2xl font-extrabold text-slate-900 tabular-nums">{fmtILS(value)}</div>
      <div className="text-xs text-slate-400 mb-3">final net wealth</div>
      <div className="flex items-center justify-between text-sm border-t border-slate-100 pt-3">
        <span className="text-slate-500">Net profit</span>
        <span className={`font-bold tabular-nums ${profit >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>{fmtILS(profit, { showSign: true })}</span>
      </div>
      <div className="flex items-center justify-between text-sm mt-1">
        <span className="text-slate-500">Return multiple</span>
        <span className="font-bold text-slate-700 tabular-nums">{multiple.toFixed(2)}×</span>
      </div>
    </div>
  );
}

export function CustomTooltip({ active, payload, label, leverageEnabled }) {
  if (!active || !payload || !payload.length) return null;
  return (
    <div className="rounded-lg bg-white shadow-lg border border-slate-200 px-3 py-2 text-xs">
      <div className="font-bold text-slate-700 mb-1">Year {label}</div>
      {payload
        .filter((p) => leverageEnabled || p.dataKey !== 'LeveragedStocks')
        .map((p) => (
          <div key={p.dataKey} className="flex items-center gap-2 justify-between">
            <span className="flex items-center gap-1.5 text-slate-500">
              <span className="w-2 h-2 rounded-full" style={{ background: p.color }}></span>
              {CARD_META[p.dataKey].title}
            </span>
            <span className="font-semibold text-slate-800 tabular-nums ml-3">{fmtILS(p.value)}</span>
          </div>
        ))}
    </div>
  );
}

export function Stat({ label, value }) {
  return (
    <div className="rounded-lg bg-slate-50 border border-slate-100 px-3 py-2.5">
      <div className="text-[11px] text-slate-400 mb-0.5">{label}</div>
      <div className="font-bold text-slate-800 tabular-nums">{value}</div>
    </div>
  );
}
