# ═══════════════════════════════════════════════════════════
# DATA LOADING
# ═══════════════════════════════════════════════════════════

import pandas as pd
from neo4j import GraphDatabase

NEO4J_URI = "neo4j://127.0.0.1:7687"
NEO4J_USERNAME = "neo4j"
NEO4J_PASSWORD = "dataeaze@12345"
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))


def run_query(query, params=None):
    with driver.session() as session:
        session.run(query, params or {})


# ═══════════════════════════════════════════════════════════
# STEP 1: LOAD DATA FILES
# ═══════════════════════════════════════════════════════════
print("=" * 80)
print("LOADING CSV FILES")
print("=" * 80)

ppcm = pd.read_csv("../../thar_csv/1. THAR ROXX PPCM_Sheet1.csv")
warranty = pd.read_csv("../../thar_csv/2. THAR ROXX Warranty_Sheet1.csv")
warranty_analysis = pd.read_csv(
    "../../thar_csv/3. THAR ROXX Warranty Analysis_Sheet1.csv"
)
esqa = pd.read_csv("../../thar_csv/4. THAR ROXX e-SQA_Sheet1.csv")

# Load ALL traceability files
import os

folder = "../../thar_csv"
trace_files = [
    f for f in os.listdir(folder) if "traceability" in f.lower() and f.endswith(".csv")
]
print(f"Found {len(trace_files)} traceability files")
trace = pd.concat(
    [pd.read_csv(os.path.join(folder, f)) for f in trace_files], ignore_index=True
)

print(
    f"✅ Loaded: {len(ppcm)} PPCM, {len(warranty)} Warranty, {len(warranty_analysis)} Analysis, {len(esqa)} e-SQA, {len(trace)} Trace"
)

# ═══════════════════════════════════════════════════════════
# STEP 2: DATA PREPROCESSING
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("PREPROCESSING DATA")
print("=" * 80)

# Fill NaN with 'unknown'
ppcm = ppcm.fillna("unknown")
warranty = warranty.fillna("unknown")
warranty_analysis = warranty_analysis.fillna("unknown")
esqa = esqa.fillna("unknown")
trace = trace.fillna("unknown")

# Clean vendor names
warranty["vender"] = warranty["vender"].replace(["-", "", "N/A", " "], "unknown")

# CRITICAL: Extract VIN suffix (last 8 chars) from traceability
trace["VIN_SHORT"] = trace["VINNumber"].str[-8:]


# ═══════════════════════════════════════════════════════════
# PART NUMBER NORMALIZATION (FIX ISSUE #1 & #5: Part mismatch & Duplicate nodes)
# ═══════════════════════════════════════════════════════════
def normalize_part_number(part_value):
    """
    Normalize part numbers to ensure consistency across datasets.

    Valid formats:
        - ####AA#####A  (12-13 chars: 4 digits + 2 letters + 5-6 digits + 1 letter)
        - ####AAA####A  (13-14 chars: 4 digits + 3 letters + 5-6 digits + 1 letter)

    Examples:
        - 0107BW500561N (13 chars)
        - 2303CW504481N (13 chars)
        - 1101AAA03621N (13 chars)

    Returns:
        - Standard format part if valid (e.g., "0107BW500561N")
        - J-format preserved (e.g., "J60-BOD-1920")
        - "unknown" if invalid or garbage text
    """
    import re

    # Handle NaN, None, empty
    if pd.isna(part_value) or part_value == "" or part_value == "unknown":
        return "unknown"

    # Convert to string and clean
    part = str(part_value).strip()

    # Remove common control characters
    part = part.replace("_x000d_", "").replace("_X000D_", "")
    part = part.replace("\r", "").replace("\n", "").replace("\t", "")
    part = part.strip()

    # Convert to uppercase for consistency
    part = part.upper()

    # Check if it matches valid part number pattern
    # Pattern: 4 digits + 2-3 letters + 5-6 digits + 1 letter (total 12-14 chars)
    # Examples: 0114DW500591N, 1101AAA03621N, 2303CW504481N
    pattern = r"^[0-9]{4}[A-Z]{2,3}[0-9]{5,6}[A-Z]$"

    if re.match(pattern, part):
        return part  # Valid standard format

    # Check for alternative J-format (internal M&M codes)
    # Format: J##-AAA-#### (e.g., J60-BOD-1920)
    j_pattern = r"^J[0-9]{2}-[A-Z]{3}-[0-9]{4}$"
    if re.match(j_pattern, part):
        # Keep J-format as-is (may not match traceability but preserve for reference)
        return part

    # If it contains spaces or is too long, it's likely a description, not a part number
    if len(part) > 50 or " " in part:
        return "unknown"

    # If too short, likely incomplete
    if len(part) < 5:
        return "unknown"

    # Default: mark as unknown (invalid format)
    return "unknown"


