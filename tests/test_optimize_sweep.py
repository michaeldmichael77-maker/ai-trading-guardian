"""Smoke tests for the offline parameter-sweep tool (kept fast)."""

from trading_bot.optimize_sweep import (
    evaluate, run_sweep, walk_forward, compare, current_config_params)


def test_evaluate_returns_metrics():
    params = {"min_confidence": 0.60, "take_profit_r": 0.0,
              "trail_activate_r": 1.0, "trail_giveback": 0.5}
    m = evaluate(params, ticks=120, seeds=[1, 7])
    for key in ("mean_return", "mean_sharpe", "mean_win", "mean_pf",
                "worst_return"):
        assert key in m


def test_evaluate_restores_global_config():
    import trading_bot.config as cfg
    before = cfg.MIN_CONFIDENCE
    evaluate({"min_confidence": 0.99, "take_profit_r": 0.0,
              "trail_activate_r": 1.0, "trail_giveback": 0.5},
             ticks=60, seeds=[1])
    assert cfg.MIN_CONFIDENCE == before   # must not leak global mutation


def test_run_sweep_is_ranked_and_bounded():
    top = run_sweep(ticks=80, seeds=[1, 7], top=3)
    assert len(top) == 3
    # sorted by mean_sharpe descending
    sharpes = [m["mean_sharpe"] for _, m in top]
    assert sharpes == sorted(sharpes, reverse=True)


def test_walk_forward_returns_train_and_test_metrics():
    params, train_m, test_m = walk_forward(
        ticks=80, train_seeds=[1, 7], test_seeds=[42])
    # chosen params must be a valid grid point
    assert set(params.keys()) == {"min_confidence", "take_profit_r",
                                  "trail_activate_r", "trail_giveback"}
    for m in (train_m, test_m):
        assert "mean_sharpe" in m and "mean_return" in m


def test_walk_forward_restores_global_config():
    import trading_bot.config as cfg
    before = cfg.MIN_CONFIDENCE
    walk_forward(ticks=60, train_seeds=[1], test_seeds=[7])
    assert cfg.MIN_CONFIDENCE == before


def test_current_config_params_reflects_config():
    import trading_bot.config as cfg
    p = current_config_params()
    assert p["min_confidence"] == cfg.MIN_CONFIDENCE
    assert p["take_profit_r"] == cfg.TAKE_PROFIT_R


def test_compare_returns_current_and_best():
    cur, cur_m, best, best_m = compare(ticks=80, seeds=[1, 7])
    assert "mean_sharpe" in cur_m and "mean_sharpe" in best_m
    # best is selected as the top of the sweep, so its sharpe >= current's
    assert best_m["mean_sharpe"] >= cur_m["mean_sharpe"] - 1e-9
