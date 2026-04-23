import os
import csv
import logging
from app.connectors.state_db_connector import StateDBConnector
from app.queries.part_labeler_queries import PartLabelerQueries
from sqlalchemy import text

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def process_warranty_to_db():
    # The CSV is located in PartLabeler/csv_output relative to project root
    csv_path = r"C:\Users\50014665\GraphRag\Traceability\nashik-chatbot-pq\PartLabeler\csv_output\2. THAR ROXX Warranty_Sheet1_FILTERED.csv"

    if not os.path.exists(csv_path):
        logger.error(f"CSV file not found at {csv_path}")
        return

    db = StateDBConnector()
    
    # Mapping CSV headers to DB columns
    column_mapping = {
        'Region': 'region',
        'Zone': 'zone',
        'Area Office': 'area_office',
        'Plant': 'plant',
        'PlantDesc': 'plant_desc',
        'Commodity': 'commodity',
        'Group Code': 'group_code',
        'Group Code Desc': 'group_code_desc',
        'Complaint Code': 'complaint_code',
        'Complaint Code Desc': 'complaint_code_desc',
        'BASE MODEL': 'base_model',
        'Model Code': 'model_code',
        'Model Family': 'model_family',
        'Claim Type': 'claim_type',
        'SAP Claim No': 'sap_claim_no',
        'Claim Desc': 'claim_desc',
        'AC / Non AC': 'ac_non_ac',
        'Variant': 'variant',
        'Drive Type': 'drive_type',
        'Service Type': 'service_type',
        'Billing Dealer': 'billing_dealer',
        'Billing Dealer Name': 'billing_dealer_name',
        'Serial No': 'serial_no',
        'Claim Date': 'claim_date',
        'Failure Kms': 'failure_kms',
        'KmHrGroup': 'km_hr_group',
        'Dealer Verbatim': 'dealer_verbatim',
        'part': 'part',
        'vender': 'vender',
        'Material Description': 'material_description',
        'Causal Flag': 'causal_flag',
        'JDP City': 'jdp_city',
        'FisYr Qrt': 'fisyr_qrt',
        'ENGINE NUMBER': 'engine_number',
        'Manufac_Yr_Mon': 'manufac_yr_mon',
        'Failure Date': 'failure_date',
        'MIS_BUCKET': 'mis_bucket',
        'Walk Home': 'walk_home',
        'Dealer Code': 'dealer_code',
        'Claim Dealer Name': 'claim_dealer_name',
        'RONumber': 'ro_number',
        'No. of Incidents': 'no_of_incidents',
        'New Manufacturing Quater': 'new_manufacturing_quater',
        'Vendor/Manuf.': 'vendor_manuf'
    }

    try:
        with open(csv_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            # Clear existing data
            logger.info("Clearing existing raw warranty data...")
            db.execute_update("DELETE FROM raw_warranty_data")
            
            # Prepare batch insert
            records = []
            count = 0
            
            for row in reader:
                record = {}
                for csv_col, db_col in column_mapping.items():
                    record[db_col] = row.get(csv_col, '').strip()
                
                records.append(record)
                count += 1
                
                # Batch insert every 500 records
                if len(records) >= 500:
                    _insert_batch(db, records)
                    records = []
                    logger.info(f"Processed {count} records...")
            
            # Insert remaining records
            if records:
                _insert_batch(db, records)
            
            logger.info(f"Successfully loaded {count} records into raw_warranty_data")

    except Exception as e:
        logger.error(f"Error processing warranty data: {str(e)}")

def _insert_batch(db, records):
    if not records:
        return
    
    with db.get_session() as session:
        session.execute(text(PartLabelerQueries.INSERT_RAW_WARRANTY), records)