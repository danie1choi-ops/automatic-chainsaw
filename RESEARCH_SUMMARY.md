# Research Summary

## 1. Original Hypothesis

The project began from the hypothesis that home battery arbitrage might be profitable in Queensland by harvesting NEM spot-price volatility. The initial question was whether a residential battery could charge during low or negative price intervals and export during high-price intervals often enough to justify battery cycling, degradation, and payback risk.

## 2. Modelling Path

The modelling path moved from simple control logic toward market-structure analysis:

- Manual decision engine: threshold-based charge, hold, and export decisions using import price, export price, battery state of charge, and reserve constraints.
- Historical backtest: replay of price intervals against the decision engine to estimate realised arbitrage outcomes.
- Battery degradation and payback: inclusion of throughput-linked degradation costs and simple payback framing.
- Real NEM price ingestion: use of historical QLD/NEM dispatch price data rather than only sample or synthetic price series.
- Solar/load modelling: household demand and rooftop solar profiles added to separate solar self-consumption value from incremental arbitrage value.
- FCAS/grid-scale concepts: simplified FCAS and stacked-revenue simulator introduced as a planning model for grid-scale battery revenue cases.
- Regime attribution: historical intervals classified into normal, volatile, negative-pricing, price-spike, and sustained high-price regimes to attribute realised profitability.
- Saturation simulation: analytical compression model added to test how increasing battery participation reduces per-battery arbitrage value.

## 3. Core Findings

Pure residential arbitrage is weak. The backtests show that arbitrage value is not evenly distributed through normal market operation; it depends heavily on rare volatility events.

Normal market periods were negative after degradation. In the regime study, the normal regime represented most intervals but had negative total profit once degradation was included.

Profitability was concentrated in rare price-spike regimes. Price spikes represented a very small share of time but accounted for most realised profitability.

Solar self-consumption dominates the residential value case. The solar/load model indicates that reducing retail grid imports is a more stable residential value driver than cycling solely for wholesale arbitrage. Arbitrage is best interpreted as a secondary overlay on top of solar/load management, not the core residential battery value proposition.

Saturation rapidly compresses the edge. Under the default saturation assumptions, additional battery participation materially reduced per-battery profitability, especially because many batteries target the same narrow price-spike export windows.

## 4. Quantitative Findings

- Price spikes represented 0.4% of intervals and contributed 85.6% of total profitability.
- The price-spike regime contributed 334.30 of total P&L in the regime study, equal to 85.6% of total profit.
- The normal regime represented 80.14% of intervals but produced -9.8623 total profit after degradation.
- Volatility-linked regimes contributed 103.1% of total profitability, implying that non-volatility regimes were a drag on aggregate results.
- Solar plus battery value was materially better than arbitrage-only because solar self-consumption reduced grid import costs before any incremental arbitrage overlay was considered.
- In the saturation study, per-battery profit fell from 390.4889 at 1 battery to 167.4727 at 10 batteries, a 57.1% decay under default assumptions.
- At 100 batteries, modelled per-battery profit turned negative at -12.7779 under the same assumptions.
- At 10,000 batteries, spike profitability fell from 334.30 to 0.07, effectively eliminating the spike-driven edge in the simplified model.

## 5. Interpretation

The project is best framed as battery market structure research focused on volatility harvesting, regime dependency, and saturation effects.

The main result is not that batteries cannot create value. Rather, the work shows that the source of value matters. Residential batteries appear more defensible when used for solar self-consumption and retail import avoidance, with arbitrage as an opportunistic secondary layer. Wholesale arbitrage alone is fragile because it depends on rare regimes and is vulnerable to degradation costs and crowding.

## 6. Limitations

- Dispatch model is simplified and threshold-based; it is not an optimiser.
- Degradation is simplified and mainly throughput-linked; it does not fully model chemistry, temperature, calendar ageing, depth-of-discharge effects, or warranty constraints.
- No real FCAS price integration has been implemented yet.
- Solar and household load profiles are synthetic and do not include weather, seasonality, occupancy variation, tariff diversity, or real smart-meter traces.
- Saturation assumptions are simplified and analytical; they do not use actual battery capacity additions, bidding behaviour, network constraints, or participant heterogeneity.
- Results are research outputs, not investment advice.

## 7. Future Research Directions

- Integrate real historical FCAS prices and separate raise/lower/regulation/contingency products.
- Test against real household load and rooftop solar data.
- Model EV charging and vehicle-to-home/vehicle-to-grid integration.
- Add VPP aggregation logic, fleet dispatch constraints, and household participation assumptions.
- Calibrate battery saturation using real capacity additions and observed market responses.
- Compare multiple years of NEM data to test whether the regime dependency persists across different market conditions.
