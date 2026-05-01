# Energy Arbitrage Controller

A local manual-mode retail energy arbitrage controller for Brisbane, Queensland.

## Overview

This project implements a simple decision engine for battery energy arbitrage. It takes manual inputs (import price, export price, battery state of charge) and recommends an action: CHARGE, HOLD, or EXPORT.

## Decision Rules

- **CHARGE**: If import price ≤ $0.05/kWh AND battery SoC < 95%
- **CHARGE**: If import price is negative AND battery SoC < 95%
- **EXPORT**: If export price ≥ $0.30/kWh AND battery SoC > reserve SoC
- **HOLD**: Otherwise

### Reserve SoC

- Day (6 AM - 6 PM): 25%
- Night (6 PM - 6 AM): 55%

## Usage

```bash
cd energy_arbitrage
python -m src.main
```

## Testing

```bash
cd energy_arbitrage
python -m pytest tests/
```