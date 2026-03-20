import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Upload,
  Search,
  Trash2,
  Edit2,
  X,
  Check,
  BarChart2,
  Info,
  MapPin,
  ChevronRight,
  ChevronDown,
  Layout,
  AlertCircle,
  Download,
  Database,
  FileSpreadsheet,
  Layers,
  Map as MapIcon,
  Activity,
  History,
  ChevronUp
} from 'lucide-react';
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip as RechartsTooltip, 
  ResponsiveContainer, 
  Cell,
  Legend,
  LabelList
} from 'recharts';
import { ComposableMap, Geographies, Geography } from "react-simple-maps";
import { scaleLinear } from "d3-scale";
import { backend_url } from '../../services/api/config';
import './PartLabeler.css';

const API_BASE = `${backend_url}/part-labeler`;
const UPLOAD_BASE = backend_url.endsWith('/api')
  ? backend_url.replace('/api', '/uploads')
  : backend_url.replace('/api/', '/uploads/');

// =====================================================
// DATA SOURCE CONFIGURATION
// =====================================================
const DATA_SOURCES = {
  warranty: {
    key: 'warranty',
    label: 'Warranty Data',
    chartTitles: {
      mfgMonth: 'Vehicle Mfg Month Wise Data',
      reportingMonth: 'Reporting Month Wise Data',
      kms: 'Kms Wise Data',
      region: 'Locationwise Distribution',
    },
    useMapForRegion: true,
    targetColumns: [
      { key: 'complaint_code_desc', label: 'Complaint Code Desc', mandatory: true, group: 'Required' },
      { key: 'material_description', label: 'Material Description', mandatory: true, group: 'Required' },
      { key: 'manufac_yr_mon', label: 'Manufac_Yr_Mon', mandatory: true, group: 'Required' },
      { key: 'new_manufacturing_quater', label: 'New Manufacturing Quater', mandatory: true, group: 'Required' },
      { key: 'mis_bucket', label: 'MIS_BUCKET', mandatory: true, group: 'Required' },
      { key: 'base_model', label: 'BASE MODEL', mandatory: true, group: 'Required' },
      { key: 'claim_date', label: 'Claim Date', mandatory: true, group: 'Required' },
      { key: 'failure_kms', label: 'Failure Kms', mandatory: true, group: 'Required' },
      { key: 'region', label: 'Region', mandatory: true, group: 'Required' },
      { key: 'failure_date', label: 'Failure Date', group: 'Technical' },
      { key: 'part', label: 'part', group: 'Technical' },
      { key: 'serial_no', label: 'Serial No', group: 'Technical' },
      { key: 'vender', label: 'vender', group: 'Technical' },
      { key: 'vendor_manuf', label: 'Vendor/Manuf.', group: 'Technical' },
      { key: 'zone', label: 'Zone', group: 'Geography' },
      { key: 'area_office', label: 'Area Office', group: 'Geography' },
      { key: 'plant', label: 'Plant', group: 'Geography' },
      { key: 'plant_desc', label: 'PlantDesc', group: 'Geography' },
      { key: 'jdp_city', label: 'JDP City', group: 'Geography' },
      { key: 'commodity', label: 'Commodity', group: 'Classification' },
      { key: 'group_code', label: 'Group Code', group: 'Classification' },
      { key: 'group_code_desc', label: 'Group Code Desc', group: 'Classification' },
      { key: 'complaint_code', label: 'Complaint Code', group: 'Classification' },
      { key: 'model_code', label: 'Model Code', group: 'Classification' },
      { key: 'model_family', label: 'Model Family', group: 'Classification' },
      { key: 'claim_type', label: 'Claim Type', group: 'Claim Info' },
      { key: 'sap_claim_no', label: 'SAP Claim No', group: 'Claim Info' },
      { key: 'claim_desc', label: 'Claim Desc', group: 'Claim Info' },
      { key: 'service_type', label: 'Service Type', group: 'Claim Info' },
      { key: 'ro_number', label: 'RONumber', group: 'Claim Info' },
      { key: 'dealer_code', label: 'Dealer Code', group: 'Dealer' },
      { key: 'billing_dealer_name', label: 'Billing Dealer Name', group: 'Dealer' },
      { key: 'dealer_verbatim', label: 'Dealer Verbatim', group: 'Dealer' },
      { key: 'ac_non_ac', label: 'AC / Non AC', group: 'Specs' },
      { key: 'variant', label: 'Variant', group: 'Specs' },
      { key: 'drive_type', label: 'Drive Type', group: 'Specs' },
    ],
  },
  rpt: {
    key: 'rpt',
    label: 'Offline RPT Data',
    chartTitles: {
      mfgMonth: 'Vehicle Mfg Month Wise Data',
      reportingMonth: 'Attribute Name Wise Data',
      kms: 'Shift Wise Data',
      region: 'Location Name Wise Distribution',
    },
    useMapForRegion: false,
    targetColumns: [
      { key: 'date_col', label: 'DATE', mandatory: true, group: 'Required', hint: 'e.g. 2026-01-01' },
      { key: 'model', label: 'Model', mandatory: true, group: 'Required' },
      { key: 'defect_category', label: 'Defect_Category', mandatory: true, group: 'Required', hint: 'Used for MIS filter' },
      { key: 'part_defect', label: 'PartDefect', mandatory: true, group: 'Required', hint: 'Used for failure search' },
      { key: 'attribute_name', label: 'Attribute_Name', mandatory: true, group: 'Required', hint: 'Used for Reporting Month chart' },
      { key: 'location_name', label: 'Location_Name', mandatory: true, group: 'Required', hint: 'Used for Location chart' },
      { key: 'shift', label: 'Shift', mandatory: true, group: 'Required', hint: 'Used for Shift/KMS chart' },
      { key: 'body_sr_no', label: 'BODYSRNO', group: 'Vehicle Info' },
      { key: 'vin_number', label: 'VIN_Number', group: 'Vehicle Info' },
      { key: 'buyoff_stage', label: 'Buyoff Stage', group: 'Vehicle Info' },
      { key: 'platform_group', label: 'Platform Group', group: 'Vehicle Info' },
      { key: 'stage_name', label: 'Stage Name', group: 'Vehicle Info' },
      { key: 'part', label: 'PART', group: 'Defect Info' },
      { key: 'defect', label: 'Defect', group: 'Defect Info' },
      { key: 'custom_attribution', label: 'Custom Attribution', group: 'Defect Info' },
      { key: 'offline_val', label: '_Offline', group: 'Defect Info' },
      { key: 'online_val', label: '_Online', group: 'Defect Info' },
      { key: 'rework_status', label: 'REWORK_STATUS', group: 'Defect Info' },
      { key: 'defect_status', label: 'DEFECT_STATUS', group: 'Defect Info' },
      { key: 'as_is_ok', label: 'As_Is_Ok', group: 'Defect Info' },
      { key: 'shop_name', label: 'Shop_Name', group: 'Other' },
      { key: 'model_description', label: 'Model_Description', group: 'Other' },
      { key: 'model_code', label: 'ModelCode', group: 'Other' },
      { key: 'severity_name', label: 'Severity Name', group: 'Other' },
      { key: 'domestic_export', label: 'Domestic/Export', group: 'Other' },
    ],
  },
  gnovac: {
    key: 'gnovac',
    label: 'GNOVAC Data',
    chartTitles: {
      mfgMonth: 'Vehicle Mfg Month Wise Data',
      reportingMonth: 'Attribution Wise Data',
      kms: 'Concern Severity (Pointer) Wise Data',
      region: 'Location Name Wise Distribution',
    },
    useMapForRegion: false,
    targetColumns: [
      { key: 'audit_date', label: 'Audit Date', mandatory: true, group: 'Required', hint: 'e.g. 2026-01-01' },
      { key: 'model_code', label: 'Model Code', mandatory: true, group: 'Required', hint: 'Used for Model filter' },
      { key: 'pointer', label: 'Pointer', mandatory: true, group: 'Required', hint: 'Used for MIS filter & KMS chart' },
      { key: 'part_name', label: 'Part Name', mandatory: true, group: 'Required', hint: 'Used for failure search' },
      { key: 'defect_name', label: 'Defect Name', mandatory: true, group: 'Required', hint: 'Used for failure search' },
      { key: 'attribution', label: 'Attribution', mandatory: true, group: 'Required', hint: 'Used for Reporting Month chart' },
      { key: 'location_name', label: 'Location Name', mandatory: true, group: 'Required', hint: 'Used for Location chart' },
      { key: 'vin_no', label: 'VIN No', group: 'Vehicle Info' },
      { key: 'plant_name', label: 'Plant Name', group: 'Vehicle Info' },
      { key: 'variant_name', label: 'Variant Name', group: 'Vehicle Info' },
      { key: 'fuel_type', label: 'Fuel Type', group: 'Vehicle Info' },
      { key: 'build_phase_name', label: 'BuildPhase Name', group: 'Vehicle Info' },
      { key: 'body_no', label: 'Body No', group: 'Vehicle Info' },
      { key: 'concern_type_name', label: 'Concern Type Name', group: 'Defect Info' },
      { key: 'four_m', label: '4M', group: 'Analysis' },
      { key: 'four_m_analysis_name', label: '4M Analysis Name', group: 'Analysis' },
      { key: 'root_cause', label: 'Root Cause', group: 'Analysis' },
      { key: 'ica', label: 'ICA', group: 'Analysis' },
      { key: 'pca', label: 'PCA', group: 'Analysis' },
      { key: 'responsibility', label: 'Responsibility', group: 'Analysis' },
      { key: 'target_date', label: 'Target Date', group: 'Analysis' },
      { key: 'status', label: 'Status', group: 'Other' },
      { key: 'frequency', label: 'Frequency', group: 'Other' },
      { key: 'new_and_repeat', label: 'New and repeat', group: 'Other' },
      { key: 'remark', label: 'Remark', group: 'Other' },
    ],
  },
  rfi: {
    key: 'rfi',
    label: 'RFI Data',
    chartTitles: {
      mfgMonth: 'Vehicle Mfg Month Wise Data',
      reportingMonth: 'Attribution Name Wise Data',
      kms: 'DefectType & Severity Wise Data',
      region: 'Area Name Wise Distribution',
    },
    useMapForRegion: false,
    targetColumns: [
      { key: 'date_col', label: 'Date', mandatory: true, group: 'Required', hint: 'e.g. 2025-04-01' },
      { key: 'model_name', label: 'Model Name', mandatory: true, group: 'Required', hint: 'Used for Model filter' },
      { key: 'severity_name', label: 'Severity Name', mandatory: true, group: 'Required', hint: 'Used for MIS filter & KMS chart' },
      { key: 'part_name', label: 'Part Name', mandatory: true, group: 'Required', hint: 'Used for failure search' },
      { key: 'defect_name', label: 'Defect Name', mandatory: true, group: 'Required', hint: 'Used for failure search' },
      { key: 'attribution_name', label: 'Attribution Name', mandatory: true, group: 'Required', hint: 'Used for Reporting Month chart' },
      { key: 'area_name', label: 'Area Name', mandatory: true, group: 'Required', hint: 'Used for Location chart' },
      { key: 'defect_type_name', label: 'DefectType Name', mandatory: true, group: 'Required', hint: 'Used for KMS joint chart' },
      { key: 'plant_name', label: 'Plant Name', group: 'Vehicle Info' },
      { key: 'vin_no', label: 'Vin No', group: 'Vehicle Info' },
      { key: 'biw_no', label: 'BIW No', group: 'Vehicle Info' },
      { key: 'variant', label: 'Variant', group: 'Vehicle Info' },
      { key: 'fuel', label: 'Fuel', group: 'Vehicle Info' },
      { key: 'drive_name', label: 'Drive Name', group: 'Vehicle Info' },
      { key: 'build_phase_name', label: 'Build Phase Name', group: 'Vehicle Info' },
      { key: 'software_v_name', label: 'SoftwareV Name', group: 'Vehicle Info' },
      { key: 'color_name', label: 'Color Name', group: 'Vehicle Info' },
      { key: 'country_name', label: 'Country Name', group: 'Vehicle Info' },
      { key: 'location_name', label: 'Location Name', group: 'Defect Info' },
      { key: 'stage_name', label: 'Stage Name', group: 'Analysis' },
      { key: 'root_cause', label: 'Root Cause', group: 'Analysis' },
      { key: 'ica', label: 'ICA', group: 'Analysis' },
      { key: 'pca', label: 'PCA', group: 'Analysis' },
      { key: 'target_date', label: 'Target Date', group: 'Analysis' },
      { key: 'responsibility', label: 'Responsibility', group: 'Other' },
      { key: 'status', label: 'Status', group: 'Other' },
      { key: 'category_name', label: 'Category Name', group: 'Other' },
      { key: 'analysis_name', label: 'Analysis Name', group: 'Other' },
      { key: 'action_plan_status', label: 'Action plan status', group: 'Other' },
      { key: 'frequency', label: 'Frequency', group: 'Other' },
    ],
  },
  esqa: {
    key: 'esqa',
    label: 'e-SQA Data',
    chartTitles: {
      mfgMonth: 'Vehicle Mfg Month Wise Data',
      reportingMonth: 'Commodity Wise Data',
      kms: 'Concern Source Wise Data',
      region: 'Concern Severity Wise Distribution',
    },
    useMapForRegion: false,
    targetColumns: [
      { key: 'concern_report_date', label: 'Concern Report Date', mandatory: true, group: 'Required', hint: 'e.g. 2024-07-23' },
      { key: 'vehicle_model', label: 'Vehicle Model', mandatory: true, group: 'Required', hint: 'Used for Model filter' },
      { key: 'concern_category', label: 'Concern Catergory', mandatory: true, group: 'Required', hint: 'Used for MIS filter' },
      { key: 'part_name', label: 'Part Name', mandatory: true, group: 'Required', hint: 'Used for failure search' },
      { key: 'concern_description', label: 'Concern Description', mandatory: true, group: 'Required', hint: 'Used for failure search' },
      { key: 'commodity', label: 'Commodity', mandatory: true, group: 'Required', hint: 'Used for Reporting Month chart' },
      { key: 'concern_source', label: 'Concern Source', mandatory: true, group: 'Required', hint: 'Used for KMS chart' },
      { key: 'concern_severity', label: 'Concern Severity', mandatory: true, group: 'Required', hint: 'Used for Location chart' },
      { key: 'concern_number', label: 'Concern Number', group: 'Concern Info' },
      { key: 'pu_name', label: 'Pu Name', group: 'Concern Info' },
      { key: 'part_no', label: 'Part No', group: 'Concern Info' },
      { key: 'vendor_code', label: 'Vendor Code', group: 'Concern Info' },
      { key: 'vendor_name', label: 'Vendor Name', group: 'Concern Info' },
      { key: 'vehicle_variant', label: 'Vehicle Variant', group: 'Vehicle Info' },
      { key: 'concern_repeat', label: 'Concern Repeat', group: 'Vehicle Info' },
      { key: 'concern_attribution', label: 'Concern Attribution', group: 'Analysis' },
      { key: 'initial_analysis', label: 'Initial Analysis & Reason', group: 'Analysis' },
      { key: 'sqa_officer', label: 'SQA Officer', group: 'Analysis' },
      { key: 'ica_possible', label: 'ICA Possible', group: 'Analysis' },
      { key: 'reason_ica_not_possible', label: 'Reason for ICA Not Possible', group: 'Analysis' },
      { key: 'ica_details', label: 'ICA Details at M&M', group: 'Analysis' },
      { key: 'ica_failure', label: 'ICA Failure', group: 'Analysis' },
      { key: 'qty_reported', label: 'Qty. Reported', group: 'Quantities' },
      { key: 'segregation_qty', label: 'Segregation Qty', group: 'Quantities' },
      { key: 'ok_qty', label: 'OK Qty', group: 'Quantities' },
      { key: 'rejection_qty', label: 'Rejection Qty', group: 'Quantities' },
      { key: 'scrap_qty', label: 'Scrap Qty', group: 'Quantities' },
      { key: 'rework_qty', label: 'Rework Qty', group: 'Quantities' },
      { key: 'esqa_number', label: 'ESQA Number', group: 'ESQA' },
      { key: 'esqa_posting_date', label: 'ESQA Posting Date', group: 'ESQA' },
    ],
  },
};

