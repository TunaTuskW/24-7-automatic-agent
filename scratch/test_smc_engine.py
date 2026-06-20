import sys
import os
import unittest
import pandas as pd
import numpy as np

# Add src to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from engines.smc_engine import SMCEngine

class TestSMCEngine(unittest.TestCase):
    def setUp(self):
        self.engine = SMCEngine(swing_period=3, fvg_min_pct=0.001)

    def test_under_size_input(self):
        # Scenario 1 — under-size input (< swing_period*2+1 bars)
        # 3*2+1 = 7, so give 5 bars
        df = pd.DataFrame({
            "High": [10, 11, 12, 13, 14],
            "Low": [9, 10, 11, 12, 13],
            "Close": [9.5, 10.5, 11.5, 12.5, 13.5]
        })
        state = self.engine.compute(df)
        self.assertEqual(state.bos_direction, 0)
        self.assertEqual(state.smc_bias, 0)
        self.assertEqual(state.premium_discount, "EQUILIBRIUM")

    def test_clean_uptrend_data(self):
        # Scenario 2 — clean uptrend data (ascending closes and swings)
        # Need at least two swing highs and lows
        # Let's create an obvious uptrend that forms swings
        # Swing period = 2 to make it easier
        engine = SMCEngine(swing_period=2, fvg_min_pct=0.001)
        
        # We need swings: local min/max over 5-bar window
        # swing 1: H=20, L=10
        # swing 2: H=30, L=20
        # last close > prev high (30)
        highs = [15, 18, 20, 17, 16, 25, 28, 30, 27, 26, 35, 38, 40]
        lows =  [16, 15, 14, 10, 15, 18, 20, 25, 24, 22, 28, 30, 35]
        closes= [12, 15, 18, 14, 15, 22, 25, 28, 24, 25, 32, 35, 38]
        
        df = pd.DataFrame({
            "High": highs,
            "Low": lows,
            "Close": closes
        })
        state = engine.compute(df)
        self.assertEqual(state.bos_direction, 1)
        self.assertGreaterEqual(state.smc_bias, 0)

    def test_clean_downtrend_data(self):
        # Scenario 3 — clean downtrend data
        engine = SMCEngine(swing_period=2, fvg_min_pct=0.001)
        highs = [40, 38, 35, 36, 37, 30, 28, 25, 26, 27, 20, 18, 15]
        lows =  [35, 30, 28, 32, 33, 25, 20, 18, 23, 24, 15, 12, 10]
        closes= [38, 35, 32, 34, 35, 28, 25, 22, 24, 25, 18, 15, 12]
        
        df = pd.DataFrame({
            "High": highs,
            "Low": lows,
            "Close": closes
        })
        state = engine.compute(df)
        self.assertEqual(state.bos_direction, -1)
        self.assertLessEqual(state.smc_bias, 0)

    def test_flat_prices(self):
        # Scenario 4 — flat prices (no swings detectable)
        engine = SMCEngine(swing_period=2, fvg_min_pct=0.001)
        highs = [10] * 15
        lows = [10] * 15
        closes = [10] * 15
        
        df = pd.DataFrame({
            "High": highs,
            "Low": lows,
            "Close": closes
        })
        state = engine.compute(df)
        self.assertEqual(state.smc_bias, 0)

if __name__ == "__main__":
    unittest.main()
