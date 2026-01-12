# WARRANTY DATA FILTERING SCRIPTS

These scripts help you analyze and filter warranty data based on traceability matching rates.

## 📁 Files

1. **`analyze_monthly_matching.py`** - Analyzes matching rates by month
2. **`filter_warranty_data.py`** - Filters data to keep only specified months
3. **`README_FILTERING.md`** - This file

---

## 🚀 STEP-BY-STEP USAGE

### STEP 1: Analyze Monthly Matching Rates

Run the analysis script first to see which months have complete traceability:

```bash
cd /home/user/Traceability/nashik-chatbot-pq/scripts
python3 analyze_monthly_matching.py
```

**Output:**
```
Month            Records  Unique VINs    Matched  Unmatched    Match %          Status
----------------------------------------------------------------------------------------
Dec-2024             695          572        572          0     100.0%     ✓ COMPLETE
Mar-2025             406          361        361          0     100.0%     ✓ COMPLETE
May-2025             249          237        237          0     100.0%     ✓ COMPLETE
Jul-2025              84           81         81          0     100.0%     ✓ COMPLETE
Jan-2025             497          433          0        433       0.0%   ✗ INCOMPLETE
Feb-2025             407          354          0        354       0.0%   ✗ INCOMPLETE
...
```

**This shows:**
- Which months have ≥95% matching (COMPLETE)
- Which months have <95% matching (INCOMPLETE)
- Total records that will be kept vs removed
- Recommendations on what to do

**Results saved to:** `monthly_analysis_results.txt`

---

### STEP 2: Filter Warranty Data

Run the filtering script to remove incomplete months:

```bash
python3 filter_warranty_data.py
```

**Interactive Mode:**

The script will:
1. Show you recommendations from Step 1
2. Ask which months to keep
3. Create backups of original files
4. Filter the data
5. Save filtered files with `_FILTERED` suffix

**Example interaction:**
```
Enter the months you want to KEEP in the filtered data.
Format: Dec-2024,Mar-2025,May-2025,Jul-2025
(comma-separated, no spaces)

Months to keep: Dec-2024,Mar-2025,May-2025,Jul-2025

✓ You selected 4 month(s) to KEEP:
   • Dec-2024
   • Mar-2025
   • May-2025
   • Jul-2025

Proceed with filtering? (yes/no): yes
```

**OR Command Line Mode:**

```bash
python3 filter_warranty_data.py --keep "Dec-2024,Mar-2025,May-2025,Jul-2025"
```

---

### STEP 3: Review Filtered Files

After filtering, check the output files:

```
thar_csv/
├── 2. THAR ROXX Warranty_Sheet1_FILTERED.csv        ← New filtered file
├── 3. THAR ROXX Warranty Analysis_Sheet1_FILTERED.csv  ← New filtered file
└── backups/
    ├── 2. THAR ROXX Warranty_Sheet1_backup_YYYYMMDD_HHMMSS.csv
    └── 3. THAR ROXX Warranty Analysis_Sheet1_backup_YYYYMMDD_HHMMSS.csv
```

**Verify the filtered data:**
```bash
# Check how many records are in filtered files
wc -l "2. THAR ROXX Warranty_Sheet1_FILTERED.csv"
wc -l "3. THAR ROXX Warranty Analysis_Sheet1_FILTERED.csv"
```

---

### STEP 4: Replace Original Files (OPTIONAL)

**⚠️ IMPORTANT: Only do this if you're satisfied with the filtered data!**

If the filtered data looks good, replace the original files:

```bash
cd /home/user/Traceability/thar_csv

# Move filtered files to replace originals
mv "2. THAR ROXX Warranty_Sheet1_FILTERED.csv" "2. THAR ROXX Warranty_Sheet1.csv"
mv "3. THAR ROXX Warranty Analysis_Sheet1_FILTERED.csv" "3. THAR ROXX Warranty Analysis_Sheet1.csv"
```

**Your backups are safe in:** `backups/` directory

---

### STEP 5: Reload Data into Neo4j

After filtering, reload the data:

```bash
cd /home/user/Traceability/nashik-chatbot-pq/scripts
python3 data_loading.py
```

---

## 📋 EXAMPLE WORKFLOW

