"""Performance metrics and analysis."""

from typing import List, Dict
from datetime import datetime
from src import config


def calculate_performance_metrics(results: List[Dict]) -> dict:
    """Calculate performance metrics from backtest results.
    
    Args:
        results: List of interval result dictionaries.
        
    Returns:
        Dictionary of performance metrics.
    """
    if not results:
        return {
            'total_profit': 0.0,
            'num_intervals': 0,
            'avg_profit_per_interval': 0.0,
            'sharpe_ratio': 0.0,
        }
    
    total_profit = sum(r.get('cashflow', 0) for r in results)
    num_intervals = len(results)
    avg_profit = total_profit / num_intervals if num_intervals > 0 else 0
    
    # Calculate standard deviation of profits
    profits = [r.get('cashflow', 0) for r in results]
    variance = sum((p - avg_profit) ** 2 for p in profits) / num_intervals
    std_dev = variance ** 0.5
    
    # Simple Sharpe-like ratio (annualized for 5-min intervals)
    # 5-min intervals * 12 * 24 * 365 = 105,120 intervals/year
    intervals_per_year = 12 * 24 * 365
    if std_dev > 0:
        sharpe_ratio = (avg_profit * intervals_per_year) / (std_dev * (intervals_per_year ** 0.5))
    else:
        sharpe_ratio = 0.0
    
    return {
        'total_profit': total_profit,
        'num_intervals': num_intervals,
        'avg_profit_per_interval': avg_profit,
        'std_dev': std_dev,
        'sharpe_ratio': sharpe_ratio,
    }


def calculate_investment_metrics(backtest_results: dict, price_data: List) -> dict:
    """Calculate investment metrics for battery payback analysis.
    
    Args:
        backtest_results: Dictionary from run_backtest().
        price_data: List of PricePoint objects from the backtest.
        
    Returns:
        Dictionary with investment metrics.
    """
    net_profit = backtest_results['net_profit']
    num_intervals = backtest_results['num_intervals']
    
    # Calculate days in dataset
    if len(price_data) > 0:
        first_timestamp = price_data[0].timestamp
        last_timestamp = price_data[-1].timestamp
        days_in_dataset = (last_timestamp - first_timestamp).total_seconds() / (24 * 3600)
        # Ensure at least 1 day for annualization
        if days_in_dataset < 1:
            days_in_dataset = 1
    else:
        days_in_dataset = 1
    
    # Annualize profit
    annual_net_profit = net_profit * (365 / days_in_dataset)
    
    # Calculate simple payback
    if annual_net_profit > 0:
        simple_payback_years = config.TOTAL_BATTERY_SYSTEM_COST / annual_net_profit
    else:
        simple_payback_years = "Never"
    
    return {
        'net_profit': net_profit,
        'days_in_dataset': days_in_dataset,
        'annual_net_profit': annual_net_profit,
        'simple_payback_years': simple_payback_years,
    }


def print_investment_summary(backtest_results: dict, investment_metrics: dict):
    """Print investment payback analysis.
    
    Args:
        backtest_results: Dictionary from run_backtest().
        investment_metrics: Dictionary from calculate_investment_metrics().
    """
    print("\n" + "=" * 60)
    print("INVESTMENT ANALYSIS")
    print("=" * 60)
    print(f"Gross Profit:              ${backtest_results['total_gross_profit']:.2f}")
    print(f"Degradation Cost:          ${backtest_results['total_degradation_cost']:.2f}")
    print(f"Net Profit:                ${investment_metrics['net_profit']:.2f}")
    print("-" * 60)
    print(f"Charged kWh:               {backtest_results['total_charged_kwh']:.2f} kWh")
    print(f"Exported kWh:              {backtest_results['total_exported_kwh']:.2f} kWh")
    print(f"Equivalent Cycles:         {backtest_results['equivalent_cycles']:.2f}")
    print(f"Ending SoC:                {backtest_results['ending_soc']:.1f}%")
    print("-" * 60)
    print(f"Dataset Period:            {investment_metrics['days_in_dataset']:.1f} days")
    print(f"Annualized Net Profit:     ${investment_metrics['annual_net_profit']:.2f}/year")
    print("-" * 60)
    print(f"Battery System Cost:       ${config.TOTAL_BATTERY_SYSTEM_COST:,.0f}")
    if isinstance(investment_metrics['simple_payback_years'], str):
        print(f"Simple Payback:            {investment_metrics['simple_payback_years']}")
    else:
        print(f"Simple Payback:            {investment_metrics['simple_payback_years']:.1f} years")
    print("=" * 60)
    print("⚠️  WARNING: Sample data is synthetic. Do not use this result")
    print("             for a battery purchase decision.")
    print("=" * 60)


def print_performance_summary(metrics: dict):
    """Print a performance summary.
    
    Args:
        metrics: Dictionary of performance metrics.
    """
    print("\n" + "=" * 40)
    print("PERFORMANCE SUMMARY")
    print("=" * 40)
    print(f"Total Profit:        ${metrics['total_profit']:.2f}")
    print(f"Intervals:           {metrics['num_intervals']}")
    print(f"Avg Profit/Interval: ${metrics['avg_profit_per_interval']:.4f}")
    print(f"Std Dev:             ${metrics['std_dev']:.4f}")
    print(f"Sharpe Ratio:        {metrics['sharpe_ratio']:.2f}")
    print("=" * 40)