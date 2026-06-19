import joblib
m = joblib.load('models/mlp_model_spx.pkl')
print(m['model_mlp'].classes_)
