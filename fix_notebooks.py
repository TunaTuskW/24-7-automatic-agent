import json
import os

def process_notebook(file_path):
    with open(file_path, 'r') as f:
        nb = json.load(f)

    for cell in nb.get('cells', []):
        if cell.get('cell_type') == 'code':
            source = cell.get('source', [])
            new_source = []
            for line in source:
                new_source.append(line)
                if line.strip() == '"kelly_smoothed = pd.Series(kelly_exposure).rolling(5).mean().fillna(0)\\n",':
                    new_source.append('    "safe_haven_exposure = np.where((df[\'Regime_Label\'].str.contains(\'CRISIS_DISLOCATION|DEFLATION_FEAR\')) & (kelly_smoothed < 0.2), 1.0 - kelly_smoothed, 0.0)\\n",\n')
                    new_source.append('    "safe_haven_smoothed = pd.Series(safe_haven_exposure).rolling(5).mean().fillna(0)\\n",\n')
                elif line.strip() == '"ax1.plot(df.index, kelly_smoothed * 100, color=\'lime\', label=\'Target Portfolio Exposure %\')\\n",':
                    new_source.append('    "ax1.fill_between(df.index, safe_haven_smoothed * 100, color=\'gold\', alpha=0.4)\\n",\n')
                    new_source.append('    "ax1.plot(df.index, safe_haven_smoothed * 100, color=\'gold\', label=\'Safe Haven Exposure %\')\\n",\n')
            cell['source'] = new_source

    with open(file_path, 'w') as f:
        json.dump(nb, f, indent=1)
        
process_notebook("src/visualize_math_1w.ipynb")
process_notebook("src/visualize_math_4h.ipynb")
print("Notebooks updated successfully!")