print("\n🔧 Normalizing part numbers...")

# Apply normalization to all datasets
warranty["part_original"] = warranty["part"]  # Keep original for debugging
warranty["part"] = warranty["part"].apply(normalize_part_number)

ppcm["Part No"] = ppcm["Part No"].apply(normalize_part_number)
esqa["Part No"] = esqa["Part No"].apply(normalize_part_number)
trace["BOMPARTNO"] = trace["BOMPARTNO"].apply(normalize_part_number)

# Report normalization results
warranty_valid = (warranty["part"] != "unknown").sum()
warranty_total = len(warranty)
warranty_invalid = warranty_total - warranty_valid

print(f"✅ Part number normalization complete:")
print(f"   Warranty - Valid: {warranty_valid:,}/{warranty_total:,} ({warranty_valid/warranty_total*100:.1f}%)")
print(f"   Warranty - Invalid/Unknown: {warranty_invalid:,} ({warranty_invalid/warranty_total*100:.1f}%)")

# Show sample invalid entries (for debugging)
invalid_samples = warranty[warranty["part"] == "unknown"]["part_original"].unique()[:5]
if len(invalid_samples) > 0:
    print(f"   Sample invalid entries (marked as 'unknown'):")
    for sample in invalid_samples:
        sample_str = str(sample)[:60]
        if len(str(sample)) > 60:
            sample_str += "..."
        print(f"     - {sample_str}")


# CRITICAL: Parse ScanValue (format: mfg_date:shift:batch_code)
def parse_scan_value(scan_val):
    """Extract batch info from ScanValue: date:shift:batch
    Format: ...:DDMMYY:Shift:BatchCode
    Example: 040:0502AAA14030N:A002:290825:1:4SH078823
    Returns: (date_ddmmyy, shift, batch_code)
    """
    try:
        if pd.isna(scan_val) or scan_val == "unknown":
            return "unknown", "unknown", scan_val

        parts = str(scan_val).split(":")
        if len(parts) >= 3:
            # Example: 040:0502AAA14030N:A002:290825:1:4SH078823
            # We want: date (290825 = DDMMYY), shift (1), batch_code (4SH078823)
            date_part = parts[-3] if len(parts) >= 3 else "unknown"
            shift_part = parts[-2] if len(parts) >= 2 else "unknown"
            batch_code = parts[-1] if len(parts) >= 1 else scan_val
            return date_part, shift_part, batch_code
        else:
            return "unknown", "unknown", scan_val
    except:
        return "unknown", "unknown", scan_val


def convert_ddmmyy_to_ddmmyyyy(date_str, reference_date=None):
    """Convert DDMMYY to DD-MM-YYYY format
    Uses reference_date (from TDATE) to infer century if needed
    """
    try:
        if date_str == "unknown" or len(date_str) != 6:
            return date_str
        # Extract DD, MM, YY
        dd = date_str[:2]
        mm = date_str[2:4]
        yy = date_str[4:6]

        # Infer year: if YY > 50, assume 19YY, else 20YY
        # Or use reference_date if provided
        if reference_date:
            ref_year = int(str(reference_date)[:4])
            year = 2000 + int(yy) if int(yy) < 50 else 1900 + int(yy)
            # Adjust if reference suggests different century
            if abs(year - ref_year) > 50:
                year = ref_year - (ref_year % 100) + int(yy)
        else:
            year = 2000 + int(yy) if int(yy) < 50 else 1900 + int(yy)

        return f"{dd}-{mm}-{year}"
    except:
        return date_str


trace[["BATCH_DATE", "SHIFT", "BATCH_CODE"]] = trace["ScanValue"].apply(
    lambda x: pd.Series(parse_scan_value(x))
)

print("✅ VIN extraction and ScanValue parsing complete")

# Check VIN match rate
warranty_vins = set(warranty["Serial No"].dropna().unique())
trace_vin_short = set(trace["VIN_SHORT"].dropna().unique())
vin_matches = warranty_vins.intersection(trace_vin_short)

