import React, { useMemo, useState } from 'react';
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ReferenceLine
} from 'recharts';
import { simulate } from './simulation.js';
import { fmtILS } from './format.js';
import { CARD_META, buildInsights } from './insights.js';
import {
  Field, NumField, SectionTitle, Toggle, SummaryCard, CustomTooltip, Stat
} from './components.jsx';

const DEFAULT_INPUTS = {
  initialCapital: 200000,
  years: 20,
  purchasePrice: 600000,
  ltv: 75,
  appreciationRate: 5.8,
  mortgageRate: 4.8,
  totalMaintenance: 90000,
  stockYield: 10.2,
  monthlyRent: 3000,
  rentInflation: 3,
  capitalGainsTax: 25,
  cpiRate: 2.5,
  leverageEnabled: true,
  leverageRate: 6.5
};

export default function App() {
  const [inputs, setInputs] = useState(DEFAULT_INPUTS);
  const set = (key) => (val) => setInputs((s) => ({ ...s, [key]: val }));

  const sim = useMemo(() => simulate(inputs), [inputs]);
  const { yearlyData, final, details } = sim;

  const winnerId = useMemo(() => {
    const opts = [
      { id: 'RealEstate', v: final.RealEstate },
      { id: 'Stocks', v: final.Stocks },
      ...(inputs.leverageEnabled ? [{ id: 'LeveragedStocks', v: final.LeveragedStocks }] : [])
    ];
    return opts.sort((a, b) => b.v - a.v)[0].id;
  }, [final, inputs.leverageEnabled]);

  const insights = useMemo(() => buildInsights(sim, inputs), [sim, inputs]);

  return (
    <div className="min-h-screen pb-16">
      <header className="bg-white border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-5">
          <h1 className="text-xl sm:text-2xl font-extrabold text-slate-900">Buy vs. Rent &amp; Invest — Wealth Simulator</h1>
          <p className="text-sm text-slate-500 mt-1">
            Compare buying a primary residence against renting and investing in the stock market, with or without leverage, over a long-term horizon.
          </p>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 mt-6 grid grid-cols-1 lg:grid-cols-[360px_1fr] gap-6">

        {/* -------- Sidebar: Inputs -------- */}
        <aside className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5 h-fit lg:sticky lg:top-6 max-h-[calc(100vh-3rem)] overflow-y-auto scrollbar-thin">
          <SectionTitle icon="💼">General</SectionTitle>
          <NumField label="Initial capital / equity" value={inputs.initialCapital} onChange={set('initialCapital')} prefix="₪" />
          <Field label="Time horizon" value={inputs.years} min={5} max={30} step={1} unit=" yrs" onChange={set('years')} />

          <SectionTitle icon="🏠">Real Estate</SectionTitle>
          <NumField label="Purchase price" value={inputs.purchasePrice} onChange={set('purchasePrice')} prefix="₪" />
          <Field label="Loan-to-value (mortgage)" value={inputs.ltv} min={0} max={95} step={1} unit="%" onChange={set('ltv')} />
          <Field label="Annual appreciation rate" value={inputs.appreciationRate} min={0} max={12} step={0.1} unit="%" onChange={set('appreciationRate')} />
          <Field label="Mortgage interest rate" value={inputs.mortgageRate} min={0} max={12} step={0.1} unit="%" onChange={set('mortgageRate')} />
          <NumField label="Total maintenance &amp; closing costs" value={inputs.totalMaintenance} onChange={set('totalMaintenance')} prefix="₪" />

          <SectionTitle icon="📈">Stock Market</SectionTitle>
          <Field label="Expected annual yield (S&amp;P 500 / global)" value={inputs.stockYield} min={0} max={15} step={0.1} unit="%" onChange={set('stockYield')} />
          <NumField label="Monthly rent paid" value={inputs.monthlyRent} onChange={set('monthlyRent')} prefix="₪" />
          <Field label="Annual rent inflation" value={inputs.rentInflation} min={0} max={10} step={0.1} unit="%" onChange={set('rentInflation')} />
          <Field label="Capital gains tax" value={inputs.capitalGainsTax} min={0} max={40} step={1} unit="%" onChange={set('capitalGainsTax')} />
          <Field label="Inflation / CPI (for real gain calc)" value={inputs.cpiRate} min={0} max={8} step={0.1} unit="%" onChange={set('cpiRate')} />

          <SectionTitle icon="⚡">Leverage</SectionTitle>
          <Toggle
            checked={inputs.leverageEnabled}
            onChange={set('leverageEnabled')}
            label="Enable leveraged stock portfolio"
            sub="Borrow an amount equal to the mortgage to invest"
          />
          {inputs.leverageEnabled && (
            <Field label="Leverage loan interest rate" value={inputs.leverageRate} min={0} max={15} step={0.1} unit="%" onChange={set('leverageRate')} />
          )}
        </aside>

        {/* -------- Main content -------- */}
        <section className="space-y-6 min-w-0">

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <SummaryCard id="RealEstate" value={final.RealEstate} initialCapital={inputs.initialCapital} isWinner={winnerId === 'RealEstate'} />
            <SummaryCard id="Stocks" value={final.Stocks} initialCapital={inputs.initialCapital} isWinner={winnerId === 'Stocks'} />
            <SummaryCard id="LeveragedStocks" value={final.LeveragedStocks} initialCapital={inputs.initialCapital} isWinner={winnerId === 'LeveragedStocks'} disabled={!inputs.leverageEnabled} />
          </div>

          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5">
            <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
              <h2 className="font-bold text-slate-800">Wealth Accumulation Over Time</h2>
              <div className="flex items-center gap-4 text-xs text-slate-500">
                <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full" style={{ background: CARD_META.RealEstate.color }}></span>Buy a Home</span>
                <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full" style={{ background: CARD_META.Stocks.color }}></span>Rent + Invest</span>
                {inputs.leverageEnabled && <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full" style={{ background: CARD_META.LeveragedStocks.color }}></span>Rent + Invest (Leveraged)</span>}
              </div>
            </div>
            <div style={{ width: '100%', height: 380 }}>
              <ResponsiveContainer>
                <LineChart data={yearlyData} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#eef1f6" />
                  <XAxis dataKey="year" tickFormatter={(y) => `Yr ${y}`} tick={{ fontSize: 12, fill: '#94a3b8' }} axisLine={{ stroke: '#e2e8f0' }} tickLine={false} />
                  <YAxis tickFormatter={(v) => fmtILS(v, { compact: true })} tick={{ fontSize: 12, fill: '#94a3b8' }} axisLine={{ stroke: '#e2e8f0' }} tickLine={false} width={70} />
                  <Tooltip content={<CustomTooltip leverageEnabled={inputs.leverageEnabled} />} />
                  <ReferenceLine y={0} stroke="#cbd5e1" />
                  <Line type="monotone" dataKey="RealEstate" stroke={CARD_META.RealEstate.color} strokeWidth={2.5} dot={false} activeDot={{ r: 5 }} />
                  <Line type="monotone" dataKey="Stocks" stroke={CARD_META.Stocks.color} strokeWidth={2.5} dot={false} activeDot={{ r: 5 }} />
                  {inputs.leverageEnabled && (
                    <Line type="monotone" dataKey="LeveragedStocks" stroke={CARD_META.LeveragedStocks.color} strokeWidth={2.5} dot={false} activeDot={{ r: 5 }} strokeDasharray="6 3" />
                  )}
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5">
            <h2 className="font-bold text-slate-800 mb-4 flex items-center gap-2">💡 Insights — Why This Result?</h2>
            <ul className="space-y-3">
              {insights.map((ins, i) => (
                <li key={i} className="flex gap-3 text-sm text-slate-600 leading-relaxed">
                  <span className="shrink-0">{ins.icon}</span>
                  <span>{ins.text}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5">
            <h2 className="font-bold text-slate-800 mb-4">Key Figures at Year {inputs.years}</h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <Stat label="Mortgage payment / mo" value={fmtILS(details.monthlyPayment)} />
              <Stat label="Total mortgage interest" value={fmtILS(details.cumMortgageInterest)} />
              <Stat label="Property value" value={fmtILS(details.propertyValueFinal)} />
              <Stat label="Remaining mortgage" value={fmtILS(details.mortgageBalanceFinal)} />
              <Stat label="Total rent paid" value={fmtILS(details.cumRent)} />
              <Stat label="Down payment used" value={fmtILS(details.downPayment)} />
              <Stat label="Tax paid (stocks)" value={fmtILS(details.taxPaidStocks)} />
              {inputs.leverageEnabled && <Stat label="Leverage interest paid" value={fmtILS(details.cumLeverageInterest)} />}
            </div>
          </div>

          <p className="text-xs text-slate-400 leading-relaxed">
            Disclaimer: this simulator is a simplified educational model for comparing long-term wealth outcomes. It assumes a fixed-rate amortizing mortgage,
            constant compounding returns (no volatility), an interest-only leverage loan repaid at exit, and Israeli-style tax treatment (0% capital-gains /
            purchase tax on a single primary residence; 25% tax on inflation-adjusted real gains for securities). It is not financial advice.
          </p>
        </section>
      </main>
    </div>
  );
}
