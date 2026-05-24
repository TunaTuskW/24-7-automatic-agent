import nbformat as nbf
import os

def create_comprehensive_notebook(filename, report_prefix, title, timeframe_label):
    nb = nbf.v4.new_notebook()

    md_intro = nbf.v4.new_markdown_cell(f"""# {title}
This comprehensive dashboard visually unpacks EVERY quantitative math engine and algorithmic layer over the {timeframe_label} reporting cadence. It calculates the Regime Persistence, Deep Learning Probs, Information Theory (Chaos), Fragility Index, and Epistemic Kelly Exposure, concluding with the final generated {timeframe_label} report.
""")

    code_imports = nbf.v4.new_code_cell("""import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from train_models import fetch_training_data
import joblib
import warnings
import glob
import os
from IPython.display import Markdown
warnings.filterwarnings('ignore')

plt.style.use('dark_background')
""")

    md_data = nbf.v4.new_markdown_cell("""## 1. Data Ingestion, HMM Decoder & Deep Learning (MLP) Output""")

    code_data = nbf.v4.new_code_cell("""# Load the 2-year data using the exact daily training schema
df = fetch_training_data(years=2)

# Load the HMM
hmm_package = joblib.load('../models/hmm_model.pkl')
hmm = hmm_package['hmm']
scaler = hmm_package['scaler']
state_labels = hmm_package['state_labels']
features = hmm_package['feature_names']

# Predict the Hidden States
X_scaled = scaler.transform(df[features].values)
states = hmm.predict(X_scaled)
df['Regime_ID'] = states
df['Regime_Label'] = df['Regime_ID'].map(state_labels)

# Get HMM Probabilities & Shannon Entropy
_, posteriors = hmm.score_samples(X_scaled)
df['HMM_Entropy'] = -np.sum(posteriors * np.log2(posteriors + 1e-9), axis=1)

# Load the Deep Learning MLP
mlp_package = joblib.load('../models/mlp_model.pkl')
mlp = mlp_package['model']
mlp_scaler = mlp_package['scaler']
mlp_features = mlp_package['feature_names']

# Predict MLP Probabilities (0=RiskOff, 1=RiskOn, 2=Transitional)
X_mlp = mlp_scaler.transform(df[mlp_features].values)
mlp_probs = mlp.predict_proba(X_mlp)
df['MLP_RiskOff'] = mlp_probs[:, 0]
df['MLP_RiskOn'] = mlp_probs[:, 1]
df['MLP_Transitional'] = mlp_probs[:, 2]
""")

    md_overlay = nbf.v4.new_markdown_cell("""## 2. Regime Overlay & Deep Learning Conviction""")

    code_overlay = nbf.v4.new_code_cell("""fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 10), gridspec_kw={'height_ratios': [2, 1]}, sharex=True)

# Top Chart: SPX with HMM Regimes
ax1.plot(df.index, df['Close'], color='white', linewidth=1.5, label='SPX')
ax1.set_title('S&P 500 Price with Hidden Markov Model Regime Overlay', fontsize=16)

unique_regimes = df['Regime_Label'].unique()
colors = sns.color_palette("husl", len(unique_regimes))
regime_colors = dict(zip(unique_regimes, colors))

for i in range(len(df)-1):
    regime = df['Regime_Label'].iloc[i]
    ax1.axvspan(df.index[i], df.index[i+1], color=regime_colors[regime], alpha=0.3, lw=0)

from matplotlib.patches import Patch
legend_elements = [Patch(facecolor=regime_colors[reg], alpha=0.5, label=reg) for reg in unique_regimes]
ax1.legend(handles=legend_elements, loc='upper left')

# Bottom Chart: MLP Probabilities
ax2.plot(df.index, df['MLP_RiskOn'], color='lime', label='MLP Risk-On Prob')
ax2.plot(df.index, df['MLP_RiskOff'], color='red', label='MLP Risk-Off Prob')
ax2.plot(df.index, df['MLP_Transitional'], color='yellow', alpha=0.5, label='MLP Transitional Prob')
ax2.set_title('Deep Learning (MLP) Probability Output', fontsize=14)
ax2.set_ylabel('Probability')
ax2.legend(loc='upper left')

plt.tight_layout()
plt.show()
""")

    md_chaos = nbf.v4.new_markdown_cell("""## 3. Information Theory: System Chaos & Entropy""")

    code_chaos = nbf.v4.new_code_cell("""# Plot Shannon Entropy to measure system chaos (Max entropy for 6 states is ~2.58)
fig, ax = plt.subplots(figsize=(15, 4))
ax.plot(df.index, df['HMM_Entropy'], color='orange', label='HMM Shannon Entropy')
ax.axhline(1.5, color='red', linestyle='--', label='High Chaos Threshold (Stand Aside)')
ax.fill_between(df.index, df['HMM_Entropy'], 1.5, where=(df['HMM_Entropy'] > 1.5), color='red', alpha=0.3)
ax.set_title('Information Theory: Shannon Entropy (Market Chaos)', fontsize=14)
ax.set_ylabel('Entropy (Bits)')
ax.legend(loc='upper left')
plt.tight_layout()
plt.show()
""")

    md_heat = nbf.v4.new_markdown_cell("""## 4. Institutional Heat Index (Stealth Accumulation)""")

    code_heat = nbf.v4.new_code_cell("""# The Inst Heat Index combines Volume Z-Score (Effort) with Intraday Range (Result)
fig, ax = plt.subplots(figsize=(15, 4))
ax.bar(df.index, df['Inst_Heat_Index'], color=np.where(df['Inst_Heat_Index'] > 0, 'lime', 'red'), alpha=0.7, label='Institutional Heat')
ax.set_title('Institutional Heat Index (Stealth Accumulation / Exhaustion)', fontsize=14)
ax.set_ylabel('Heat Index')
ax.axhline(0, color='white', linewidth=0.5)
ax.legend(loc='upper left')
plt.tight_layout()
plt.show()
""")

    md_fragility = nbf.v4.new_markdown_cell("""## 5. The Fragility Index (Hidden Liquidity Shocks)""")

    code_fragility = nbf.v4.new_code_cell("""spx_dxy_corr = df['spx_ret'].rolling(10).corr(df['dxy_ret'])

fig, ax1 = plt.subplots(figsize=(15, 5))
ax1.plot(df.index, spx_dxy_corr, color='cyan', label='10-Day SPX/DXY Correlation')
ax1.axhline(0.4, color='red', linestyle='--', label='Fragility Threshold (>0.4)')
ax1.set_ylabel('Correlation')
ax1.set_title('Hidden Market Fragility: Dollar Liquidity Drain & VVIX', fontsize=14)
ax1.legend(loc='upper left')

ax2 = ax1.twinx()
ax2.plot(df.index, df['vix_zscore'], color='magenta', alpha=0.5, label='VIX Z-Score (Vol-of-Vol)')
ax2.set_ylabel('VIX Z-Score')
ax2.legend(loc='upper right')

plt.tight_layout()
plt.show()
""")

    md_kelly = nbf.v4.new_markdown_cell("""## 6. Epistemic Kelly Exposure Sizing & Target Calibration""")

    code_kelly = nbf.v4.new_code_cell("""kelly_exposure = np.where(df['vix_zscore'] > 2.0, 0.05, 0.5)
kelly_exposure = np.where(df['Regime_Label'].str.contains('RISK_ON'), kelly_exposure + 0.3, kelly_exposure)
kelly_exposure = np.where(df['Regime_Label'].str.contains('FEAR|SHOCK|STRESS'), 0.0, kelly_exposure)
kelly_smoothed = pd.Series(kelly_exposure).rolling(5).mean().fillna(0)

# Simulate Brier Score drift (Mocking calibration decay during chaos)
simulated_brier = 0.15 + (df['HMM_Entropy'] / 10.0)

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 8), sharex=True)
ax1.fill_between(df.index, kelly_smoothed * 100, color='lime', alpha=0.4)
ax1.plot(df.index, kelly_smoothed * 100, color='lime', label='Target Portfolio Exposure %')
ax1.set_ylim(0, 100)
ax1.set_title('Epistemic Kelly Sizing Curve (Risk Scaler)', fontsize=14)
ax1.set_ylabel('Exposure %')
ax1.legend(loc='upper left')

ax2.plot(df.index, simulated_brier, color='violet', label='Simulated Brier Score (Calibration)')
ax2.axhline(0.25, color='red', linestyle='--', label='Calibration Crisis (>0.25)')
ax2.set_title('Model Governance: Brier Score Calibration Tracking', fontsize=14)
ax2.set_ylabel('Brier Score (Error)')
ax2.legend(loc='upper left')

plt.tight_layout()
plt.show()
""")

    reports_target_dir = "'../reports/updates'" if timeframe_label == "4-Hour" else "'../reports'"

    md_report = nbf.v4.new_markdown_cell(f"""## 7. Generated {timeframe_label} Report Layout
Displaying the most recent algorithmically generated report.
""")

    code_report = nbf.v4.new_code_cell(f"""reports_dir = {reports_target_dir}
pattern = '{report_prefix}*.md'
files = glob.glob(os.path.join(reports_dir, pattern))

if files:
    latest_file = max(files, key=os.path.getmtime)
    with open(latest_file, 'r') as f:
        content = f.read()
    display(Markdown(content))
else:
    print("No recent report found. Run the {timeframe_label} script first.")
""")

    nb['cells'] = [md_intro, code_imports, md_data, code_data, md_overlay, code_overlay, md_chaos, code_chaos, md_heat, code_heat, md_fragility, code_fragility, md_kelly, code_kelly, md_report, code_report]

    with open(f"src/{filename}", 'w') as f:
        nbf.write(nb, f)

create_comprehensive_notebook("visualize_math_4h.ipynb", "4 hours update", "Macro Math Visualizer (4-Hour Sync)", "4-Hour")
create_comprehensive_notebook("visualize_math_1w.ipynb", "macro weekly synthesis", "Macro Math Visualizer (Weekly Synthesis)", "Weekly")
