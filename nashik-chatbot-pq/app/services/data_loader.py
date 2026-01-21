
import os
import pandas as pd
import logging
import re
from pathlib import Path
from neo4j import GraphDatabase
from app.config.config import get_settings

logger = logging.getLogger(__name__)

def load_data(csv_folder_path: str):
    """
    Loads data from CSV files in the specified folder into Neo4j.
    """
    settings = get_settings()
    
    # Connect to Neo4j using settings
    driver = GraphDatabase.driver(
        settings.NEO4J_URL, 
        auth=(settings.NEO4J_USERNAME, settings.NEO4J_PASSWORD)
    )

    def run_query(query, params=None):
        with driver.session() as session:
            session.run(query, params or {})

    try:
        csv_folder = Path(csv_folder_path)
        if not csv_folder.exists():
            raise FileNotFoundError(f"Folder not found: {csv_folder}")

        print("=" * 80)
        print("LOADING CSV FILES")
        print("=" * 80)

        # Helper to find file safely
        def find_file(keyword):
            for f in os.listdir(csv_folder):
                if keyword.lower() in f.lower() and f.endswith(".csv"):
                    return csv_folder / f
            return None

        # Load specific files based on keywords matching the original script
        # Original: "1. THAR ROXX PPCM_Sheet1.csv"
        ppcm_path = find_file("PPCM")
        # Original: "2. THAR ROXX Warranty_Sheet1_FILTERED.csv"
        warranty_path = find_file("Warranty_Sheet1") 
        # Original: "3. THAR ROXX Warranty Analysis_Sheet1_FILTERED.csv"
        analysis_path = find_file("Warranty Analysis")
        # Original: "4. THAR ROXX e-SQA_Sheet1.csv"
        esqa_path = find_file("e-SQA")

        if not all([ppcm_path, warranty_path, analysis_path, esqa_path]):
            print("⚠️ Warning: Some standard files (PPCM, Warranty, Analysis, e-SQA) were not found.")
            print(f"  PPCM: {ppcm_path}")
            print(f"  Warranty: {warranty_path}")
            print(f"  Analysis: {analysis_path}")
            print(f"  e-SQA: {esqa_path}")
            # Depending on requirements, we might want to return or raise here.
            # For now, let's proceed but this will likely fail if pandas tries to read None.
            # Better to strictly check.
        
        # We need to handle missing files gracefully or fail. 
        # The prompt implies the user provides a folder with THE csvs.
        if not ppcm_path: raise FileNotFoundError("PPCM csv not found")
        if not warranty_path: raise FileNotFoundError("Warranty csv not found")
        if not analysis_path: raise FileNotFoundError("Warranty Analysis csv not found")
        if not esqa_path: raise FileNotFoundError("e-SQA csv not found")

        ppcm = pd.read_csv(ppcm_path)
        warranty = pd.read_csv(warranty_path)
        warranty_analysis = pd.read_csv(analysis_path)
        esqa = pd.read_csv(esqa_path)

        # Load ALL traceability files
        trace_files = [
            f for f in os.listdir(csv_folder) if "traceability" in f.lower() and f.endswith(".csv")
        ]
        print(f"Found {len(trace_files)} traceability files")
        if not trace_files:
             raise FileNotFoundError("No traceability files found")

        trace = pd.concat(
            [pd.read_csv(csv_folder / f, low_memory=False) for f in trace_files], ignore_index=True
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

        print("✅ Filled missing values with 'unknown'")

        # Clean vendor names
        if "vender" in warranty.columns:
            warranty["vender"] = warranty["vender"].replace(["-", "", "N/A", " "], "unknown")

        # CRITICAL: Extract VIN suffix (last 8 chars) from traceability
        if "VINNumber" in trace.columns:
            trace["VIN_SHORT"] = trace["VINNumber"].str[-8:]
            print("✅ Extracted short VIN (last 8 chars) from traceability")
        else:
            print("⚠️ 'VINNumber' column missing in traceability data")

        # ═══════════════════════════════════════════════════════════
        # PART NUMBER NORMALIZATION
        # ═══════════════════════════════════════════════════════════
        def normalize_part_number(part_value):
            if pd.isna(part_value) or part_value == "" or part_value == "unknown":
                return "unknown"
            part = str(part_value).strip()
            part = part.replace("_x000d_", "").replace("_X000D_", "")
            part = part.replace("\r", "").replace("\n", "").replace("\t", "")
            part = part.strip().upper()
            pattern = r"^[0-9]{4}[A-Z]{2,3}[0-9]{5,6}[A-Z]$"
            if re.match(pattern, part):
                return part
            j_pattern = r"^J[0-9]{2}-[A-Z]{3}-[0-9]{4}$"
            if re.match(j_pattern, part):
                return part
            if len(part) > 50 or " " in part or len(part) < 5:
                return "unknown"
            return "unknown"

        print("\n🔧 Normalizing part numbers...")

        if "part" in warranty.columns:
            warranty["part_original"] = warranty["part"]
            warranty["part"] = warranty["part"].apply(normalize_part_number)
        
        if "Part No" in ppcm.columns:
            ppcm["Part No"] = ppcm["Part No"].apply(normalize_part_number)
        
        if "Part No" in esqa.columns:
            esqa["Part No"] = esqa["Part No"].apply(normalize_part_number)
        
        if "BOMPARTNO" in trace.columns:
            trace["BOMPARTNO"] = trace["BOMPARTNO"].apply(normalize_part_number)

        print(f"✅ Part number normalization complete")

        # CRITICAL: Parse ScanValue
        def parse_scan_value(scan_val):
            try:
                if pd.isna(scan_val) or scan_val == "unknown":
                    return "unknown", "unknown", scan_val
                parts = str(scan_val).split(":")
                if len(parts) >= 3:
                    date_part = parts[-3] if len(parts) >= 3 else "unknown"
                    shift_part = parts[-2] if len(parts) >= 2 else "unknown"
                    batch_code = parts[-1] if len(parts) >= 1 else scan_val
                    return date_part, shift_part, batch_code
                else:
                    return "unknown", "unknown", scan_val
            except:
                return "unknown", "unknown", scan_val

        if "ScanValue" in trace.columns:
            trace[["BATCH_DATE", "SHIFT", "BATCH_CODE"]] = trace["ScanValue"].apply(
                lambda x: pd.Series(parse_scan_value(x))
            )
            print("✅ VIN extraction and ScanValue parsing complete")

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
            except Exception as e:
                print(f"Constraint warning: {e}")
        print("✅ Constraints created")

        # ═══════════════════════════════════════════════════════════
        # STEP 5: LOAD TRACEABILITY
        # ═══════════════════════════════════════════════════════════
        print("\n" + "=" * 80)
        print("1. LOADING TRACEABILITY (Part → VIN → Batch)")
        print("=" * 80)

        query_trace = """
        UNWIND $rows AS row
        MERGE (v:Vehicle {vin: row.vin_short})
        SET v.full_vin = row.full_vin
        MERGE (p:Part {part_no: row.part_no})
        MERGE (p)-[f:FITTED_ON]->(v)
        SET f.date = row.tdate, 
            f.scan_value = row.scan_value,
            f.batch_date = row.batch_date,
            f.shift = row.shift
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
        rows = [r for r in rows if r["vin_short"] != "unknown" and r["part_no"] != "unknown"]
        
        batch_size = 1000
        total_rows = len(rows)
        for i in range(0, total_rows, batch_size):
            run_query(query_trace, {"rows": rows[i : i + batch_size]})
            if i % 10000 == 0 and i > 0:
                print(f"   Progress: {i:,}/{total_rows:,}")
        print(f"✅ Loaded {len(rows):,} traceability records")

        # ═══════════════════════════════════════════════════════════
        # STEP 6: LOAD PPCM
        # ═══════════════════════════════════════════════════════════
        print("\n" + "=" * 80)
        print("2. LOADING PPCM")
        print("=" * 80)

        query_ppcm = """
        UNWIND $rows AS row
        MERGE (v:Vendor {name: row.vendor_name})
        MERGE (p:Part {part_no: row.part_no})
        SET p.model = row.model, 
            p.characteristic = row.characteristic,
            p.specification = row.specification
        MERGE (v)-[:SUPPLIES]->(p)
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
            run_query(query_ppcm, {"rows": rows[i : i + 500]})
        print(f"✅ Loaded {len(rows):,} PPCM records")

        # ═══════════════════════════════════════════════════════════
        # STEP 7: LOAD WARRANTY
        # ═══════════════════════════════════════════════════════════
        print("\n" + "=" * 80)
        print("3. LOADING WARRANTY")
        print("=" * 80)

        query_warranty = """
        UNWIND $rows AS row
        MERGE (w:WarrantyClaim {claim_no: row.claim_no})
        SET w.complaint_code = row.complaint_code, 
            w.complaint_desc = row.complaint_desc,
            w.failure_date = row.failure_date, 
            w.failure_kms = row.failure_kms,
            w.claim_date = row.claim_date, 
            w.incidents = toInteger(row.incidents),
            w.region = row.region, 
            w.zone = row.zone
        MERGE (v:Vehicle {vin: row.serial_no})
        SET v.model = row.model_code, 
            v.engine_no = row.engine_no
        MERGE (d:Dealer {code: row.dealer_code})
        SET d.name = row.dealer_name
        MERGE (pl:Plant {code: row.plant})
        SET pl.desc = row.plant_desc
        MERGE (c:Commodity {name: row.commodity})
        MERGE (p:Part {part_no: row.part})
        MERGE (v)-[:HAS_CLAIM]->(w)
        MERGE (w)-[:FILED_AT]->(d)
        MERGE (w)-[:INVOLVES_PART]->(p)
        MERGE (v)-[:MANUFACTURED_AT]->(pl)
        MERGE (p)-[:BELONGS_TO]->(c)
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
            run_query(query_warranty, {"rows": rows[i : i + 500]})
        print(f"✅ Loaded {len(rows):,} warranty claims")

        # ═══════════════════════════════════════════════════════════
        # STEP 8: LOAD WARRANTY ANALYSIS
        # ═══════════════════════════════════════════════════════════
        print("\n" + "=" * 80)
        print("4. LOADING WARRANTY ANALYSIS")
        print("=" * 80)

        query_by_claim = """
        UNWIND $rows AS row
        MATCH (w:WarrantyClaim {claim_no: row.claim_no})
        SET w.decision = row.decision, 
            w.attribution = row.attribution
        WITH w, row WHERE row.commodity <> 'unknown' AND row.commodity <> ''
        MERGE (c:Commodity {name: row.commodity})
        MERGE (w)-[:INVOLVES_COMMODITY]->(c)
        """
        query_by_serial = """
        UNWIND $rows AS row
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
        rows_with_claim = [r for r in rows if r["claim_no"] != "unknown" and r["claim_no"] != ""]
        rows_without_claim = [r for r in rows if r["claim_no"] == "unknown" or r["claim_no"] == ""]
        
        for i in range(0, len(rows_with_claim), 500):
            run_query(query_by_claim, {"rows": rows_with_claim[i : i + 500]})
        for i in range(0, len(rows_without_claim), 500):
            run_query(query_by_serial, {"rows": rows_without_claim[i : i + 500]})
        print(f"✅ Loaded {len(rows):,} warranty analysis records")

        # ═══════════════════════════════════════════════════════════
        # STEP 9: LOAD e-SQA
        # ═══════════════════════════════════════════════════════════
        print("\n" + "=" * 80)
        print("5. LOADING e-SQA")
        print("=" * 80)

        query_esqa = """
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
            run_query(query_esqa, {"rows": rows[i : i + 500]})
        print(f"✅ Loaded {len(rows):,} e-SQA concerns")

        print("\n" + "=" * 80)
        print("✅ DATA LOAD COMPLETE!")
        print("=" * 80)

    except Exception as e:
        print(f"❌ Error during data loading: {e}")
        raise
    finally:
        driver.close()