print(f"\nVIN Matching:")
print(f"  Warranty VINs: {len(warranty_vins):,}")
print(f"  Trace VINs (short): {len(trace_vin_short):,}")
print(
    f"  Matches: {len(vin_matches):,} ({len(vin_matches)/len(warranty_vins)*100:.1f}%)"
)

# Check Part No match rate
warranty_parts = set(warranty["part"].dropna().unique())
trace_parts = set(trace["BOMPARTNO"].dropna().unique())
part_matches = warranty_parts.intersection(trace_parts)

print(f"\nPart Number Matching:")
print(f"  Warranty parts: {len(warranty_parts):,}")
print(f"  Trace parts: {len(trace_parts):,}")
print(
    f"  Matches: {len(part_matches):,} ({len(part_matches)/len(warranty_parts)*100:.1f}%)"
)

# ═══════════════════════════════════════════════════════════
# STEP 3: CLEAR EXISTING DATA
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("CLEARING EXISTING DATA")
print("=" * 80)

run_query("MATCH (n) DETACH DELETE n")
print("✅ Database cleared")

# ═══════════════════════════════════════════════════════════
# STEP 4: CREATE CONSTRAINTS
# ═══════════════════════════════════════════════════════════
print("\nCreating constraints...")

constraints = [
    "CREATE CONSTRAINT IF NOT EXISTS FOR (v:Vendor) REQUIRE v.name IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Part) REQUIRE p.part_no IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (v:Vehicle) REQUIRE v.vin IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (w:WarrantyClaim) REQUIRE w.claim_no IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (d:Dealer) REQUIRE d.code IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Commodity) REQUIRE c.name IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (pl:Plant) REQUIRE pl.code IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (b:Batch) REQUIRE b.lot_no IS UNIQUE",
]

for c in constraints:
    try:
        run_query(c)
    except:
        pass

print("✅ Constraints created")

# ═══════════════════════════════════════════════════════════
# STEP 5: LOAD TRACEABILITY (FIRST - creates Vehicles & Batches)
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("1. LOADING TRACEABILITY (Part → VIN → Batch)")
print("=" * 80)

query = """
UNWIND $rows AS row

// Create Vehicle using SHORT VIN (8 chars)
MERGE (v:Vehicle {vin: row.vin_short})
SET v.full_vin = row.full_vin

// Create Part
MERGE (p:Part {part_no: row.part_no})

// Link Part to Vehicle
MERGE (p)-[f:FITTED_ON]->(v)
SET f.date = row.tdate, 
    f.scan_value = row.scan_value,
    f.batch_date = row.batch_date,
    f.shift = row.shift

// Create Batch with detailed info
WITH p, v, row WHERE row.scan_value <> 'unknown' AND row.scan_value <> ''
MERGE (b:Batch {lot_no: row.scan_value})
SET b.batch_code = row.batch_code,
    b.batch_date = row.batch_date,
    b.shift = row.shift

MERGE (p)-[:FROM_BATCH]->(b)
"""

rows = trace.rename(
    columns={
        "VINNumber": "full_vin",
        "VIN_SHORT": "vin_short",
        "BOMPARTNO": "part_no",
        "TDATE": "tdate",
        "ScanValue": "scan_value",
        "BATCH_DATE": "batch_date",
        "SHIFT": "shift",
        "BATCH_CODE": "batch_code",
    }
).to_dict("records")

# Filter valid records
rows = [r for r in rows if r["vin_short"] != "unknown" and r["part_no"] != "unknown"]

batch_size = 1000
for i in range(0, len(rows), batch_size):
    run_query(query, {"rows": rows[i : i + batch_size]})
    if i % 10000 == 0 and i > 0:
        print(f"   Progress: {i:,}/{len(rows):,}")

print(f"✅ Loaded {len(rows):,} traceability records")

# ═══════════════════════════════════════════════════════════
# STEP 6: LOAD PPCM (Supplier Quality - Cp/Cpk)
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("2. LOADING PPCM (Vendor → Part → Cp/Cpk)")
print("=" * 80)

