# Quantitative Engine Backtest: Detailed (Rolling 6-Month)

**Test Period:** 2026-01-01 to 2026-06-11
**Samples:** 110 Trading Periods

## Performance Summary
- **Portfolio Win Rate (Edge Accuracy):** 41.3%
- **Crash Protection Rate:** 100.0% (6/6 major dips avoided)
- **Average Kelly Allocation:** 0.013

## Deep Learning Probability Calibration
| Probability Bucket | Occurrences | Win Rate | Avg Forward Return |
|--------------------|-------------|----------|--------------------|
| 0-20% | 67 | 10.4% | -0.056% |
| 20-40% | 5 | 20.0% | -0.075% |
| 40-60% | 3 | 0.0% | 0.000% |
| 60-80% | 2 | 0.0% | -0.042% |
| 80-100% | 33 | 51.5% | 0.220% |


## Simulated Trading Ledger Analysis (Continuous Compounding)
- **Mock Execution PnL:** -6.49% (Total Equity: $9,350.52)
- **Total Executed Rotations:** 27
- **Total Slippage/Fees Paid:** $284.10


## Detailed Daily Log
| Date | SPX Close | HMM Regime | Kalman State | Ensemble Prob | Consensus | SPX Kelly | Short Kelly | BTC Kelly | GLD Kelly | WTI Kelly | Cash | Portfolio 5D PnL |
|------|-----------|------------|--------------|---------------|-----------|-----------|-------------|-----------|-----------|-----------|------|------------------|
| 2026-01-02 | 6858.47021484375 | NEUTRAL_TRANSITIONAL | transitional | 0.987 | 1.0 | 0.033 | 0.0 | 0.167 | 0.167 | 0.167 | 0.0 | 0.130% |
| 2026-01-05 | 6902.0498046875 | NEUTRAL_TRANSITIONAL | transitional | 0.922 | 1.0 | 0.065 | 0.0 | 0.162 | 0.162 | 0.162 | 0.0 | -0.578% |
| 2026-01-06 | 6944.81982421875 | NEUTRAL_TRANSITIONAL | transitional | 1.000 | 1.0 | 0.065 | 0.0 | 0.162 | 0.162 | 0.162 | 0.0 | -0.085% |
| 2026-01-07 | 6920.93017578125 | NEUTRAL_TRANSITIONAL | transitional | 0.000 | 1.0 | 0.0 | 0.6 | 0.0 | 0.24 | 0.0 | 0.16 | 0.350% |
| 2026-01-08 | 6921.4599609375 | NEUTRAL_TRANSITIONAL | transitional | 0.545 | 1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1.0 | 0.000% |
| 2026-01-09 | 6966.27978515625 | NEUTRAL_TRANSITIONAL | transitional | 0.000 | 1.0 | 0.0 | 0.6 | 0.0 | 0.24 | 0.0 | 0.16 | 0.000% |
| 2026-01-12 | 6977.27001953125 | NEUTRAL_TRANSITIONAL | transitional | 0.000 | 1.0 | 0.0 | 0.6 | 0.0 | 0.24 | 0.0 | 0.16 | 0.000% |
| 2026-01-13 | 6963.740234375 | NEUTRAL_TRANSITIONAL | transitional | 0.401 | 1.0 | 0.0 | 0.143 | 0.0 | 0.057 | 0.0 | 0.8 | 0.000% |
| 2026-01-14 | 6926.60009765625 | NEUTRAL_TRANSITIONAL | transitional | 0.256 | 1.0 | 0.2 | 0.0 | 0.2 | 0.2 | 0.2 | 0.0 | -0.627% |
| 2026-01-15 | 6944.47021484375 | NEUTRAL_TRANSITIONAL | transitional | 0.323 | 1.0 | 0.0 | 0.185 | 0.0 | 0.074 | 0.0 | 0.741 | 0.658% |
| 2026-01-16 | 6940.009765625 | NEUTRAL_TRANSITIONAL | transitional | 0.000 | 1.0 | 0.0 | 0.36 | 0.0 | 0.144 | 0.0 | 0.496 | 0.000% |
| 2026-01-20 | 6796.85986328125 | NEUTRAL_TRANSITIONAL | transitional | 0.000 | 1.0 | 0.0 | 0.36 | 0.0 | 0.144 | 0.0 | 0.496 | 0.000% |
| 2026-01-21 | 6875.6201171875 | NEUTRAL_TRANSITIONAL | transitional | 0.994 | 1.0 | 0.0 | 0.0 | 0.171 | 0.171 | 0.171 | 0.0 | -0.750% |
| 2026-01-22 | 6913.35009765625 | NEUTRAL_TRANSITIONAL | transitional | 0.000 | 1.0 | 0.0 | 0.36 | 0.0 | 0.144 | 0.0 | 0.496 | -0.028% |
| 2026-01-23 | 6915.60986328125 | NEUTRAL_TRANSITIONAL | transitional | 0.000 | 1.0 | 0.0 | 0.36 | 0.0 | 0.144 | 0.0 | 0.496 | 0.000% |
| 2026-01-26 | 6950.22998046875 | NEUTRAL_TRANSITIONAL | transitional | 0.989 | 1.0 | 0.068 | 0.0 | 0.162 | 0.162 | 0.162 | 0.0 | -1.906% |
| 2026-01-27 | 6978.60009765625 | NEUTRAL_TRANSITIONAL | transitional | 0.936 | 1.0 | 0.074 | 0.0 | 0.161 | 0.161 | 0.161 | 0.0 | -2.204% |
| 2026-01-28 | 6978.02978515625 | NEUTRAL_TRANSITIONAL | transitional | 0.996 | 1.0 | 0.105 | 0.0 | 0.156 | 0.156 | 0.156 | 0.0 | -5.501% |
| 2026-01-29 | 6969.009765625 | NEUTRAL_TRANSITIONAL | transitional | 0.000 | 1.0 | 0.0 | 0.36 | 0.0 | 0.144 | 0.0 | 0.496 | 0.690% |
| 2026-01-30 | 6939.02978515625 | NEUTRAL_TRANSITIONAL | transitional | 0.002 | 1.0 | 0.0 | 0.359 | 0.0 | 0.144 | 0.0 | 0.497 | 0.000% |
| 2026-02-02 | 6976.43994140625 | NEUTRAL_TRANSITIONAL | transitional | 1.000 | 1.0 | 0.028 | 0.0 | 0.167 | 0.167 | 0.167 | 0.0 | -1.402% |
| 2026-02-03 | 6917.81005859375 | NEUTRAL_TRANSITIONAL | transitional | 0.990 | 1.0 | 0.0 | 0.0 | 0.171 | 0.171 | 0.171 | 0.0 | -0.645% |
| 2026-02-04 | 6882.72021484375 | NEUTRAL_TRANSITIONAL | transitional | 0.002 | 1.0 | 0.0 | 0.359 | 0.0 | 0.144 | 0.0 | 0.497 | -0.317% |
| 2026-02-05 | 6798.39990234375 | NEUTRAL_TRANSITIONAL | transitional | 0.001 | 1.0 | 0.0 | 0.359 | 0.0 | 0.144 | 0.0 | 0.497 | 0.104% |
| 2026-02-06 | 6932.2998046875 | NEUTRAL_TRANSITIONAL | transitional | 1.000 | 1.0 | 0.104 | 0.0 | 0.157 | 0.157 | 0.157 | 0.0 | -0.519% |
| 2026-02-09 | 6964.81982421875 | NEUTRAL_TRANSITIONAL | transitional | 0.176 | 1.0 | 0.0 | 0.265 | 0.0 | 0.106 | 0.0 | 0.629 | 0.000% |
| 2026-02-10 | 6941.81005859375 | NEUTRAL_TRANSITIONAL | transitional | 0.000 | 1.0 | 0.0 | 0.36 | 0.0 | 0.144 | 0.0 | 0.496 | 0.000% |
| 2026-02-11 | 6941.47021484375 | NEUTRAL_TRANSITIONAL | transitional | 0.106 | 1.0 | 0.0 | 0.303 | 0.0 | 0.121 | 0.0 | 0.576 | 0.000% |
| 2026-02-12 | 6832.759765625 | NEUTRAL_TRANSITIONAL | transitional | 0.000 | 1.0 | 0.0 | 0.36 | 0.0 | 0.144 | 0.0 | 0.496 | -0.436% |
| 2026-02-13 | 6836.169921875 | NEUTRAL_TRANSITIONAL | transitional | 1.000 | 1.0 | 0.0 | 0.0 | 0.171 | 0.171 | 0.171 | 0.0 | -0.819% |
| 2026-02-17 | 6843.22021484375 | NEUTRAL_TRANSITIONAL | transitional | 0.951 | 1.0 | 0.0 | 0.0 | 0.171 | 0.171 | 0.171 | 0.0 | 0.318% |
| 2026-02-18 | 6881.31005859375 | NEUTRAL_TRANSITIONAL | transitional | 0.999 | 1.0 | 0.0 | 0.0 | 0.171 | 0.171 | 0.171 | 0.0 | -0.797% |
| 2026-02-19 | 6861.89013671875 | NEUTRAL_TRANSITIONAL | transitional | 0.000 | 1.0 | 0.0 | 0.36 | 0.0 | 0.144 | 0.0 | 0.496 | 0.376% |
| 2026-02-20 | 6909.509765625 | NEUTRAL_TRANSITIONAL | transitional | 0.296 | 1.0 | 0.0 | 0.2 | 0.0 | 0.08 | 0.0 | 0.72 | 0.000% |
| 2026-02-23 | 6837.75 | NEUTRAL_TRANSITIONAL | transitional | 0.139 | 1.0 | 0.0 | 0.285 | 0.0 | 0.114 | 0.0 | 0.601 | 0.000% |
| 2026-02-24 | 6890.06982421875 | NEUTRAL_TRANSITIONAL | transitional | 0.042 | 1.0 | 0.0 | 0.337 | 0.0 | 0.135 | 0.0 | 0.528 | 0.000% |
| 2026-02-25 | 6946.1298828125 | NEUTRAL_TRANSITIONAL | transitional | 1.000 | 1.0 | 0.014 | 0.0 | 0.169 | 0.169 | 0.169 | 0.0 | 6.044% |
| 2026-02-26 | 6908.85986328125 | NEUTRAL_TRANSITIONAL | transitional | 1.000 | 1.0 | 0.014 | 0.0 | 0.169 | 0.169 | 0.169 | 0.0 | 1.562% |
| 2026-02-27 | 6878.8798828125 | NEUTRAL_TRANSITIONAL | transitional | 0.000 | 1.0 | 0.0 | 0.36 | 0.0 | 0.144 | 0.0 | 0.496 | 0.000% |
| 2026-03-02 | 6881.6201171875 | NEUTRAL_TRANSITIONAL | transitional | 0.999 | 1.0 | 0.0 | 0.0 | 0.171 | 0.171 | 0.171 | 0.0 | -0.256% |
| 2026-03-03 | 6816.6298828125 | NEUTRAL_TRANSITIONAL | transitional | 1.000 | 1.0 | 0.0 | 0.0 | 0.171 | 0.171 | 0.171 | 0.0 | -1.585% |
| 2026-03-04 | 6869.5 | NEUTRAL_TRANSITIONAL | transitional | 1.000 | 1.0 | 0.0 | 0.0 | 0.171 | 0.171 | 0.171 | 0.0 | 1.916% |
| 2026-03-05 | 6830.7099609375 | NEUTRAL_TRANSITIONAL | transitional | 0.000 | 1.0 | 0.0 | 0.36 | 0.0 | 0.144 | 0.0 | 0.496 | 0.012% |
| 2026-03-06 | 6740.02001953125 | NEUTRAL_TRANSITIONAL | transitional | 0.000 | 1.0 | 0.0 | 0.36 | 0.0 | 0.144 | 0.0 | 0.496 | 0.000% |
| 2026-03-09 | 6795.990234375 | NEUTRAL_TRANSITIONAL | transitional | 1.000 | 1.0 | 0.0 | 0.0 | 0.171 | 0.171 | 0.171 | 0.0 | 0.315% |
| 2026-03-10 | 6781.47998046875 | NEUTRAL_TRANSITIONAL | transitional | 0.000 | 1.0 | 0.0 | 0.36 | 0.0 | 0.144 | 0.0 | 0.496 | 0.000% |
| 2026-03-11 | 6775.7998046875 | NEUTRAL_TRANSITIONAL | transitional | 0.004 | 1.0 | 0.0 | 0.358 | 0.0 | 0.143 | 0.0 | 0.499 | -0.484% |
| 2026-03-12 | 6672.6201171875 | NEUTRAL_TRANSITIONAL | transitional | 0.000 | 1.0 | 0.0 | 0.36 | 0.0 | 0.144 | 0.0 | 0.496 | -0.602% |
| 2026-03-13 | 6632.18994140625 | NEUTRAL_TRANSITIONAL | transitional | 0.007 | 1.0 | 0.0 | 0.356 | 0.0 | 0.142 | 0.0 | 0.502 | 0.000% |
| 2026-03-16 | 6699.3798828125 | NEUTRAL_TRANSITIONAL | transitional | 0.000 | 1.0 | 0.0 | 0.36 | 0.0 | 0.144 | 0.0 | 0.496 | 0.000% |
| 2026-03-17 | 6716.08984375 | NEUTRAL_TRANSITIONAL | transitional | 0.015 | 1.0 | 0.0 | 0.352 | 0.0 | 0.141 | 0.0 | 0.507 | 0.000% |
| 2026-03-18 | 6624.7001953125 | NEUTRAL_TRANSITIONAL | transitional | 0.097 | 1.0 | 0.0 | 0.308 | 0.0 | 0.123 | 0.0 | 0.569 | -0.407% |
| 2026-03-19 | 6606.490234375 | NEUTRAL_TRANSITIONAL | transitional | 0.007 | 1.0 | 0.0 | 0.356 | 0.0 | 0.142 | 0.0 | 0.502 | -0.805% |
| 2026-03-20 | 6506.47998046875 | NEUTRAL_TRANSITIONAL | transitional | 0.000 | 1.0 | 0.0 | 0.36 | 0.0 | 0.144 | 0.0 | 0.496 | 0.000% |
| 2026-03-23 | 6581.0 | NEUTRAL_TRANSITIONAL | transitional | 0.000 | 1.0 | 0.0 | 0.36 | 0.0 | 0.144 | 0.0 | 0.496 | 0.000% |
| 2026-03-24 | 6556.3701171875 | NEUTRAL_TRANSITIONAL | transitional | 0.001 | 1.0 | 0.0 | 0.359 | 0.0 | 0.144 | 0.0 | 0.497 | 0.000% |
| 2026-03-25 | 6591.89990234375 | NEUTRAL_TRANSITIONAL | transitional | 0.000 | 1.0 | 0.0 | 0.36 | 0.0 | 0.144 | 0.0 | 0.496 | 1.237% |
| 2026-03-26 | 6477.16015625 | NEUTRAL_TRANSITIONAL | transitional | 0.000 | 1.0 | 0.0 | 0.36 | 0.0 | 0.144 | 0.0 | 0.496 | -0.404% |
| 2026-03-27 | 6368.85009765625 | NEUTRAL_TRANSITIONAL | transitional | 0.000 | 1.0 | 0.0 | 0.36 | 0.0 | 0.144 | 0.0 | 0.496 | 0.000% |
| 2026-03-30 | 6343.72021484375 | NEUTRAL_TRANSITIONAL | transitional | 0.039 | 1.0 | 0.0 | 0.339 | 0.0 | 0.136 | 0.0 | 0.525 | 0.000% |
| 2026-03-31 | 6528.52001953125 | NEUTRAL_TRANSITIONAL | transitional | 0.000 | 1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1.0 | 0.000% |
| 2026-04-01 | 6575.31982421875 | NEUTRAL_TRANSITIONAL | transitional | 0.091 | 1.0 | 0.0 | 0.311 | 0.0 | 0.124 | 0.0 | 0.565 | -0.124% |
| 2026-04-02 | 6582.68994140625 | NEUTRAL_TRANSITIONAL | transitional | 1.000 | 1.0 | 0.0 | 0.0 | 0.171 | 0.171 | 0.171 | 0.0 | 1.280% |
| 2026-04-06 | 6611.830078125 | NEUTRAL_TRANSITIONAL | transitional | 1.000 | 1.0 | 0.055 | 0.0 | 0.164 | 0.164 | 0.164 | 0.0 | 0.254% |
| 2026-04-07 | 6616.85009765625 | NEUTRAL_TRANSITIONAL | transitional | 0.777 | 1.0 | 0.08 | 0.0 | 0.16 | 0.16 | 0.16 | 0.0 | -0.083% |
| 2026-04-08 | 6782.81005859375 | NEUTRAL_TRANSITIONAL | transitional | 0.000 | 1.0 | 0.0 | 0.36 | 0.0 | 0.144 | 0.0 | 0.496 | -0.474% |
| 2026-04-09 | 6824.66015625 | NEUTRAL_TRANSITIONAL | transitional | 0.220 | 1.0 | 0.0 | 0.241 | 0.0 | 0.096 | 0.0 | 0.663 | -0.405% |
| 2026-04-10 | 6816.89013671875 | NEUTRAL_TRANSITIONAL | transitional | 0.859 | 1.0 | 0.068 | 0.0 | 0.162 | 0.162 | 0.162 | 0.0 | 0.388% |
| 2026-04-13 | 6886.240234375 | NEUTRAL_TRANSITIONAL | transitional | 1.000 | 1.0 | 0.055 | 0.0 | 0.164 | 0.164 | 0.164 | 0.0 | 0.341% |
| 2026-04-14 | 6967.3798828125 | NEUTRAL_TRANSITIONAL | transitional | 0.000 | 1.0 | 0.0 | 0.36 | 0.0 | 0.144 | 0.0 | 0.496 | 0.000% |
| 2026-04-15 | 7022.9501953125 | NEUTRAL_TRANSITIONAL | transitional | 0.001 | 1.0 | 0.0 | 0.575 | 0.0 | 0.23 | 0.0 | 0.195 | -0.452% |
| 2026-04-16 | 7041.27978515625 | NEUTRAL_TRANSITIONAL | transitional | 0.019 | 1.0 | 0.0 | 0.35 | 0.0 | 0.14 | 0.0 | 0.51 | -0.154% |
| 2026-04-17 | 7126.06005859375 | NEUTRAL_TRANSITIONAL | transitional | 0.000 | 1.0 | 0.0 | 0.36 | 0.0 | 0.144 | 0.0 | 0.496 | 0.000% |
| 2026-04-20 | 7109.14013671875 | NEUTRAL_TRANSITIONAL | transitional | 0.004 | 1.0 | 0.0 | 0.358 | 0.0 | 0.143 | 0.0 | 0.499 | 0.000% |
| 2026-04-21 | 7064.009765625 | NEUTRAL_TRANSITIONAL | transitional | 0.004 | 1.0 | 0.0 | 0.358 | 0.0 | 0.143 | 0.0 | 0.499 | 0.000% |
| 2026-04-22 | 7137.89990234375 | NEUTRAL_TRANSITIONAL | transitional | 1.000 | 1.0 | 0.055 | 0.0 | 0.164 | 0.164 | 0.164 | 0.0 | 0.726% |
| 2026-04-23 | 7108.39990234375 | NEUTRAL_TRANSITIONAL | transitional | 0.000 | 1.0 | 0.0 | 0.36 | 0.0 | 0.144 | 0.0 | 0.496 | -0.267% |
| 2026-04-24 | 7165.080078125 | NEUTRAL_TRANSITIONAL | transitional | 0.010 | 1.0 | 0.0 | 0.355 | 0.0 | 0.142 | 0.0 | 0.503 | 0.000% |
| 2026-04-27 | 7173.91015625 | NEUTRAL_TRANSITIONAL | transitional | 0.504 | 1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1.0 | 0.000% |
| 2026-04-28 | 7138.7998046875 | NEUTRAL_TRANSITIONAL | transitional | 0.878 | 1.0 | 0.017 | 0.0 | 0.169 | 0.169 | 0.169 | 0.0 | 0.616% |
| 2026-04-29 | 7135.9501953125 | NEUTRAL_TRANSITIONAL | transitional | 0.993 | 1.0 | 0.028 | 0.0 | 0.167 | 0.167 | 0.167 | 0.0 | 2.220% |
| 2026-04-30 | 7209.009765625 | NEUTRAL_TRANSITIONAL | transitional | 0.023 | 1.0 | 0.0 | 0.347 | 0.0 | 0.139 | 0.0 | 0.514 | -0.362% |
| 2026-05-01 | 7230.1201171875 | NEUTRAL_TRANSITIONAL | transitional | 0.992 | 1.0 | 0.014 | 0.0 | 0.169 | 0.169 | 0.169 | 0.0 | 0.595% |
| 2026-05-04 | 7200.75 | NEUTRAL_TRANSITIONAL | transitional | 0.276 | 1.0 | 0.0 | 0.211 | 0.0 | 0.084 | 0.0 | 0.705 | 0.000% |
| 2026-05-05 | 7259.22021484375 | NEUTRAL_TRANSITIONAL | transitional | 1.000 | 1.0 | 0.028 | 0.0 | 0.167 | 0.167 | 0.167 | 0.0 | 0.146% |
| 2026-05-06 | 7365.1201171875 | NEUTRAL_TRANSITIONAL | transitional | 0.176 | 1.0 | 0.0 | 0.265 | 0.0 | 0.106 | 0.0 | 0.629 | -0.231% |
| 2026-05-07 | 7337.10986328125 | NEUTRAL_TRANSITIONAL | transitional | 0.006 | 1.0 | 0.0 | 0.571 | 0.0 | 0.228 | 0.0 | 0.201 | -0.222% |
| 2026-05-08 | 7398.93017578125 | NEUTRAL_TRANSITIONAL | transitional | 0.011 | 1.0 | 0.0 | 0.566 | 0.0 | 0.226 | 0.0 | 0.208 | 0.000% |
| 2026-05-11 | 7412.83984375 | NEUTRAL_TRANSITIONAL | transitional | 0.000 | 1.0 | 0.0 | 0.576 | 0.0 | 0.23 | 0.0 | 0.194 | 0.000% |
| 2026-05-12 | 7400.9599609375 | NEUTRAL_TRANSITIONAL | transitional | 0.010 | 1.0 | 0.0 | 0.355 | 0.0 | 0.142 | 0.0 | 0.503 | 0.000% |
| 2026-05-13 | 7444.25 | NEUTRAL_TRANSITIONAL | transitional | 0.027 | 1.0 | 0.0 | 0.346 | 0.0 | 0.138 | 0.0 | 0.516 | 0.082% |
| 2026-05-14 | 7501.240234375 | NEUTRAL_TRANSITIONAL | transitional | 1.000 | 1.0 | 0.035 | 0.0 | 0.166 | 0.166 | 0.166 | 0.0 | -3.675% |
| 2026-05-15 | 7408.5 | NEUTRAL_TRANSITIONAL | transitional | 0.000 | 1.0 | 0.0 | 0.576 | 0.0 | 0.23 | 0.0 | 0.194 | 0.000% |
| 2026-05-18 | 7403.0498046875 | NEUTRAL_TRANSITIONAL | transitional | 0.001 | 1.0 | 0.0 | 0.575 | 0.0 | 0.23 | 0.0 | 0.195 | 0.000% |
| 2026-05-19 | 7353.60986328125 | NEUTRAL_TRANSITIONAL | transitional | 0.001 | 1.0 | 0.0 | 0.575 | 0.0 | 0.23 | 0.0 | 0.195 | 0.000% |
| 2026-05-20 | 7432.97021484375 | NEUTRAL_TRANSITIONAL | transitional | 0.000 | 1.0 | 0.0 | 0.576 | 0.0 | 0.23 | 0.0 | 0.194 | 0.000% |
| 2026-05-21 | 7445.72021484375 | NEUTRAL_TRANSITIONAL | transitional | 0.000 | 1.0 | 0.0 | 0.576 | 0.0 | 0.23 | 0.0 | 0.194 | -0.457% |
| 2026-05-22 | 7473.47021484375 | NEUTRAL_TRANSITIONAL | transitional | 0.000 | 1.0 | 0.0 | 0.576 | 0.0 | 0.23 | 0.0 | 0.194 | 0.000% |
| 2026-05-26 | 7519.1201171875 | NEUTRAL_TRANSITIONAL | transitional | 0.000 | 1.0 | 0.0 | 0.576 | 0.0 | 0.23 | 0.0 | 0.194 | 0.000% |
| 2026-05-27 | 7520.35986328125 | NEUTRAL_TRANSITIONAL | transitional | 0.999 | 1.0 | 0.105 | 0.0 | 0.156 | 0.156 | 0.156 | 0.0 | 17.503% |
| 2026-05-28 | 7563.6298828125 | NEUTRAL_TRANSITIONAL | transitional | 0.000 | 1.0 | 0.0 | 0.36 | 0.0 | 0.144 | 0.0 | 0.496 | -0.367% |
| 2026-05-29 | 7580.06005859375 | NEUTRAL_TRANSITIONAL | transitional | 0.120 | 1.0 | 0.0 | 0.295 | 0.0 | 0.118 | 0.0 | 0.587 | 0.000% |
| 2026-06-01 | 7599.9599609375 | NEUTRAL_TRANSITIONAL | transitional | 1.000 | 1.0 | 0.104 | 0.0 | 0.157 | 0.157 | 0.157 | 0.0 | -1.374% |
| 2026-06-02 | 7609.77978515625 | NEUTRAL_TRANSITIONAL | transitional | 0.000 | 1.0 | 0.0 | 0.36 | 0.0 | 0.144 | 0.0 | 0.496 | 0.000% |
| 2026-06-03 | 7553.68017578125 | NEUTRAL_TRANSITIONAL | transitional | 1.000 | 1.0 | 0.014 | 0.0 | 0.169 | 0.169 | 0.169 | 0.0 | -5.224% |
| 2026-06-04 | 7584.31005859375 | NEUTRAL_TRANSITIONAL | transitional | 0.832 | 1.0 | 0.019 | 0.0 | 0.169 | 0.169 | 0.169 | 0.0 | 0.234% |
| 2026-06-05 | 7383.740234375 | NEUTRAL_TRANSITIONAL | transitional | 0.000 | 1.0 | 0.0 | 0.36 | 0.0 | 0.144 | 0.0 | 0.496 | 0.000% |
| 2026-06-08 | 7405.72998046875 | NEUTRAL_TRANSITIONAL | transitional | 0.680 | 1.0 | 0.0 | 0.0 | 0.2 | 0.2 | 0.2 | 0.0 | 0.000% |
| 2026-06-09 | 7386.64990234375 | NEUTRAL_TRANSITIONAL | transitional | 0.028 | 1.0 | 0.0 | 0.345 | 0.0 | 0.138 | 0.0 | 0.517 | 0.000% |
| 2026-06-10 | 7266.990234375 | NEUTRAL_TRANSITIONAL | transitional | 0.088 | 1.0 | 0.0 | 0.313 | 0.0 | 0.125 | 0.0 | 0.562 | 0.000% |
