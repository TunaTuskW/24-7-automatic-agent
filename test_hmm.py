import joblib
import numpy as np
m = joblib.load('models/hmm_model_1d.pkl')
hmm = m['hmm']
scaler = m['scaler']

features = [0.184, 0.532, -1.1235270671688296, -0.008, -0.039, -0.1335750370638359, 0.023999691009521484, 0.4479997158050537, 0.758, 0.094, -0.262, 0.709, 0.505, -0.934, 0.59, 0.52, 52.27104960157115, -1.2604883665958724, 0.030814283823419903, -0.893623395957895]
obs = np.array([features] * 30)

obs_scaled = scaler.transform(obs)
_, posteriors = hmm.score_samples(obs_scaled)

state_probs = posteriors[-1]
state_labels = m['state_labels']

regime_probs = {state_labels.get(i, f"STATE_{i}"): round(float(prob), 4) for i, prob in enumerate(state_probs)}
print("Regime probs:", regime_probs)
dominant = max(regime_probs, key=regime_probs.get)
print("Dominant:", dominant)
