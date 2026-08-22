import { fmtILS, fmtPct } from './format.js';

export const CARD_META = {
  RealEstate: { title: 'Buy a Home', color: '#2c39e0', bg: 'bg-brand-600', ring: 'ring-brand-200', icon: '🏠' },
  Stocks: { title: 'Rent + Invest (Unleveraged)', color: '#059669', bg: 'bg-emerald-600', ring: 'ring-emerald-200', icon: '📈' },
  LeveragedStocks: { title: 'Rent + Invest (Leveraged)', color: '#d97706', bg: 'bg-amber-600', ring: 'ring-amber-200', icon: '⚡' }
};

export function buildInsights(sim, inputs) {
  const { final, details } = sim;
  const { leverageEnabled, capitalGainsTax } = inputs;
  const options = [
    { id: 'RealEstate', v: final.RealEstate },
    { id: 'Stocks', v: final.Stocks },
    ...(leverageEnabled ? [{ id: 'LeveragedStocks', v: final.LeveragedStocks }] : [])
  ].sort((a, b) => b.v - a.v);
  const winner = options[0];
  const runnerUp = options[1];
  const gap = winner.v - runnerUp.v;

  const insights = [];

  insights.push({
    icon: '🏆',
    text: `${CARD_META[winner.id].title} produces the highest net wealth after ${inputs.years} years — ${fmtILS(winner.v)}, beating ${CARD_META[runnerUp.id].title} by ${fmtILS(gap)}.`
  });

  insights.push({
    icon: '🧾',
    text: `Tax exemption effect: as a single primary residence, the property pays ₪0 in capital-gains and purchase tax. The stock portfolio(s) pay ${fmtPct(capitalGainsTax, 0)} on real (inflation-adjusted) gains — ${fmtILS(details.taxPaidStocks)} in tax for the unleveraged path${leverageEnabled ? `, ${fmtILS(details.taxPaidLeveraged)} for the leveraged path` : ''}.`
  });

  insights.push({
    icon: '🏠',
    text: `Home financing costs: over the horizon, the mortgage accrues ${fmtILS(details.cumMortgageInterest)} in interest and ${fmtILS(details.cumMaintenance)} in maintenance/closing costs, against a property value that grows from ${fmtILS(inputs.purchasePrice)} to ${fmtILS(details.propertyValueFinal)}.`
  });

  insights.push({
    icon: '🏚️',
    text: `Rent drain: renting instead of buying costs ${fmtILS(details.cumRent)} in cumulative rent over ${inputs.years} years, a direct drag on both stock-investing paths' net wealth.`
  });

  if (leverageEnabled) {
    const leverageImpact = final.LeveragedStocks - final.Stocks;
    insights.push({
      icon: '⚡',
      text: leverageImpact >= 0
        ? `Leverage impact: borrowing ${fmtILS(details.loanAmount)} to invest adds ${fmtILS(leverageImpact)} of extra net wealth versus the unleveraged path, even after paying ${fmtILS(details.cumLeverageInterest)} in loan interest and repaying the principal — because the stock return (${fmtPct(inputs.stockYield)}) exceeds the loan rate (${fmtPct(inputs.leverageRate)}).`
        : `Leverage impact: borrowing ${fmtILS(details.loanAmount)} to invest actually costs ${fmtILS(Math.abs(leverageImpact))} of net wealth versus the unleveraged path — the loan rate (${fmtPct(inputs.leverageRate)}) is eating into returns faster than the stock market (${fmtPct(inputs.stockYield)}) compounds.`
    });
  }

  if (details.surplus > 0) {
    insights.push({
      icon: '💰',
      text: `Only ${fmtILS(details.downPayment)} of your ${fmtILS(inputs.initialCapital)} capital is needed as a down payment, so the remaining ${fmtILS(details.surplus)} is also invested in stocks in the "Buy a Home" scenario, keeping the starting capital equal across all three paths.`
    });
  }
  if (details.shortfall > 0) {
    insights.push({
      icon: '⚠️',
      text: `Capital shortfall: the required down payment (${fmtILS(details.downPayment)}) exceeds your initial capital by ${fmtILS(details.shortfall)}. Increase initial capital, lower the purchase price, or raise the LTV to close the gap.`
    });
  }

  insights.push({
    icon: '📊',
    text: `Starting monthly cash-flow difference: mortgage payment ${fmtILS(details.monthlyPayment)} vs. rent ${fmtILS(inputs.monthlyRent)} — this ${details.firstMonthContribution >= 0 ? 'surplus' : 'shortfall'} of ${fmtILS(Math.abs(details.firstMonthContribution))}/month is what gets invested (or withdrawn) in the stock scenarios, growing with rent inflation over time.`
  });

  return insights;
}