query = """
UNWIND $rows AS row

MERGE (v:Vendor {name: row.vendor_name})

MERGE (p:Part {part_no: row.part_no})
SET p.model = row.model, 
    p.characteristic = row.characteristic,
    p.specification = row.specification

MERGE (v)-[:SUPPLIES]->(p)

// Add Cpk relationship if data exists
WITH v, p, row WHERE row.cpk <> 'unknown' AND row.cpk <> ''
MERGE (v)-[r:HAS_CPK]->(p)
SET r.cpk = toFloat(row.cpk), 
    r.cp = toFloat(row.cp)
"""

rows = ppcm.rename(
    columns={
        "Vendor Name": "vendor_name",
        "Part No": "part_no",
        "Model": "model",
        "Characteristic": "characteristic",
        "Specification": "specification",
        "CpK": "cpk",
        "Cp": "cp",
    }
).to_dict("records")

for i in range(0, len(rows), 500):
    run_query(query, {"rows": rows[i : i + 500]})

print(f"✅ Loaded {len(rows):,} PPCM records")

# ═══════════════════════════════════════════════════════════
# STEP 7: LOAD WARRANTY (Field Failures)
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("3. LOADING WARRANTY (Claims → Vehicle → Parts)")
print("=" * 80)

query = """
UNWIND $rows AS row

// Create Warranty Claim
MERGE (w:WarrantyClaim {claim_no: row.claim_no})
SET w.complaint_code = row.complaint_code, 
    w.complaint_desc = row.complaint_desc,
    w.failure_date = row.failure_date, 
    w.failure_kms = row.failure_kms,
    w.claim_date = row.claim_date, 
    w.incidents = toInteger(row.incidents),
    w.region = row.region, 
    w.zone = row.zone

// Link to Vehicle (using 8-char VIN - same as trace)
MERGE (v:Vehicle {vin: row.serial_no})
SET v.model = row.model_code, 
    v.engine_no = row.engine_no

// Dealer
MERGE (d:Dealer {code: row.dealer_code})
SET d.name = row.dealer_name

// Plant
MERGE (pl:Plant {code: row.plant})
SET pl.desc = row.plant_desc

// Commodity
MERGE (c:Commodity {name: row.commodity})

// Part
MERGE (p:Part {part_no: row.part})

// Create relationships
MERGE (v)-[:HAS_CLAIM]->(w)
MERGE (w)-[:FILED_AT]->(d)
MERGE (w)-[:INVOLVES_PART]->(p)
MERGE (v)-[:MANUFACTURED_AT]->(pl)
MERGE (p)-[:BELONGS_TO]->(c)

// Vendor attribution
WITH w, row WHERE row.vendor <> 'unknown' AND row.vendor <> ''
MERGE (vd:Vendor {name: row.vendor})
MERGE (w)-[:ATTRIBUTED_TO]->(vd)
"""

rows = warranty.rename(
    columns={
        "SAP Claim No": "claim_no",
        "Serial No": "serial_no",
        "Complaint Code": "complaint_code",
        "Complaint Code Desc": "complaint_desc",
        "Failure Date": "failure_date",
        "Failure Kms": "failure_kms",
        "Claim Date": "claim_date",
        "No. of Incidents": "incidents",
        "Region": "region",
        "Zone": "zone",
        "Dealer Code": "dealer_code",
        "Claim Dealer Name": "dealer_name",
        "Plant": "plant",
        "PlantDesc": "plant_desc",
        "part": "part",
        "vender": "vendor",
        "Model Code": "model_code",
        "ENGINE NUMBER": "engine_no",
        "Commodity": "commodity",
    }
).to_dict("records")

for i in range(0, len(rows), 500):
    run_query(query, {"rows": rows[i : i + 500]})

print(f"✅ Loaded {len(rows):,} warranty claims")

# ═══════════════════════════════════════════════════════════
# STEP 8: LOAD WARRANTY ANALYSIS (Decisions & Attribution)
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("4. LOADING WARRANTY ANALYSIS (Decisions)")
print("=" * 80)

# CRITICAL: Link Warranty Analysis to WarrantyClaim by claim_no OR Serial Number
# This ensures Decision/Attribution data is linked to Parts via existing WarrantyClaim relationships
# Split into two queries for better performance
query_by_claim = """
UNWIND $rows AS row

// Match by claim_no (when available)
MATCH (w:WarrantyClaim {claim_no: row.claim_no})
SET w.decision = row.decision, 
    w.attribution = row.attribution

WITH w, row WHERE row.commodity <> 'unknown' AND row.commodity <> ''
MERGE (c:Commodity {name: row.commodity})
MERGE (w)-[:INVOLVES_COMMODITY]->(c)
"""

