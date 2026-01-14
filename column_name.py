import pandas as pd
import os

folder = "./thar_csv"

for f in os.listdir(folder):
    path = os.path.join(folder, f)
    try:
        if f.endswith('.csv'):
            df = pd.read_csv(path, nrows=5)
        elif f.endswith('.xlsx'):
            df = pd.read_excel(path, nrows=5)
        else:
            continue
        
        print(f"\n{'='*50}")
        print(f"FILE: {f}")
        print(f"COLUMNS: {list(df.columns)}")
    except Exception as e:
        print(f"\n{f}: ERROR - {e}")