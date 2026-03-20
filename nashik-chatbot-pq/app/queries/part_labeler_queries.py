"""
PartLabeler SQL Queries
Queries for managing images and labels in PartLabeler
"""

class PartLabelerQueries:
    INSERT_IMAGE = """
        INSERT INTO images (filename, display_name, user_id)
        VALUES (:filename, :display_name, :user_id)
        RETURNING id
    """

    GET_ALL_IMAGES = """
        SELECT id, filename, created_at, display_name
        FROM images
        WHERE user_id = :user_id
        ORDER BY created_at DESC
    """

    DELETE_IMAGE = """
        DELETE FROM images
        WHERE id = :id AND user_id = :user_id
    """

    INSERT_LABEL = """
        INSERT INTO labels (image_id, part_name, description, part_number, failure_count, report_month, x_coord, y_coord, user_id)
        VALUES (:image_id, :part_name, :description, :part_number, :failure_count, :report_month, :x_coord, :y_coord, :user_id)
        RETURNING id
    """

    DELETE_LABEL = """
        DELETE FROM labels
        WHERE id = :id AND user_id = :user_id
    """

    UPDATE_LABEL_NAME = """
        UPDATE labels
        SET part_name = :part_name
        WHERE id = :id AND user_id = :user_id
    """

    GET_LABELS_FOR_IMAGE = """
        SELECT id, image_id, part_name, description, part_number, failure_count, report_month, x_coord, y_coord
        FROM labels
        WHERE image_id = :image_id AND user_id = :user_id
    """

    GET_UNIQUE_MODELS = """
        SELECT DISTINCT base_model FROM raw_warranty_data 
        WHERE base_model IS NOT NULL AND base_model != '' AND user_id = :user_id
        ORDER BY base_model ASC
    """

    GET_UNIQUE_MIS_BUCKETS = """
        SELECT DISTINCT mis_bucket FROM raw_warranty_data 
        WHERE mis_bucket IS NOT NULL AND mis_bucket != '' AND user_id = :user_id
        ORDER BY mis_bucket ASC
    """

    GET_UNIQUE_MFG_QUARTERS = """
        SELECT DISTINCT new_manufacturing_quater FROM raw_warranty_data 
        WHERE new_manufacturing_quater IS NOT NULL AND new_manufacturing_quater != '' AND user_id = :user_id
        ORDER BY new_manufacturing_quater ASC
    """

    GET_UNIQUE_MFG_MONTHS = """
        SELECT DISTINCT manufac_yr_mon FROM raw_warranty_data 
        WHERE manufac_yr_mon IS NOT NULL AND manufac_yr_mon != '' AND user_id = :user_id
        ORDER BY manufac_yr_mon DESC
    """

    GET_MFG_DATE_RANGE = """
        SELECT 
            MIN(TO_DATE(manufac_yr_mon, 'Mon-YYYY')) as min_date,
            MAX(TO_DATE(manufac_yr_mon, 'Mon-YYYY')) as max_date
        FROM raw_warranty_data
        WHERE user_id = :user_id AND manufac_yr_mon IS NOT NULL AND manufac_yr_mon != ''
    """

    GET_REPORTING_DATE_RANGE = """
        SELECT 
            MIN(TO_DATE(claim_date, 'YYYY-MM-DD')) as min_date,
            MAX(TO_DATE(claim_date, 'YYYY-MM-DD')) as max_date
        FROM raw_warranty_data
        WHERE user_id = :user_id AND claim_date IS NOT NULL AND claim_date != ''
    """

    GET_ALL_WARRANTY_FOR_PART = """
        SELECT * FROM raw_warranty_data
        WHERE (LOWER(REPLACE(material_description, ' ', '')) LIKE :search_term
           OR LOWER(REPLACE(complaint_code_desc, ' ', '')) LIKE :search_term)
           AND (:base_model IS NULL OR base_model = ANY(:base_model))
           AND (:mis_bucket IS NULL OR mis_bucket = ANY(:mis_bucket))
           AND (:mfg_qtr IS NULL OR new_manufacturing_quater = ANY(:mfg_qtr))
           AND (:month_val IS NULL OR manufac_yr_mon = ANY(:month_val))
           AND user_id = :user_id
        ORDER BY failure_date DESC
    """

    # Warranty Record Queries (from raw_warranty_data)
    GET_WARRANTY_DATA = """
        SELECT 
            mode() WITHIN GROUP (ORDER BY material_description) as "partName", 
            manufac_yr_mon as "month", 
            COUNT(*) as "failureCount", 
            mode() WITHIN GROUP (ORDER BY COALESCE(NULLIF(complaint_code_desc, ''), dealer_verbatim)) as "description"
        FROM raw_warranty_data
        WHERE manufac_yr_mon IS NOT NULL AND manufac_yr_mon != ''
          AND (:base_model IS NULL OR base_model = ANY(:base_model))
          AND (:mis_bucket IS NULL OR mis_bucket = ANY(:mis_bucket))
          AND (:mfg_qtr IS NULL OR new_manufacturing_quater = ANY(:mfg_qtr))
          AND user_id = :user_id
        GROUP BY manufac_yr_mon
        ORDER BY manufac_yr_mon DESC
    """

    SEARCH_WARRANTY_DATA = """
        SELECT 
            mode() WITHIN GROUP (ORDER BY material_description) as "partName", 
            manufac_yr_mon as "month", 
            COUNT(*) as "failureCount", 
            mode() WITHIN GROUP (ORDER BY COALESCE(NULLIF(complaint_code_desc, ''), dealer_verbatim)) as "description"
        FROM raw_warranty_data
        WHERE (LOWER(REPLACE(material_description, ' ', '')) LIKE :search_term
           OR LOWER(REPLACE(complaint_code_desc, ' ', '')) LIKE :search_term)
          AND manufac_yr_mon IS NOT NULL AND manufac_yr_mon != ''
          AND (:base_model IS NULL OR base_model = ANY(:base_model))
          AND (:mis_bucket IS NULL OR mis_bucket = ANY(:mis_bucket))
          AND (:mfg_qtr IS NULL OR new_manufacturing_quater = ANY(:mfg_qtr))
          AND user_id = :user_id
        GROUP BY manufac_yr_mon
        ORDER BY manufac_yr_mon DESC
    """

    INSERT_RAW_WARRANTY = """
        INSERT INTO raw_warranty_data (
            region, zone, area_office, plant, plant_desc, commodity, group_code, group_code_desc, 
            complaint_code, complaint_code_desc, base_model, model_code, model_family, claim_type, 
            sap_claim_no, claim_desc, ac_non_ac, variant, drive_type, service_type, billing_dealer, 
            billing_dealer_name, serial_no, claim_date, failure_kms, km_hr_group, dealer_verbatim, 
            part, vender, material_description, causal_flag, jdp_city, fisyr_qrt, engine_number, 
            manufac_yr_mon, failure_date, mis_bucket, walk_home, dealer_code, claim_dealer_name, 
            ro_number, no_of_incidents, new_manufacturing_quater, vendor_manuf, user_id
        ) VALUES (
            :region, :zone, :area_office, :plant, :plant_desc, :commodity, :group_code, :group_code_desc, 
            :complaint_code, :complaint_code_desc, :base_model, :model_code, :model_family, :claim_type, 
            :sap_claim_no, :claim_desc, :ac_non_ac, :variant, :drive_type, :service_type, :billing_dealer, 
            :billing_dealer_name, :serial_no, :claim_date, :failure_kms, :km_hr_group, :dealer_verbatim, 
            :part, :vender, :material_description, :causal_flag, :jdp_city, :fisyr_qrt, :engine_number, 
            :manufac_yr_mon, :failure_date, :mis_bucket, :walk_home, :dealer_code, :claim_dealer_name, 
            :ro_number, :no_of_incidents, :new_manufacturing_quater, :vendor_manuf, :user_id
        )
    """

    GET_DASHBOARD_MFG_MONTH = """
        SELECT manufac_yr_mon as label, COUNT(*) as value
        FROM raw_warranty_data
        WHERE user_id = :user_id
          AND manufac_yr_mon IS NOT NULL AND manufac_yr_mon != ''
          AND (:search_terms IS NULL OR LOWER(REPLACE(material_description, ' ', '')) LIKE ANY(:search_terms) OR LOWER(REPLACE(complaint_code_desc, ' ', '')) LIKE ANY(:search_terms))
          AND (:month_val IS NULL OR manufac_yr_mon = ANY(:month_val))
          AND (:base_model IS NULL OR base_model = ANY(:base_model))
          AND (:mis_bucket IS NULL OR mis_bucket = ANY(:mis_bucket))
          AND (:mfg_qtr IS NULL OR new_manufacturing_quater = ANY(:mfg_qtr))
        GROUP BY manufac_yr_mon
        ORDER BY TO_DATE(manufac_yr_mon, 'Mon-YYYY') ASC
    """

    GET_DASHBOARD_REPORTING_MONTH = """
        SELECT TO_CHAR(TO_DATE(claim_date, 'YYYY-MM-DD'), 'Mon-YYYY') as label, COUNT(*) as value
        FROM raw_warranty_data
        WHERE user_id = :user_id AND claim_date IS NOT NULL AND claim_date != ''
          AND (:search_terms IS NULL OR LOWER(REPLACE(material_description, ' ', '')) LIKE ANY(:search_terms) OR LOWER(REPLACE(complaint_code_desc, ' ', '')) LIKE ANY(:search_terms))
          AND (:month_val IS NULL OR manufac_yr_mon = ANY(:month_val))
          AND (:base_model IS NULL OR base_model = ANY(:base_model))
          AND (:mis_bucket IS NULL OR mis_bucket = ANY(:mis_bucket))
          AND (:mfg_qtr IS NULL OR new_manufacturing_quater = ANY(:mfg_qtr))
        GROUP BY 1
        ORDER BY MIN(TO_DATE(claim_date, 'YYYY-MM-DD')) ASC
    """

    GET_DASHBOARD_KMS = """
        SELECT 
            CASE 
                WHEN CAST(NULLIF(REGEXP_REPLACE(failure_kms, '[^0-9.]', '', 'g'), '') AS FLOAT) <= 1000 THEN '0-1k'
                WHEN CAST(NULLIF(REGEXP_REPLACE(failure_kms, '[^0-9.]', '', 'g'), '') AS FLOAT) <= 2000 THEN '1k-2k'
                WHEN CAST(NULLIF(REGEXP_REPLACE(failure_kms, '[^0-9.]', '', 'g'), '') AS FLOAT) <= 5000 THEN '2k-5k'
                WHEN CAST(NULLIF(REGEXP_REPLACE(failure_kms, '[^0-9.]', '', 'g'), '') AS FLOAT) <= 10000 THEN '5k-10k'
                WHEN CAST(NULLIF(REGEXP_REPLACE(failure_kms, '[^0-9.]', '', 'g'), '') AS FLOAT) <= 20000 THEN '10k-20k'
                WHEN CAST(NULLIF(REGEXP_REPLACE(failure_kms, '[^0-9.]', '', 'g'), '') AS FLOAT) <= 30000 THEN '20k-30k'
                ELSE '30k above'
            END as label,
            COUNT(*) as value
        FROM raw_warranty_data
        WHERE user_id = :user_id AND failure_kms IS NOT NULL AND failure_kms != ''
          AND (:search_terms IS NULL OR LOWER(REPLACE(material_description, ' ', '')) LIKE ANY(:search_terms) OR LOWER(REPLACE(complaint_code_desc, ' ', '')) LIKE ANY(:search_terms))
          AND (:month_val IS NULL OR manufac_yr_mon = ANY(:month_val))
          AND (:base_model IS NULL OR base_model = ANY(:base_model))
          AND (:mis_bucket IS NULL OR mis_bucket = ANY(:mis_bucket))
          AND (:mfg_qtr IS NULL OR new_manufacturing_quater = ANY(:mfg_qtr))
        GROUP BY 1
        ORDER BY MIN(CASE 
            WHEN CAST(NULLIF(REGEXP_REPLACE(failure_kms, '[^0-9.]', '', 'g'), '') AS FLOAT) <= 1000 THEN 1
            WHEN CAST(NULLIF(REGEXP_REPLACE(failure_kms, '[^0-9.]', '', 'g'), '') AS FLOAT) <= 2000 THEN 2
            WHEN CAST(NULLIF(REGEXP_REPLACE(failure_kms, '[^0-9.]', '', 'g'), '') AS FLOAT) <= 5000 THEN 3
            WHEN CAST(NULLIF(REGEXP_REPLACE(failure_kms, '[^0-9.]', '', 'g'), '') AS FLOAT) <= 10000 THEN 4
            WHEN CAST(NULLIF(REGEXP_REPLACE(failure_kms, '[^0-9.]', '', 'g'), '') AS FLOAT) <= 20000 THEN 5
            WHEN CAST(NULLIF(REGEXP_REPLACE(failure_kms, '[^0-9.]', '', 'g'), '') AS FLOAT) <= 30000 THEN 6
            ELSE 7 END) ASC
    """

    GET_DASHBOARD_REGION = """
        SELECT region as label, COUNT(*) as value
        FROM raw_warranty_data
        WHERE user_id = :user_id AND region IS NOT NULL AND region != ''
          AND (:search_terms IS NULL OR LOWER(REPLACE(material_description, ' ', '')) LIKE ANY(:search_terms) OR LOWER(REPLACE(complaint_code_desc, ' ', '')) LIKE ANY(:search_terms))
          AND (:month_val IS NULL OR manufac_yr_mon = ANY(:month_val))
          AND (:base_model IS NULL OR base_model = ANY(:base_model))
          AND (:mis_bucket IS NULL OR mis_bucket = ANY(:mis_bucket))
          AND (:mfg_qtr IS NULL OR new_manufacturing_quater = ANY(:mfg_qtr))
        GROUP BY region
        ORDER BY value DESC
    """
