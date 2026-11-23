# Assumptions

synthetic series are demeaned so realised average returns equal the stated assumptions
Data corrections. Four confirmed source-data errors are blanked and forward-filled: SBK.JO on 25 Apr 2025 (R2.29 vs ~R228, unit error) and USDZAR=X on 15 Nov 2024, 15 Jan 2025 and 17 Jan 2025 (bad ticks of 14.86, 16.50 and 15.43 against ~18-19 either side, each reversing the next trading day). All are listed in KNOWN_DATA_ERRORS in the config and recorded in the refresh log. Daily moves above per-asset-class thresholds are logged as exceptions for review and are not auto-corrected.
Exception thresholds (rolling-quarter underperformance 5 points, mandate drawdown and volatility limits, 30% single-holding cap) are illustrative reporting thresholds to be agreed with the adviser team. The single-holding rule applies to securities only, not to synthetic asset-class sleeves.

Currency effect is reported two ways: a compounded counterfactual (portfolio return with USD/ZAR held flat versus actual) and an additive contribution split. They differ because the stronger rand also reduced the gains.
