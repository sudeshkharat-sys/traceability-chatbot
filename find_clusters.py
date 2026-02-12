import os
import pandas as pd

# 1. Load Head Lamp failure VINs from Warranty
df_w = pd.read_csv('csv_output/2. THAR ROXX Warranty_Sheet1_FILTERED.csv', low_memory=False)
hl_claims = df_w[df_w['Complaint Code Desc'] == 'HEAD LAMP FAILURE']
hl_vins_short = {str(v)[-8:] for v in hl_claims['Serial No'].unique()}

print(f"Total unique Head Lamp failure VINs: {len(hl_vins_short)}")

# 2. Scan Traceability files for these VINs
scan_map = {}
files = [f for f in os.listdir('csv_output') if f.startswith('6.')]

for f in files:
    print(f"Checking {f}...")
    # Read only necessary columns
    try:
        df_t = pd.read_csv('csv_output/' + f, usecols=['VINNumber', 'ScanValue', 'BOMPARTNO'], low_memory=False)
        df_t = df_t.dropna(subset=['ScanValue'])
        
        # Filter for our failed VINs
        for _, row in df_t.iterrows():
            vin = str(row['VINNumber'])[-8:]
            if vin in hl_vins_short:
                # We only care about Head Lamp parts in these VINs
                part = str(row['BOMPARTNO'])
                if '1701AW500101N' in part or '1701AW500091N' in part:
                    scan = str(row['ScanValue'])
                    if scan not in scan_map:
                        scan_map[scan] = set()
                    scan_map[scan].add(vin)
    except Exception as e:
        print(f"Error reading {f}: {e}")

# 3. Identify clusters
clusters = {k: v for k, v in scan_map.items() if len(v) > 1}

print("\n=== CLUSTERS FOUND ===")
if not clusters:
    print("No batch clusters found in the raw CSV data.")
    print("Every traceable Head Lamp failure recorded in the CSV comes from a unique batch.")
else:
    for scan, vins in clusters.items():
        print(f"Batch/Scan: {scan}")
        print(f"Failed VINs: {vins}")
        print("-" * 20)