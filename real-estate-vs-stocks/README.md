# Buy vs. Rent & Invest — Wealth Simulator

A single-page React + Tailwind CSS app that compares three long-term wealth-building
paths over a configurable horizon (default 20 years):

- **Buy a Home** — mortgage-financed primary residence, benefiting from Israeli-style
  0% capital-gains / purchase-tax exemption on a single primary residence.
- **Rent + Invest (Unleveraged)** — invest initial capital in the stock market
  (S&P 500 / global index) and rent instead of buying, paying 25% tax on real
  (inflation-adjusted) capital gains at exit.
- **Rent + Invest (Leveraged)** — same as above, plus a loan sized to match the
  mortgage, invested alongside the initial capital, with loan interest and
  principal deducted at exit.

All parameters (capital, prices, rates, rent, taxes, leverage) are adjustable via
sliders/inputs, with results shown as summary cards, a year-by-year wealth chart, and
an auto-generated insights panel explaining the outcome.

## Run locally

```bash
npm install
npm run dev       # start the dev server
npm run build     # production build to dist/
npm run preview   # preview the production build
```

## Stack

React 18, Tailwind CSS, Recharts, Vite.
