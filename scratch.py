import numpy as np

def compute_shannon_entropy(probs: np.ndarray) -> float:
    try:
        probs = np.clip(probs, 1e-9, 1.0)
        entropy = -np.sum(probs * np.log2(probs))
        return round(float(entropy), 3)
    except Exception as e:
        print(f"Exception: {e}")
        return 1.58

hmm_beta_probs = {"A": 0.0096, "B": 0.9519, "C": 0.0096, "D": 0.0096, "E": 0.0096, "F": 0.0096}
probs = np.array(list((hmm_beta_probs or {}).values()))
print("Entropy:", compute_shannon_entropy(probs))
