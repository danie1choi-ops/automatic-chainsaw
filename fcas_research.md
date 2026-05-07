# FCAS Research: Australian NEM and Grid-Scale Battery Opportunity

## 1. What FCAS is in the NEM

Frequency Control Ancillary Services (FCAS) are market services in the National Electricity Market (NEM) that maintain system frequency and secure power system stability. FCAS markets procure capability and response across contingency and regulation categories: raise/lower and fast/slow services. In the NEM, providers bid into 5-minute dispatch and 30-minute settlement frameworks, with separate markets for contingency services (e.g. 6-second, 60-second, 5-minute) and frequency control (`regulation raise` and `regulation lower`).

## 2. Why grid-scale batteries make money from FCAS

Grid-scale batteries can provide FCAS because they can change active power output rapidly and precisely. Key economic attributes:

- fast response: batteries can dispatch within seconds, matching fast FCAS requirements
- bidirectional capability: they can both raise and lower power, allowing participation in both raise and lower markets
- state-of-charge flexibility: if managed correctly, a battery can offer repeated reversals without fuel

Revenue from FCAS arises from capacity payments for being available and from energy settlement when instructed by the market operator. Batteries can capture both the availability premium and the energy response premium if they are scheduled and dispatched effectively.

## 3. Difference between FCAS and energy arbitrage

Energy arbitrage is the purchase of energy at low price times and sale at high price times. It depends on price spread, round-trip efficiency, and energy capacity.

FCAS is a service market for maintaining frequency, not for bulk energy transfer. Primary differences:

- objective: arbitrage seeks energy price differential; FCAS seeks ancillary service availability and fast response
- dispatch signal: arbitrage follows price-driven energy dispatch; FCAS follows system frequency and contingency triggers
- revenues: arbitrage revenue is energy price spread; FCAS revenue is availability/reserve payments plus response energy
- asset requirements: FCAS favors high ramp rate and low latency; arbitrage favors energy capacity and efficient cycling

## 4. Why residential batteries struggle economically

Residential batteries face several structural disadvantages compared to grid-scale assets:

- smaller capacity: limited energy and power reduces revenue per asset and increases relative fixed costs
- higher cost base: unit capital and operating costs are typically higher for residential installations
- weaker market access: residential systems rarely participate directly in FCAS or wholesale ancillary service markets
- limited dispatch optimization: residential optimisation focuses on self-consumption and retail tariffs rather than active market participation
- tariff and regulatory constraints: export limits, retail tariffs, and non-export policies reduce effective revenue opportunities

As a result, residential systems are usually better suited to load shifting and self-consumption rather than direct market-based arbitrage or FCAS participation.

## 5. Revenue stacking

Revenue stacking refers to combining multiple value streams for one asset. For batteries, relevant stacks include:

- arbitrage: buying low and selling high in the energy market, or reducing retail import cost through price-responsive dispatch
- FCAS: offering frequency control services to the system operator, capturing reserve capacity and response energy payments
- VPPs: aggregating many distributed batteries into a Virtual Power Plant to provide capacity or energy services at scale
- demand response: reducing or shifting consumption in response to price signals or network constraints, often through retail or network programs

A grid-scale battery can operate simultaneously in these domains if scheduling and state-of-charge management maintain operational readiness. Effective stacking requires co-optimization to avoid conflicts between services.

## 6. Typical grid-scale battery durations

Grid-scale battery projects are often described by nominal duration at rated power:

- 1-hour duration: optimized for fast reserve and short-duration price volatility; common for FCAS and peak shaving
- 2-hour duration: common for energy arbitrage and summer peak support; provides a balance between capacity and response
- 4-hour duration: more appropriate for daily energy shifting, evening peak coverage, and longer-duration ancillary services

Longer durations increase stored energy capacity but also raise capital cost and may reduce cycling frequency per MWh. Short-duration assets typically excel in fast-response services like regulation and contingency FCAS.

## 7. Key risks

Important risks for battery FCAS and arbitrage modelling include:

- degradation: battery capacity and efficiency decline with cycling and calendar aging, changing revenue potential and operating strategy
- FCAS saturation: if too many providers offer the same FCAS product, clearing prices can fall and revenue may compress
- declining spreads: energy arbitrage depends on price volatility; lower wholesale price spreads reduce arbitrage value and can make stacked services essential

Additional risks include regulatory changes, market design adjustments, and the potential for congestion or network constraints to alter dispatch outcomes.

## 8. Ideas for future modelling in this repo

Possible modelling extensions for this repository:

- co-optimization framework for simultaneous arbitrage and FCAS participation, with explicit state-of-charge reservation
- degradation-aware dispatch that tracks cycle depth, energy throughput, and capacity fade over time
- stochastic FCAS price modelling using historical contingency and regulation market outcomes
- VPP-style aggregation modelling for distributed batteries, with aggregated capacity offers and response coordination
- demand-response integration to simulate residential or commercial load reduction as a complementary revenue stream
- duration and product sensitivity analysis for 1h/2h/4h batteries under varying price spread and FCAS saturation scenarios
- comparative analysis of wholesale energy vs ancillary service revenue under NEM market rules