// Use the local TopoJSON file from the public folder
const INDIA_TOPO_JSON = "/india-topo.json";

/**
 * Helper Components (Outside main component for better performance)
 */

// =====================================================
// DATA SOURCE SELECTOR COMPONENT
// =====================================================
const DataSourceSelector = ({ current, onChange }) => {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <div className="data-source-selector" ref={ref}>
      <button className="ds-toggle" onClick={() => setOpen(!open)}>
        <Database size={15} />
        <span className="ds-label">Data Source:</span>
        <span className="ds-value">{DATA_SOURCES[current].label}</span>
        <ChevronDown size={13} className={open ? 'ds-chevron open' : 'ds-chevron'} />
      </button>
      {open && (
        <div className="ds-dropdown">
          {Object.values(DATA_SOURCES).map(src => (
            <div
              key={src.key}
              className={`ds-option ${current === src.key ? 'active' : ''}`}
              onClick={() => { onChange(src.key); setOpen(false); }}
            >
              {src.label}
              {current === src.key && <Check size={13} className="ds-check" />}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// =====================================================
// LOCATION BAR CHART (for non-warranty sources)
// =====================================================
const LocationBarChart = ({ data, title }) => (
  <div className="dashboard-chart-card">
    <div className="chart-header">
      <MapIcon size={16} />
      <span>{title}</span>
    </div>
    <div className="chart-container-inner">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 20, right: 5, left: -30, bottom: 20 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f0f0f0" />
          <XAxis
            dataKey="label"
            fontSize={9}
            tick={{ fill: '#7f8c8d' }}
            axisLine={{ stroke: '#e9ecef' }}
            tickLine={false}
            interval={0}
            angle={-30}
            textAnchor="end"
            height={40}
          />
          <YAxis fontSize={10} tick={{ fill: '#7f8c8d' }} axisLine={false} tickLine={false} />
          <RechartsTooltip cursor={{ fill: '#fff5f5' }} contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }} />
          <Bar dataKey="value" fill="#667eea" radius={[4, 4, 0, 0]} barSize={10}>
            <LabelList dataKey="value" position="top" fontSize={8} fill="#7f8c8d" offset={5} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  </div>
);

const CustomBarChart = ({ title, data, color, icon: Icon }) => (
  <div className="dashboard-chart-card">
    <div className="chart-header">
      <Icon size={16} />
      <span>{title}</span>
    </div>
    <div className="chart-container-inner">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 20, right: 5, left: -30, bottom: 20 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f0f0f0" />
          <XAxis 
            dataKey="label" 
            fontSize={9} 
            tick={{ fill: '#7f8c8d' }} 
            axisLine={{ stroke: '#e9ecef' }} 
            tickLine={false}
            interval={0}
            angle={-30}
            textAnchor="end"
            height={40}
          />
          <YAxis fontSize={10} tick={{ fill: '#7f8c8d' }} axisLine={false} tickLine={false} />
          <RechartsTooltip cursor={{ fill: '#fff5f5' }} contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }} />
          <Bar dataKey="value" fill={color} radius={[4, 4, 0, 0]} barSize={10}>
            <LabelList dataKey="value" position="top" fontSize={8} fill="#7f8c8d" offset={5} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  </div>
);

const IndiaMap = ({ data }) => {
  const [hoveredState, setHoveredState] = useState(null);
  const maxValue = Math.max(...data.map(d => d.value), 1);
  const colorScale = scaleLinear().domain([0, maxValue]).range(["#f0fdf4", "#166534"]); 

      return (
        <div className="india-map-wrapper">
          <ComposableMap
            projection="geoMercator"
            projectionConfig={{ scale: 700, center: [80, 22] }}
            width={400}
            height={400}
            style={{ width: "100%", height: "100%", maxWidth: "100%", maxHeight: "100%" }}
          >        <Geographies geography={INDIA_TOPO_JSON}>
          {({ geographies }) =>
            geographies.map((geo) => {
              const stateName = geo.properties.st_nm || geo.properties.ST_NM;
              const match = data.find(d => d.label.toLowerCase() === stateName?.toLowerCase());
              const count = match ? match.value : 0;
              return (
                <Geography
                  key={geo.rsmKey}
                  geography={geo}
                  onMouseEnter={(e) => setHoveredState({ name: stateName, count, x: e.clientX, y: e.clientY })}
                  onMouseMove={(e) => setHoveredState({ name: stateName, count, x: e.clientX, y: e.clientY })}
                  onMouseLeave={() => setHoveredState(null)}
                  style={{
                    default: { fill: colorScale(count), stroke: "#cbd5e1", strokeWidth: 0.5, outline: "none" },
                    hover: { fill: "#22c55e", stroke: "#166534", strokeWidth: 1, outline: "none", cursor: "pointer" },
                    pressed: { fill: "#15803d", outline: "none" }
                  }}
                />
              );
            })
          }
        </Geographies>
      </ComposableMap>
      {hoveredState && (
        <div className="map-tooltip" style={{ left: hoveredState.x - 100, top: hoveredState.y - 100 }}>
          <div className="tooltip-state">{hoveredState.name}</div>
          <div className="tooltip-count"><strong>{hoveredState.count}</strong> Failures</div>
        </div>
      )}
    </div>
  );
};

function PartLabeler() {
  const navigate = useNavigate();
  const [userId] = useState(() => {
    const id = sessionStorage.getItem('user_id');
    return id ? parseInt(id, 10) : null;
  });

  const [dataSource, setDataSource] = useState('warranty');
  const [selectedImage, setSelectedImage] = useState(null);
  const [images, setImages] = useState([]);
  const [labels, setLabels] = useState([]);
  const [labelFailures, setLabelFailures] = useState({});
  const [showInput, setShowInput] = useState(null);
  const [activePopup, setActivePopup] = useState(null);
  const [warrantyHistory, setWarrantyHistory] = useState([]);
  const [dashboardData, setDashboardData] = useState({ mfgMonth: [], reportingMonth: [], kms: [], region: [] });
  const [filterMonth, setFilterMonth] = useState(['All']);
  const [filterModel, setFilterModel] = useState(['All']);
  const [filterMIS, setFilterMIS] = useState(['All']);
  const [filterMfgQtr, setFilterMfgQtr] = useState(['All']);
  const [filterOptions, setFilterOptions] = useState({ models: [], mis_buckets: [], mfg_quarters: [], mfg_months: [] });
  const [openFilter, setOpenFilter] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSummaryActive, setIsSummaryActive] = useState(false);
  const [nodePositions, setNodePositions] = useState([]);
  const [partName, setPartName] = useState('');
  const [isEditingLabel, setIsEditingLabel] = useState(false);
  const [editLabelName, setEditLabelName] = useState('');

  useEffect(() => {
    const handleOutsideClick = (e) => {
      if (!e.target.closest('.month-filter-compact')) {
        setOpenFilter(null);
      }
    };
    window.addEventListener('mousedown', handleOutsideClick);
    return () => window.removeEventListener('mousedown', handleOutsideClick);
  }, []);

  const fetchDashboardData = async (partNameArg = null, srcOverride = null) => {
    if (!userId) return;
    const src = srcOverride || dataSource;
    try {
      const params = new URLSearchParams();
      params.append('userId', userId);
      params.append('dataSource', src);

      if (partNameArg) {
        params.append('partName', partNameArg);
      } else if (labels && labels.length > 0) {
        labels.forEach(l => params.append('partName', l.partName));
      }

      filterMonth.forEach(m => params.append('month', m));
      filterModel.forEach(m => params.append('baseModel', m));
      filterMIS.forEach(m => params.append('misBucket', m));
      filterMfgQtr.forEach(m => params.append('mfgQtr', m));

      const res = await fetch(`${API_BASE}/dashboard-data?${params.toString()}`);
      const data = await res.json();
      setDashboardData(data);
    } catch (err) {
      console.error("Failed to fetch dashboard data", err);
    }
  };

  const fetchActivePartHistory = async (label) => {
    if (!userId || !label) return;
    try {
      const params = new URLSearchParams();
      params.append('userId', userId);
      params.append('partName', label.partName);
      params.append('dataSource', dataSource);
      filterMonth.forEach(m => params.append('month', m));
      filterModel.forEach(m => params.append('baseModel', m));
      filterMIS.forEach(m => params.append('misBucket', m));
      filterMfgQtr.forEach(m => params.append('mfgQtr', m));

      const res = await fetch(`${API_BASE}/warranty-lookup?${params.toString()}`);
      const data = await res.json();
      if (!data.error) setWarrantyHistory(Array.isArray(data) ? data : [data]);
    } catch (err) {
      console.error("No history found", err);
    }
  };

  const updateAllLabelFailures = async (currentLabels, month, model, mis, qtr, src) => {
    if (!userId) return;
    const src_ = src || dataSource;
    const counts = {};
    await Promise.all(currentLabels.map(async (label) => {
      try {
        const params = new URLSearchParams();
        params.append('userId', userId);
        params.append('partName', label.partName);
        params.append('dataSource', src_);
        month.forEach(m => params.append('month', m));
        model.forEach(m => params.append('baseModel', m));
        mis.forEach(m => params.append('misBucket', m));
        qtr.forEach(m => params.append('mfgQtr', m));

        const res = await fetch(`${API_BASE}/warranty-lookup?${params.toString()}`);
        const data = await res.json();
        const records = Array.isArray(data) ? data : [data];
        const count = records.reduce((sum, r) => sum + (r.failureCount || 0), 0);
        counts[label.id] = count;
      } catch (err) {
        counts[label.id] = 0;
      }
    }));
    setLabelFailures(counts);
  };

  useEffect(() => {
    if (!userId) {
      navigate('/');
      return;
    }
    fetchImages();
    fetchFilterOptions(dataSource);
    fetchDashboardData();
  }, [userId]);

  // Reload filters and dashboard when data source changes
  useEffect(() => {
    if (!userId) return;
    fetchFilterOptions(dataSource);
    fetchDashboardData(null, dataSource);
    if (labels.length > 0) updateAllLabelFailures(labels, filterMonth, filterModel, filterMIS, filterMfgQtr, dataSource);
  }, [dataSource]);

  useEffect(() => {
    if (labels.length > 0) {
      updateAllLabelFailures(labels, filterMonth, filterModel, filterMIS, filterMfgQtr);
    }
    if (activePopup) {
      fetchActivePartHistory(activePopup);
    }
    fetchDashboardData(activePopup?.partName);
  }, [filterMonth, filterModel, filterMIS, filterMfgQtr, activePopup, labels, isSummaryActive]);

  const imgRef = useRef(null);
  const cadInputRef = useRef(null);
  const warrantyInputRef = useRef(null);
  const [connectorPath, setConnectorPath] = useState("");
  const [expandedImageId, setExpandedImageId] = useState(null);

  const [excelHeaders, setExcelHeaders] = useState([]);
  const [tempFilePath, setTempFilePath] = useState('');
  const [columnMapping, setColumnMapping] = useState({});
  const [ingestResult, setIngestResult] = useState(null);

  // Derived from current data source config
  const targetColumns = DATA_SOURCES[dataSource]?.targetColumns || DATA_SOURCES.warranty.targetColumns;
  const mandatoryColumns = targetColumns.filter(c => c.mandatory);
  const sourceConfig = DATA_SOURCES[dataSource] || DATA_SOURCES.warranty;

  // When data source changes, reset filters and reload
  const handleDataSourceChange = (newSource) => {
    setDataSource(newSource);
    setFilterMonth(['All']);
    setFilterModel(['All']);
    setFilterMIS(['All']);
    setFilterMfgQtr(['All']);
    setFilterOptions({ models: [], mis_buckets: [], mfg_quarters: [], mfg_months: [] });
    setDashboardData({ mfgMonth: [], reportingMonth: [], kms: [], region: [] });
    setActivePopup(null);
    setWarrantyHistory([]);
  };

  const handleDataIngestionStart = () => {
    setColumnMapping({});
    setIngestResult(null);
    setModalType('ingest-start');
  };

  const handleDataIngestionFile = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    uploadDataForMapping(file);
  };

  const uploadDataForMapping = async (file) => {
    const formData = new FormData();
    formData.append('file', file);
    setIsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/warranty-upload`, { method: 'POST', body: formData });
      const data = await res.json();
      setExcelHeaders(data.headers);
      setTempFilePath(data.tempFilePath);
      const initialMap = {};
      data.headers.forEach(header => {
        const match = targetColumns.find(tc => tc.label.toLowerCase() === header.toLowerCase() || tc.key.toLowerCase() === header.toLowerCase());
        if (match) initialMap[match.key] = header;
      });
      setColumnMapping(initialMap);
      setModalType('ingest-mapping');
    } catch (err) {
      alert("Failed to upload data file");
    } finally {
      setIsLoading(false);
    }
  };

  const confirmMappingAndProcess = async (userId) => {
    const missing = mandatoryColumns.find(col => !columnMapping[col.key]);
    if (missing) {
      alert(`Please map your column for: ${missing.label}`);
      return;
    }
    setIsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/warranty-confirm-mapping`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tempFilePath, mapping: columnMapping, userId, dataSource })
      });
      const data = await res.json();
      if (data.success) {
        setIngestResult(data.count);
        setModalType('ingest-success');
        fetchFilterOptions(dataSource);
        if (selectedImage) fetchLabels(selectedImage.id);
      }
    } catch (err) {
      alert("Failed to process mapping");
    } finally {
      setIsLoading(false);
    }
  };

  const [modalType, setModalType] = useState(null);
  const [modalData, setModalTypeData] = useState(null);
  const [pendingFile, setPendingFile] = useState(null);
  const [customImageName, setCustomImageName] = useState('');

  const fetchImages = async () => {
    if (!userId) return;
    try {
      const res = await fetch(`${API_BASE}/images?userId=${userId}`);
      const data = await res.json();
      setImages(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error("Failed to fetch images", err);
      setImages([]);
    }
  };

  useEffect(() => {
    if (selectedImage) {
      fetchLabels(selectedImage.id);
    }
  }, [selectedImage]);

  const fetchLabels = async (imageId) => {
    if (!imageId || imageId === 'undefined' || !userId) return;
    try {
      const res = await fetch(`${API_BASE}/labels/${imageId}?userId=${userId}`);
      const data = await res.json();
      const labelsArray = Array.isArray(data) ? data : [];
      setLabels(labelsArray);
      updateAllLabelFailures(labelsArray, filterMonth, filterModel, filterMIS, filterMfgQtr);
    } catch (err) {
      console.error("Failed to fetch labels", err);
      setLabels([]);
    }
  };

  const fetchFilterOptions = async (src) => {
    if (!userId) return;
    const source = src || dataSource;
    try {
      const res = await fetch(`${API_BASE}/filter-options?userId=${userId}&dataSource=${source}`);
      const data = await res.json();
      setFilterOptions(data);
    } catch (err) {
      console.error("Failed to fetch filter options", err);
    }
  };

  useEffect(() => {
    let interval;
    if (activePopup && imgRef.current) {
      const updatePath = () => {
        const container = document.querySelector('.cad-img-container');
        if (!container) return;
        const imgRect = container.getBoundingClientRect();
        const workspace = document.querySelector('.cad-viewer');
        if (!workspace) return;
        const workRect = workspace.getBoundingClientRect();
        const mx = imgRect.left - workRect.left + (activePopup.x * imgRect.width / 100)+ 20;
        const my = imgRect.top - workRect.top + (activePopup.y * imgRect.height / 100) - 22.6;
        const detailPanel = document.querySelector('.marker-detail-floating');
        let tx = workRect.width - 360; 
        let ty = 160;
        if (detailPanel) {
          const detailRect = detailPanel.getBoundingClientRect();
          tx = detailRect.left - workRect.left;
          ty = detailRect.top - workRect.top + 100;
        }
        setConnectorPath(`M ${mx} ${my} L ${mx + (tx - mx) * 0.5} ${my} L ${tx} ${ty}`);
      };
      updatePath();
      interval = setInterval(updatePath, 16); 
      window.addEventListener('resize', updatePath);
      const timeout = setTimeout(() => clearInterval(interval), 600);
      return () => {
        clearInterval(interval);
        clearTimeout(timeout);
        window.removeEventListener('resize', updatePath);
      };
    }
  }, [activePopup, filterMonth, filterModel, filterMIS]);

  const handleImageUploadRequest = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setPendingFile(file);
    setCustomImageName(file.name.split('.')[0]);
    setModalType('name');
  };

  const confirmImageUpload = async () => {
    if (!pendingFile || !userId) return;
    const formData = new FormData();
    formData.append('image', pendingFile);
    setIsLoading(true);
    setModalType(null);
    try {
      const res = await fetch(`${API_BASE}/upload?userId=${userId}&displayName=${encodeURIComponent(customImageName || pendingFile.name)}`, { method: 'POST', body: formData });
      const data = await res.json();
      setSelectedImage(data);
      setLabels([]);
      fetchImages();
    } catch (err) {
      console.error("Upload failed", err);
    } finally {
      setIsLoading(false);
      setPendingFile(null);
    }
  };

  const requestDeleteImage = (e, imageId) => {
    e.stopPropagation();
    setModalTypeData(imageId);
    setModalType('delete-image');
  };

  const confirmDeleteImage = async () => {
    if (!userId) return;
    const imageId = modalData;
    try {
      await fetch(`${API_BASE}/images/${imageId}?userId=${userId}`, { method: 'DELETE' });
      setImages(images.filter(img => img.id !== imageId));
      if (selectedImage?.id === imageId) {
        setSelectedImage(null);
        setLabels([]);
        setActivePopup(null);
      }
    } catch (err) {
      console.error("Delete failed", err);
    } finally {
      setModalType(null);
    }
  };

  const requestDeleteLabel = (id) => {
    setModalTypeData(id);
    setModalType('delete-part');
  };

  const confirmDeleteLabel = async () => {
    if (!userId) return;
    const id = modalData;
    try {
      await fetch(`${API_BASE}/labels/${id}?userId=${userId}`, { method: 'DELETE' });
      setLabels(labels.filter(l => l.id !== id));
      if (activePopup?.id === id) setActivePopup(null);
    } catch (err) {
      console.error("Delete part failed", err);
    } finally {
      setModalType(null);
    }
  };

  const handleImageClick = (e) => {
    if (!selectedImage) return;
    if (activePopup) {
      setActivePopup(null);
      return;
    }
    const rect = imgRef.current.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * 100;
    const y = ((e.clientY - rect.top) / rect.height) * 100;
    setShowInput({ x, y });
  };

  const handleMarkerClick = async (label) => {
    if (!userId) return;
    setActivePopup(label);
    setIsEditingLabel(false);
    setEditLabelName(label.partName);
    setWarrantyHistory([]); 
    setShowInput(null); 
    fetchActivePartHistory(label);
    fetchDashboardData(label.partName);
  };

  const handleUpdateLabel = async () => {
    if (!editLabelName.trim() || !userId) return;
    try {
      await fetch(`${API_BASE}/labels/${activePopup.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ partName: editLabelName, userId })
      });
      fetchLabels(selectedImage.id);
      setActivePopup({ ...activePopup, partName: editLabelName });
      setIsEditingLabel(false);
    } catch (err) {
      alert("Failed to update marker");
    }
  };

  const calculateNonOverlappingPositions = (currentLabels) => {
    let nodes = currentLabels.map((l, i) => {
      const isLeft = l.x < 50;
      const isTop = l.y < 50;
      return {
        ...l,
        vx: 0, vy: 0,
        x: l.x + (isLeft ? -20 : 20) + ((i % 2) * 5),
        y: l.y + (isTop ? -15 : 15) + ((i % 3) * 5),
        originalIndex: i
      };
    });
    const ITERATIONS = 120;
    const REPULSION_RADIUS = 15; 
    const SCREEN_PADDING = 8;
    for (let iter = 0; iter < ITERATIONS; iter++) {
      for (let i = 0; i < nodes.length; i++) {
        let node = nodes[i];
        const dx = currentLabels[i].x - node.x;
        const dy = currentLabels[i].y - node.y;
        node.vx += dx * 0.03;
        node.vy += dy * 0.03;
        for (let j = 0; j < nodes.length; j++) {
          if (i === j) continue;
          let other = nodes[j];
          let diffX = node.x - other.x;
          let diffY = node.y - other.y;
          let dist = Math.sqrt(diffX*diffX + diffY*diffY);
          if (dist < REPULSION_RADIUS) {
            let force = (REPULSION_RADIUS - dist) * 0.5;
            let angle = Math.atan2(diffY, diffX);
            node.vx += Math.cos(angle) * force;
            node.vy += Math.sin(angle) * force;
          }
        }
        let mDist = Math.sqrt(dx*dx + dy*dy);
        if (mDist < 12) {
           let angle = Math.atan2(-dy, -dx);
           node.vx += Math.cos(angle) * 1.5;
           node.vy += Math.sin(angle) * 1.5;
        }
      }
      for (let node of nodes) {
        node.x += node.vx;
        node.y += node.vy;
        node.vx *= 0.6; 
        node.vy *= 0.6;
        node.x = Math.max(SCREEN_PADDING, Math.min(100 - SCREEN_PADDING, node.x));
        node.y = Math.max(SCREEN_PADDING, Math.min(100 - SCREEN_PADDING, node.y));
      }
    }
    return nodes.map(n => ({ x: n.x, y: n.y }));
  };

  const handleShowAll = async () => {
    if (!selectedImage || !userId) return;
    if (isSummaryActive) {
      setIsSummaryActive(false);
      return;
    }
    setIsLoading(true);
    const calculatedPositions = calculateNonOverlappingPositions(labels);
    setNodePositions(calculatedPositions);
    setIsSummaryActive(true); 
    setIsLoading(false);
    fetchDashboardData(null);
  };

  const saveLabel = async () => {
    if (!partName.trim() || !userId) return;
    const newLabel = { imageId: selectedImage.id, partName, x: showInput.x, y: showInput.y, userId };
    try {
      await fetch(`${API_BASE}/labels`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newLabel),
      });
      fetchLabels(selectedImage.id);
      resetForm();
    } catch (err) {
      alert("Failed to save label");
    }
  };

  const resetForm = () => {
    setPartName('');
    setShowInput(null);
  };

  const currentMonthFailures = filterMonth.includes('All') 
    ? warrantyHistory.reduce((sum, item) => sum + item.failureCount, 0)
    : warrantyHistory.filter(h => filterMonth.includes(h.month)).reduce((sum, item) => sum + item.failureCount, 0);

  const currentDescription = (() => {
    if (!filterMonth.includes('All')) {
      const match = warrantyHistory.find(h => filterMonth.includes(h.month));
      if (match) return match.description;
    }
    if (!warrantyHistory || warrantyHistory.length === 0) return 'Aggregated warranty claims data.';
    const descWeights = {};
    const relevantHistory = filterMonth.includes('All') ? warrantyHistory : warrantyHistory.filter(h => filterMonth.includes(h.month));
    relevantHistory.forEach(h => {
      const d = h.description;
      if (d && d !== '-' && d !== 'null') descWeights[d] = (descWeights[d] || 0) + h.failureCount;
    });
    let topDesc = 'Aggregated warranty claims data.';
    let maxWeight = -1;
    Object.entries(descWeights).forEach(([desc, weight]) => {
      if (weight > maxWeight) {
        maxWeight = weight;
        topDesc = desc;
      }
    });
    return topDesc;
  })();

  return (
    <div className="part-labeler">
      <AnimatePresence>
        {modalType && (
          <div className="custom-modal-overlay">
            <motion.div initial={{ opacity: 0, scale: 0.9, y: 20 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: 0.9, y: 20 }} className="custom-modal-card">
              <div className="modal-header">
                <h3>
                  {modalType === 'name' && 'New CAD Drawing'}
                  {modalType === 'delete-image' && 'Delete Drawing?'}
                  {modalType === 'delete-part' && 'Delete Part?'}
                  {modalType === 'ingest-start' && `Ingest ${sourceConfig.label}`}
                  {modalType === 'ingest-mapping' && 'Map Columns'}
                  {modalType === 'ingest-success' && 'Success'}
                </h3>
                <button onClick={() => setModalType(null)}><X size={18} /></button>
              </div>
              <div className="modal-body">
                {modalType === 'name' && (
                  <div className="modal-input-group">
                    <label>Enter a display name for this CAD:</label>
                    <input type="text" value={customImageName} onChange={(e) => setCustomImageName(e.target.value)} placeholder="e.g. THAR ROXX - Interior" autoFocus />
                  </div>
                )}
                {modalType === 'delete-image' && <p>Are you sure you want to delete this drawing? This action will remove all mapped parts permanently.</p>}
                {modalType === 'delete-part' && <p>Are you sure you want to remove this component marker?</p>}
                {modalType === 'ingest-start' && (
                  <div className="ingest-start-modal">
                    <div className="upload-zone-compact" onClick={() => warrantyInputRef.current.click()}>
                      <Upload size={32} />
                      <p>Select your Excel or CSV warranty file to begin mapping.</p>
                      <input type="file" ref={warrantyInputRef} style={{ display: 'none' }} onChange={handleDataIngestionFile} accept=".csv, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, application/vnd.ms-excel" />
                    </div>
                  </div>
                )}
                {modalType === 'ingest-mapping' && (
                  <div className="ingest-mapping-container">
                    <div className="ingest-notice">
                      <FileSpreadsheet size={20} />
                      <p>Mapping for <strong>{sourceConfig.label}</strong>. <strong>{mandatoryColumns.length} Required fields (*) must be set.</strong></p>
                    </div>
                    <div className="mapping-scroll-table">
                      <table className="mapping-table">
                        <thead><tr><th>Internal Field</th><th>Excel Column</th></tr></thead>
                        <tbody>
                          {[...new Set(targetColumns.map(c => c.group))].map(group => (
                            <React.Fragment key={group}>
                              <tr className="group-header-row"><td colSpan="2">{group} Fields</td></tr>
                              {targetColumns.filter(tc => tc.group === group).map(col => (
                                <tr key={col.key}>
                                  <td className={col.mandatory ? 'mandatory-cell' : ''}>
                                    {col.label} {col.mandatory && <span className="req">*</span>}
                                    {col.hint && <span className="col-hint"> ({col.hint})</span>}
                                  </td>
                                  <td>
                                    <select value={columnMapping[col.key] || ''} onChange={(e) => setColumnMapping({ ...columnMapping, [col.key]: e.target.value })}>
                                      <option value="">-- Discard / Skip --</option>
                                      {excelHeaders.map(h => <option key={h} value={h}>{h}</option>)}
                                    </select>
                                  </td>
                                </tr>
                              ))}
                            </React.Fragment>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
                {modalType === 'ingest-success' && (
                  <div className="ingest-success-view">
                    <div className="success-icon-circle-large"><Check size={48} /></div>
                    <h3>Data Load Successful</h3>
                    <p>Successfully processed and loaded <strong>{ingestResult}</strong> {sourceConfig.label} records.</p>
                  </div>
                )}
              </div>
              <div className="modal-footer">
                {modalType === 'ingest-success' ? (
                  <button className="modal-btn-confirm success-btn" onClick={() => setModalType(null)}>Close</button>
                ) : (
                  <>
                    <button className="modal-btn-cancel" onClick={() => setModalType(null)}>Cancel</button>
                    {modalType !== 'ingest-start' && (
                      <button className={`modal-btn-confirm ${modalType.includes('delete') ? 'danger' : ''} ${modalType === 'ingest-mapping' ? 'success-btn' : ''}`}
                        onClick={() => {
                          if (modalType === 'name') confirmImageUpload();
                          if (modalType === 'delete-image') confirmDeleteImage();
                          if (modalType === 'delete-part') confirmDeleteLabel(modalData);
                          if (modalType === 'ingest-mapping') confirmMappingAndProcess(userId);
                        }}
                        disabled={isLoading}
                      >
                        {modalType === 'name' && 'Upload Drawing'}
                        {modalType.includes('delete') && 'Confirm Delete'}
                        {modalType === 'ingest-mapping' && (isLoading ? 'Processing...' : 'Verify & Load Data')}
                      </button>
                    )}
                  </>
                )}
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      <div className="part-labeler-header">
        <div className="header-title">
          <h1>Part Sense Visualizer</h1>
          <p>Interactive failure trend analysis</p>
        </div>
        <div className="header-stats">
          <div className="stat-card">
            <span className="stat-value">{labels.length}</span>
            <span className="stat-label">Mapped Components</span>
          </div>
        </div>
      </div>

      <div className="part-labeler-content">
        <aside className="part-labeler-sidebar">
          <button className="sidebar-back-btn" onClick={() => navigate('/')}><ArrowLeft size={16} /><span>Dashboard</span></button>
          <div className="sidebar-section">
            <h3 className="section-title">Operations</h3>
            <button className="sidebar-btn primary" onClick={() => cadInputRef.current.click()}>
              <Upload size={18} /><span>Upload New CAD</span>
              <input type="file" ref={cadInputRef} style={{ display: 'none' }} onChange={handleImageUploadRequest} accept="image/*" />
            </button>
            <button className="sidebar-btn secondary" onClick={handleDataIngestionStart}><Database size={18} /><span>Ingest {sourceConfig.label}</span></button>
            <button className={`sidebar-btn secondary ${isSummaryActive ? 'active' : ''}`} onClick={handleShowAll} disabled={isLoading || !selectedImage}>
              <BarChart2 size={18} /><span>{isSummaryActive ? 'Hide Visuals' : 'Show Visuals'}</span>
            </button>
          </div>
          <div className="sidebar-section">
            <h3 className="section-title">CAD Drawings</h3>
            <div className="image-list">
              {Array.isArray(images) && images.map(img => (
                <div key={img.id} className="image-group-container">
                  <div className={`image-item ${selectedImage?.id === img.id ? 'active' : ''}`}
                    onClick={() => { setSelectedImage(img); setShowInput(null); setActivePopup(null); setExpandedImageId(expandedImageId === img.id ? null : img.id); }}>
                    <MapPin size={14} /><span className="image-display-name">{img.display_name}</span>
                    <div className="image-item-actions">
                      <button onClick={(e) => requestDeleteImage(e, img.id)} className="delete-image-btn"><Trash2 size={12} /></button>
                      {expandedImageId === img.id ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                    </div>
                  </div>
                  <AnimatePresence>
                    {expandedImageId === img.id && selectedImage?.id === img.id && (
                      <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="sidebar-parts-dropdown">
                        {labels.length > 0 ? labels.map((label, idx) => (
                          <div key={label.id} className="sidebar-part-entry">
                            <span className="entry-index">{idx + 1}</span>
                            <span className="entry-name" onClick={(e) => { e.stopPropagation(); handleMarkerClick(label); }}>{label.partName}</span>
                            <div className="entry-actions">
                              <button onClick={(e) => { e.stopPropagation(); handleMarkerClick(label); }} title="Edit"><Edit2 size={12} /></button>
                              <button onClick={(e) => { e.stopPropagation(); requestDeleteLabel(label.id); }} title="Delete"><Trash2 size={12} /></button>
                            </div>
                          </div>
                        )) : <div className="empty-parts-msg">No parts mapped yet</div>}
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              ))}
              {(!images || images.length === 0) && <p className="empty-msg">No drawings uploaded</p>}
            </div>
          </div>
        </aside>

        <main className="part-labeler-workspace">
          <div className="workspace-header-bar">
            <DataSourceSelector current={dataSource} onChange={handleDataSourceChange} />
            {['month', 'qtr', 'model', 'mis'].map(type => {
              const label = type === 'month' ? 'Mfg Month' : type === 'qtr' ? 'Mfg Qtr' : type === 'model' ? 'Model' : 'MIS';
              const options = type === 'month' ? filterOptions.mfg_months : 
                              type === 'qtr' ? filterOptions.mfg_quarters :
                              type === 'model' ? filterOptions.models :
                              filterOptions.mis_buckets;
              const currentArr = type === 'month' ? filterMonth : type === 'qtr' ? filterMfgQtr : type === 'model' ? filterModel : filterMIS;
              const setter = type === 'month' ? setFilterMonth : type === 'qtr' ? setFilterMfgQtr : type === 'model' ? setFilterModel : setFilterMIS;

              const displayValue = currentArr.includes('All') 
                ? (type === 'month' ? 'All Months' : type === 'qtr' ? 'All Quarters' : 'All')
                : (currentArr.length === 1 ? currentArr[0] : `${currentArr.length} selected`);

              const handleToggle = (opt) => {
                if (opt === 'All') {
                  setter(['All']);
                  return;
                }
                let newArr = currentArr.filter(v => v !== 'All');
                if (newArr.includes(opt)) {
                  newArr = newArr.filter(v => v !== opt);
                  if (newArr.length === 0) newArr = ['All'];
                } else {
                  newArr.push(opt);
                }
                setter(newArr);
              };

              return (
                <div key={type} className={`month-filter-compact ${openFilter === type ? 'open' : ''}`} onClick={() => setOpenFilter(openFilter === type ? null : type)}>
                  <Layout size={16} /><span>{label}:</span><div className="selected-value">{displayValue}</div>
                  <ChevronDown size={14} className={`chevron ${openFilter === type ? 'rotate' : ''}`} />
                  {openFilter === type && (
                    <div className="filter-dropdown-list" onClick={(e) => e.stopPropagation()}>
                      <div className={`filter-option ${currentArr.includes('All') ? 'selected' : ''}`} 
                           onClick={() => handleToggle('All')}>
                        {type === 'month' ? 'All Months' : type === 'qtr' ? 'All Quarters' : 'All'}
                      </div>
                      {options.map(opt => (
                        <div key={opt} className={`filter-option ${currentArr.includes(opt) ? 'selected' : ''}`} 
                             onClick={() => handleToggle(opt)}>
                          {opt}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          <div className={`workspace-scroll-container ${!selectedImage ? 'empty-state' : ''}`}>
            <div className="top-visual-section">
              {!selectedImage ? (
                <div className="upload-prompt">
                  <div className="upload-icon-circle"><Upload size={48} /></div>
                  <h2>Start Component Mapping</h2>
                  <p>Upload a CAD drawing or select an existing one to begin.</p>
                  <button className="main-upload-btn" onClick={() => cadInputRef.current.click()}>Select Drawing</button>
                </div>
              ) : (
                <div className="layout-grid-top">
                  <div className="cad-viewer-container">
                    <div className="cad-viewer centering">
                      <div className="image-wrapper">
                        <div className="cad-img-container" ref={imgRef} onClick={handleImageClick}>
                          <img src={`${UPLOAD_BASE}/${selectedImage.filename}`} alt="CAD Drawing" className="cad-img" />
                          {labels.map((label, index) => (
                            <React.Fragment key={label.id}>
                              <div className={`label-marker ${activePopup?.id === label.id ? 'active' : ''}`}
                                onClick={(e) => { e.stopPropagation(); handleMarkerClick(label); }}
                                style={{ left: `${label.x}%`, top: `${label.y}%` }}>{index + 1}</div>
                              {isSummaryActive && nodePositions[index] && (
                                <DraggableNode label={label} initialPos={nodePositions[index]} count={labelFailures[label.id] || 0} />
                              )}
                            </React.Fragment>
                          ))}
                          <AnimatePresence>
                            {showInput && (
                              <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.9 }} className="marker-input-popup"
                                style={{ left: `${showInput.x}%`, top: `${showInput.y}%` }} onClick={(e) => e.stopPropagation()}>
                                <div className="popup-header"><h4>New Component</h4><button onClick={resetForm}><X size={14} /></button></div>
                                <div className="popup-body">
                                  <input type="text" placeholder="Part Name" autoFocus value={partName} onChange={(e) => setPartName(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && saveLabel()} />
                                  <button className="save-btn" onClick={saveLabel}>Save Position</button>
                                </div>
                              </motion.div>
                            )}
                          </AnimatePresence>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div className="side-data-panel">
                    <div className="mapped-parts-integrated">
                      <div className="panel-header"><Layers size={16} /><span>Mapped Components</span></div>
                      <div className="panel-table-scroll">
                        <table className="integrated-table">
                          <thead><tr><th>#</th><th>Component Name</th><th style={{ textAlign: 'right' }}>Failures</th></tr></thead>
                          <tbody>
                            {labels.map((label, idx) => (
                              <tr key={label.id} className={activePopup?.id === label.id ? 'active-row' : ''} onClick={() => handleMarkerClick(label)}>
                                <td>{idx + 1}</td><td className="part-name-cell">{label.partName}</td><td style={{ textAlign: 'right', fontWeight: 700 }}>{labelFailures[label.id] || 0}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                                        <AnimatePresence>
                                          {activePopup && (
                                            <motion.div 
                                              initial={{ opacity: 0, y: 10 }}
                                              animate={{ opacity: 1, y: 0 }}
                                              className="active-part-details"
                                            >
                                              <div className="details-header">
                                                {isEditingLabel ? (
                                                  <div className="edit-mode-compact">
                                                    <input 
                                                      type="text" 
                                                      value={editLabelName} 
                                                      onChange={(e) => setEditLabelName(e.target.value)}
                                                      autoFocus
                                                      onKeyDown={(e) => e.key === 'Enter' && handleUpdateLabel()}
                                                    />
                                                    <div className="edit-actions">
                                                      <button onClick={handleUpdateLabel} className="success"><Check size={14} /></button>
                                                      <button onClick={() => setIsEditingLabel(false)} className="cancel"><X size={14} /></button>
                                                    </div>
                                                  </div>
                                                ) : (
                                                  <>
                                                    <div className="title-row">
                                                      <h3 className="mahindra-red-text">{activePopup.partName}</h3>
                                                      <div className="actions">
                                                        <button onClick={() => setIsEditingLabel(true)} title="Edit name"><Edit2 size={14} /></button>
                                                        <button onClick={() => requestDeleteLabel(activePopup.id)} title="Delete"><Trash2 size={14} /></button>
                                                        <button onClick={() => setActivePopup(null)} title="Close"><X size={14} /></button>
                                                      </div>
                                                    </div>
                                                    <div className="primary-concern-row">
                                                      <strong>Primary Concern:</strong>
                                                      <p>{currentDescription}</p>
                                                    </div>
                                                  </>
                                                )}
                                              </div>
                          <div className="details-summary-stats">
                            <div className="mini-stat">
                              <span className="label">
                                {filterMonth.includes('All') ? 'ANNUAL' : (filterMonth.length === 1 ? filterMonth[0] : 'Multiple')}
                              </span>
                              <span className="value">{currentMonthFailures}</span><span className="sub">Failures</span>
                            </div>
                            <button className="download-csv-btn-integrated" onClick={() => {
                              const params = new URLSearchParams();
                              params.append('userId', userId);
                              params.append('partName', activePopup.partName);
                              filterMonth.forEach(m => params.append('month', m));
                              filterModel.forEach(m => params.append('baseModel', m));
                              filterMIS.forEach(m => params.append('misBucket', m));
                              filterMfgQtr.forEach(m => params.append('mfgQtr', m));
                              window.open(`${API_BASE}/download-warranty?${params.toString()}`, '_blank');
                            }}><Download size={14} /><span>Download Data</span></button>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                </div>
              )}
            </div>

            {selectedImage && activePopup && (
              <div className="dashboard-analysis-section">
                <div className="dashboard-grid">
                  <CustomBarChart title={sourceConfig.chartTitles.mfgMonth} data={dashboardData.mfgMonth} color="#f6ad55" icon={History} />
                  <CustomBarChart title={sourceConfig.chartTitles.reportingMonth} data={dashboardData.reportingMonth} color="#68d391" icon={FileSpreadsheet} />
                  <CustomBarChart title={sourceConfig.chartTitles.kms} data={dashboardData.kms} color="#76e4f7" icon={Activity} />
                  {sourceConfig.useMapForRegion ? (
                    <div className="dashboard-chart-card">
                      <div className="chart-header"><MapIcon size={16} /><span>{sourceConfig.chartTitles.region}</span></div>
                      <div className="chart-container-inner india-map-container"><IndiaMap data={dashboardData.region} /></div>
                    </div>
                  ) : (
                    <LocationBarChart title={sourceConfig.chartTitles.region} data={dashboardData.region} />
                  )}
                </div>
              </div>
            )}
            {selectedImage && !activePopup && (
              <div className="dashboard-analysis-section dashboard-placeholder">
                <div className="dashboard-placeholder-hint">
                  <BarChart2 size={32} />
                  <p>Click a component marker on the image to view its analytics</p>
                </div>
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}

function DraggableNode({ label, initialPos, count }) {
  const [pos, setPos] = useState(initialPos);
  useEffect(() => { setPos(initialPos); }, [initialPos]);

  return (
    <>
      <svg className="connecting-line" viewBox="0 0 100 100" preserveAspectRatio="none">
        <path d={`M ${label.x} ${label.y} L ${pos.x} ${pos.y}`} stroke="#e53e3e" strokeWidth="0.5" fill="none" />
      </svg>
      <motion.div drag dragMomentum={false} onDrag={(e, info) => {
          const container = document.querySelector('.cad-img-container');
          if (container) {
            const rect = container.getBoundingClientRect();
            const newX = ((info.point.x - rect.left) / rect.width) * 100;
            const newY = ((info.point.y - rect.top) / rect.height) * 100;
            setPos({ x: newX, y: newY });
          }
        }} className="summary-node" style={{ left: `${pos.x}%`, top: `${pos.y}%` }}>
        <div className="node-title">{label.partName}</div>
        <div className="node-count">{count} Failures</div>
      </motion.div>
    </>
  );
}

export default PartLabeler;
