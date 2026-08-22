export function monthlyPayment(principal, annualRatePct, months) {
  const r = annualRatePct / 100 / 12;
  if (principal <= 0) return 0;
  if (r === 0) return principal / months;
  return (principal * r) / (1 - Math.pow(1 + r, -months));
}

/**
 * Runs the year-by-year wealth simulation for all three paths:
 *  A) Buy a primary residence (mortgage + appreciation, 0% CGT/purchase-tax exemption)
 *  B) Rent + invest the initial capital in stocks, unleveraged
 *  C) Rent + invest (initial capital + a loan sized to the mortgage), leveraged
 *
 * Both B and C invest the monthly cash-flow differential (mortgage payment
 * minus current rent) alongside their starting capital, so all three paths
 * deploy the same total capital over time. Capital-gains tax is computed on
 * the "real" (inflation-adjusted) gain: the cost basis is grown by CPI each
 * month, and only the excess of portfolio value over that inflated basis is
 * taxed at exit.
 */
export function simulate(inputs) {
  const {
    initialCapital, years,
    purchasePrice, ltv, appreciationRate, mortgageRate, totalMaintenance,
    stockYield, monthlyRent, rentInflation, capitalGainsTax, cpiRate,
    leverageEnabled, leverageRate
  } = inputs;

  const months = Math.round(years * 12);
  const mortgagePrincipal = purchasePrice * (ltv / 100);
  const downPayment = purchasePrice - mortgagePrincipal;
  const surplus = Math.max(0, initialCapital - downPayment);
  const shortfall = Math.max(0, downPayment - initialCapital);

  const payment = monthlyPayment(mortgagePrincipal, mortgageRate, months);
  const monthlyMaintenance = totalMaintenance / months;

  const rMortgage = mortgageRate / 100 / 12;
  const rStock = Math.pow(1 + stockYield / 100, 1 / 12) - 1;
  const rProperty = Math.pow(1 + appreciationRate / 100, 1 / 12) - 1;
  const rCPI = Math.pow(1 + cpiRate / 100, 1 / 12) - 1;
  const rRentInfl = rentInflation / 100;
  const rLeverage = leverageRate / 100 / 12;
  const loanAmount = mortgagePrincipal; // leverage loan sized to match the mortgage

  let mortgageBalance = mortgagePrincipal;
  let cumMortgageInterest = 0;
  let cumMaintenance = 0;
  let propertyValue = purchasePrice;

  let surplusPortfolio = surplus;
  let surplusBasis = surplus;

  let portfolioB = initialCapital;
  let basisB = initialCapital;

  let portfolioC = initialCapital + (leverageEnabled ? loanAmount : 0);
  let basisC = portfolioC;
  let cumLeverageInterest = 0;

  let cumRent = 0;
  const yearlyData = [];
  let firstMonthContribution = null;

  for (let m = 1; m <= months; m++) {
    const yearIndex = Math.floor((m - 1) / 12);
    const currentMonthlyRent = monthlyRent * Math.pow(1 + rRentInfl, yearIndex);

    if (mortgageBalance > 0) {
      const interestPortion = mortgageBalance * rMortgage;
      let principalPortion = payment - interestPortion;
      if (principalPortion > mortgageBalance) principalPortion = mortgageBalance;
      if (principalPortion < 0) principalPortion = 0;
      mortgageBalance = Math.max(0, mortgageBalance - principalPortion);
      cumMortgageInterest += interestPortion;
    }
    cumMaintenance += monthlyMaintenance;
    propertyValue *= 1 + rProperty;

    surplusPortfolio *= 1 + rStock;
    surplusBasis *= 1 + rCPI;

    const contribution = payment - currentMonthlyRent;
    if (firstMonthContribution === null) firstMonthContribution = contribution;

    portfolioB = portfolioB * (1 + rStock) + contribution;
    basisB = basisB * (1 + rCPI) + contribution;

    portfolioC = portfolioC * (1 + rStock) + contribution;
    basisC = basisC * (1 + rCPI) + contribution;
    if (leverageEnabled) cumLeverageInterest += loanAmount * rLeverage;

    cumRent += currentMonthlyRent;

    if (m % 12 === 0) {
      const yr = m / 12;

      const surplusGain = Math.max(0, surplusPortfolio - surplusBasis);
      const surplusTax = surplusGain * (capitalGainsTax / 100);
      const surplusNet = surplusPortfolio - surplusTax;
      const netA = propertyValue - mortgageBalance - cumMortgageInterest - cumMaintenance + surplusNet;

      const gainB = Math.max(0, portfolioB - basisB);
      const taxB = gainB * (capitalGainsTax / 100);
      const postTaxB = portfolioB - taxB;
      const netB = postTaxB - cumRent;

      const gainC = Math.max(0, portfolioC - basisC);
      const taxC = gainC * (capitalGainsTax / 100);
      const postTaxC = portfolioC - taxC;
      const leverageCost = leverageEnabled ? loanAmount + cumLeverageInterest : 0;
      const netC = postTaxC - cumRent - leverageCost;

      yearlyData.push({
        year: yr,
        RealEstate: Math.round(netA),
        Stocks: Math.round(netB),
        LeveragedStocks: Math.round(netC),
        propertyValue: Math.round(propertyValue),
        mortgageBalance: Math.round(mortgageBalance)
      });
    }
  }

  const final = yearlyData[yearlyData.length - 1] || { RealEstate: 0, Stocks: 0, LeveragedStocks: 0 };

  return {
    yearlyData,
    final,
    details: {
      mortgagePrincipal, downPayment, surplus, shortfall,
      monthlyPayment: payment, monthlyMaintenance,
      cumMortgageInterest, cumMaintenance, propertyValueFinal: propertyValue,
      mortgageBalanceFinal: mortgageBalance,
      cumRent, cumLeverageInterest, loanAmount,
      firstMonthContribution,
      taxPaidStocks: Math.max(0, portfolioB - basisB) * (capitalGainsTax / 100),
      taxPaidLeveraged: Math.max(0, portfolioC - basisC) * (capitalGainsTax / 100)
    }
  };
}