query_by_serial = """
UNWIND $rows AS row

// Match by Serial Number (VIN) when claim_no is missing
MATCH (v:Vehicle {vin: row.serial_no})-[:HAS_CLAIM]->(w:WarrantyClaim)
SET w.decision = row.decision, 
    w.attribution = row.attribution

WITH w, row WHERE row.commodity <> 'unknown' AND row.commodity <> ''
MERGE (c:Commodity {name: row.commodity})
MERGE (w)-[:INVOLVES_COMMODITY]->(c)
"""

rows = warranty_analysis.rename(
    columns={
        "SAP Claim No": "claim_no",
        "Serial Number": "serial_no",
        "Decision": "decision",
        "Attribution": "attribution",
        "Commodity": "commodity",
    }
).to_dict("records")

# Split rows by whether they have claim_no
rows_with_claim = [
    r for r in rows if r["claim_no"] != "unknown" and r["claim_no"] != ""
]
rows_without_claim = [
    r for r in rows if r["claim_no"] == "unknown" or r["claim_no"] == ""
]

print(f"  Records with claim_no: {len(rows_with_claim):,}")
print(f"  Records without claim_no (using Serial Number): {len(rows_without_claim):,}")

# Load records with claim_no
for i in range(0, len(rows_with_claim), 500):
    run_query(query_by_claim, {"rows": rows_with_claim[i : i + 500]})

# Load records without claim_no (match by Serial Number)
for i in range(0, len(rows_without_claim), 500):
    run_query(query_by_serial, {"rows": rows_without_claim[i : i + 500]})

print(f"✅ Loaded {len(rows):,} warranty analysis records")

# ═══════════════════════════════════════════════════════════
# STEP 9: LOAD e-SQA (Incoming Quality - Part No ONLY)
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("5. LOADING e-SQA (Quality Concerns → Part)")
print("=" * 80)

query = """
UNWIND $rows AS row

MERGE (e:ESQAConcern {esqa_no: row.esqa_no})
SET e.date = row.concern_date, 
    e.description = row.description,
    e.qty_reported = toInteger(row.qty_reported),
    e.rejection_qty = toInteger(row.rejection_qty),
    e.scrap_qty = toInteger(row.scrap_qty),
    e.rework_qty = toInteger(row.rework_qty),
    e.vehicle_model = row.vehicle_model

MERGE (p:Part {part_no: row.part_no})
MERGE (v:Vendor {name: row.vendor_name})

MERGE (e)-[:RAISED_FOR]->(p)
MERGE (e)-[:RAISED_AGAINST]->(v)
"""

rows = esqa.rename(
    columns={
        "ESQA Number": "esqa_no",
        "Concern Report Date": "concern_date",
        "Concern Description": "description",
        "Qty. Reported": "qty_reported",
        "Rejection(BLock)Qty (344 and 350 Mvt)": "rejection_qty",
        "Scarp Qty(951 and 551 Mvt)": "scrap_qty",
        "Rework Qty": "rework_qty",
        "Part No": "part_no",
        "Vendor Name": "vendor_name",
        "Vehicle Model": "vehicle_model",
    }
).to_dict("records")

for i in range(0, len(rows), 500):
    run_query(query, {"rows": rows[i : i + 500]})

print(f"✅ Loaded {len(rows):,} e-SQA concerns")

# ═══════════════════════════════════════════════════════════
# STEP 10: VERIFICATION
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("VERIFICATION")
print("=" * 80)

with driver.session() as session:
    # Node counts
    result = session.run(
        """
        MATCH (n)
        RETURN labels(n)[0] AS label, count(n) AS count
        ORDER BY count DESC
    """
    )
    print("\n📊 Node Counts:")
    for r in result:
        print(f"  {r['label']}: {r['count']:,}")

    # Relationship counts
    result = session.run(
        """
        MATCH ()-[r]->()
        RETURN type(r) AS relationship, count(r) AS count
        ORDER BY count DESC
    """
    )
    print("\n🔗 Relationship Counts:")
    for r in result:
        print(f"  {r['relationship']}: {r['count']:,}")

print("\n" + "=" * 80)
print("✅ DATA LOAD COMPLETE!")
print("=" * 80)

driver.close()
