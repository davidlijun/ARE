import numpy as np
import matplotlib.pyplot as plt
from alpha_research.ef_utils import (
    annualized_return_covariance,
    build_cml,
    compute_portfolio_metrics,
    download_price_data,
    extract_efficient_frontier,
    market_cap,
    simulate_random_portfolios,
)

DEFAULT_TICKERS = ["AAPL", "MSFT", "GOOG", "AMZN", "NVDA"]
color_list = ['red', 'blue', 'green', 'orange', 'purple', 'cyan', 'magenta', 'yellow', 'black', 'brown']
RF_RATE = 0.045
START_DATE = "2020-01-01"
NUM_PORTFOLIOS = 100_000


def plot_efficient_frontier(
    tickers,
    results,
    stock_returns,
    stock_vols,
    opt_return,
    opt_vol,
    eq_return,
    eq_vol,
    mkt_return,
    mkt_vol,
    ef_frontier,
    cml_x,
    cml_y,
):
    plt.figure(figsize=(10, 6))

    plt.scatter(
        results["Volatility"],
        results["Return"],
        c=results["Sharpe"],
        s=1,
        cmap="viridis",
        alpha=0.3,
    )
    plt.colorbar(label="Sharpe Ratio")

    plt.scatter(stock_vols, stock_returns, color = color_list[:len(tickers)], s=80, label="Individual Stocks")
    for i, ticker in enumerate(tickers):
        plt.annotate(
            ticker,
            (stock_vols[i], stock_returns[i]),
            textcoords="offset points",
            color=color_list[i],
            xytext=(5, 5),
            fontsize=9,
        )

    plt.scatter(opt_vol, opt_return, color="red", marker="*", s=200, label="Max Sharpe")
    plt.scatter(eq_vol, eq_return, color="orange", s=100, label="Equal Weight")
    plt.scatter(mkt_vol, mkt_return, color="purple", s=100, label="Market Cap")

    plt.plot(ef_frontier["Volatility"], ef_frontier["Return"], color="red", linewidth=3, label="Efficient Frontier")
    plt.plot(cml_x, cml_y, "--", color="blue", linewidth=2, label="CML")
    plt.scatter(0, RF_RATE, color="black", label="Risk-Free = {}%".format(int(RF_RATE * 100)), zorder=5)

    plt.title("Efficient Frontier Portfolio Comparison")
    plt.xlabel("Volatility")
    plt.ylabel("Expected Return")
    plt.legend()
    plt.show()


def print_summary(tickers, opt_return, opt_vol, opt_sharpe, opt_weights, eq_return, eq_vol, eq_sharpe, mkt_return, mkt_vol, mkt_sharpe):
    print("=== Portfolio Comparison ===\n")
    print("Optimized (Max Sharpe):")
    print("Return:", round(opt_return, 3))
    print("Volatility:", round(opt_vol, 3))
    print("Sharpe:", round(opt_sharpe, 3))
    print("Weights:", dict(zip(tickers, np.round(opt_weights, 3))))
    print()
    print("Equal Weight:")
    print("Return:", round(eq_return, 3))
    print("Volatility:", round(eq_vol, 3))
    print("Sharpe:", round(eq_sharpe, 3))
    print()
    print("Market Cap Weight:")
    print("Return:", round(mkt_return, 3))
    print("Volatility:", round(mkt_vol, 3))
    print("Sharpe:", round(mkt_sharpe, 3))


def main():
    prices = download_price_data(DEFAULT_TICKERS, START_DATE)
    mean_returns, cov_matrix, _ = annualized_return_covariance(prices)

    results, random_weights = simulate_random_portfolios(
        mean_returns, cov_matrix, NUM_PORTFOLIOS, RF_RATE
    )
    max_idx = results["Sharpe"].idxmax()
    opt_weights = random_weights[max_idx]
    opt_return, opt_vol, opt_sharpe = compute_portfolio_metrics(
        opt_weights, mean_returns, cov_matrix, RF_RATE
    )

    equal_weights = np.repeat(1 / len(DEFAULT_TICKERS), len(DEFAULT_TICKERS))
    eq_return, eq_vol, eq_sharpe = compute_portfolio_metrics(
        equal_weights, mean_returns, cov_matrix, RF_RATE
    )

    _, market_weights = market_cap(DEFAULT_TICKERS)
    mkt_return, mkt_vol, mkt_sharpe = compute_portfolio_metrics(
        market_weights, mean_returns, cov_matrix, RF_RATE
    )

    ef_frontier = extract_efficient_frontier(results)
    cml_x, cml_y = build_cml(opt_return, opt_vol, RF_RATE)

    stock_returns = mean_returns
    stock_vols = np.sqrt(np.diag(cov_matrix))

    plot_efficient_frontier(
        DEFAULT_TICKERS,
        results,
        stock_returns,
        stock_vols,
        opt_return,
        opt_vol,
        eq_return,
        eq_vol,
        mkt_return,
        mkt_vol,
        ef_frontier,
        cml_x,
        cml_y,
    )

    print_summary(
        DEFAULT_TICKERS,
        opt_return,
        opt_vol,
        opt_sharpe,
        opt_weights,
        eq_return,
        eq_vol,
        eq_sharpe,
        mkt_return,
        mkt_vol,
        mkt_sharpe,
    )


if __name__ == "__main__":
    main()