```bash
# 1. Go to scripts directory
cd /home/user/Traceability/nashik-chatbot-pq/scripts

# 2. Analyze matching rates
python3 analyze_monthly_matching.py

# Output shows: Keep Dec-2024, Mar-2025, May-2025, Jul-2025

# 3. Filter data (interactive)
python3 filter_warranty_data.py
# When prompted, enter: Dec-2024,Mar-2025,May-2025,Jul-2025

# 4. Review filtered files
ls -lh ../../thar_csv/*FILTERED.csv

# 5. If satisfied, replace originals
cd ../../thar_csv
mv "2. THAR ROXX Warranty_Sheet1_FILTERED.csv" "2. THAR ROXX Warranty_Sheet1.csv"
mv "3. THAR ROXX Warranty Analysis_Sheet1_FILTERED.csv" "3. THAR ROXX Warranty Analysis_Sheet1.csv"

# 6. Reload data
cd ../nashik-chatbot-pq/scripts
python3 data_loading.py
```

---

## 🔍 WHAT EACH SCRIPT DOES

### Script 1: analyze_monthly_matching.py

**Input:**
- Warranty CSV (all months)
- Traceability CSV files

**Processing:**
1. Loads all traceability VINs
2. Groups warranty data by manufacturing month
3. Calculates match rate for each month
4. Identifies complete vs incomplete months

**Output:**
- Console report with matching rates
- `monthly_analysis_results.txt` with recommendations
- Suggestions on which months to keep/remove

### Script 2: filter_warranty_data.py

**Input:**
- Months to keep (user input or command line)
- Warranty CSV
- Warranty Analysis CSV

**Processing:**
1. Creates backups of original files
2. Filters warranty data to keep only specified months
3. Filters warranty analysis to keep matching VINs
4. Saves filtered data with `_FILTERED` suffix

**Output:**
- Filtered warranty CSV
- Filtered warranty analysis CSV
- Backups in `backups/` directory

**Files NOT modified:**
- PPCM CSV (keep all)
- ESQA CSV (keep all)
- Traceability CSV (keep all)

---

## ⚠️ IMPORTANT NOTES

### Data Safety
- ✅ Original files are backed up before filtering
- ✅ Filtered files have `_FILTERED` suffix
- ✅ You must manually replace originals (safety feature)
- ✅ Backups stored in `backups/` directory with timestamp

### Files Modified
| File | Modified? | Why? |
|------|-----------|------|
| Warranty CSV | ✅ Yes | Filter by manufacturing month |
| Warranty Analysis CSV | ✅ Yes | Filter to match warranty VINs |
| PPCM CSV | ❌ No | Part quality data applies to all months |
| ESQA CSV | ❌ No | Quality concerns apply to all months |
| Traceability CSV | ❌ No | Already filtered to specific periods |

### Expected Results

**BEFORE filtering:**
- Warranty records: ~6,014
- VIN match rate: ~24.8%

**AFTER filtering (keeping 4 complete months):**
- Warranty records: ~1,434 (23.8%)
- VIN match rate: 100% ✓
- Records removed: ~4,580 (76.2%)

---

## 🆘 TROUBLESHOOTING

### "File not found" error
```bash
# Make sure you're in the correct directory
cd /home/user/Traceability/nashik-chatbot-pq/scripts

# Check if CSV files exist
ls -l ../../thar_csv/*.csv
```

### "No module named 'pandas'" error
```bash
# Install pandas
pip install pandas
```

### Want to undo filtering?
```bash
# Restore from backup
cd /home/user/Traceability/thar_csv/backups

# List available backups
ls -lt

# Copy backup back to main directory
cp "2. THAR ROXX Warranty_Sheet1_backup_YYYYMMDD_HHMMSS.csv" \
   "../2. THAR ROXX Warranty_Sheet1.csv"
```

### Want to filter again with different months?
```bash
# Just run the filter script again
# It will create new backups and new filtered files
python3 filter_warranty_data.py
```

---

## 📞 SUPPORT

For questions or issues:
1. Check the console output for error messages
2. Verify file paths are correct
3. Ensure pandas is installed: `pip install pandas`
4. Check backups exist before replacing files

---

## ✅ CHECKLIST

Before running scripts:
- [ ] All CSV files are in `thar_csv/` directory
- [ ] You've reviewed the analysis output
- [ ] You understand which months will be kept/removed
- [ ] You're ready to lose data for incomplete months

After running scripts:
- [ ] Verify filtered files look correct
- [ ] Backups are created in `backups/` directory
- [ ] Replace originals only when satisfied
- [ ] Reload data into Neo4j with `data_loading.py`
- [ ] Test traceability chatbot

---

**Last Updated:** 2026-01-12
**Scripts Version:** 1.0
