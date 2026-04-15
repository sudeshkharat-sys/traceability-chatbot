import React from 'react';
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

/**
 * ChartComponent - Renders different types of charts based on chart data
 *
 * @param {Object} chartData - Chart configuration and data
 * @param {string} chartData.type - Chart type: 'bar', 'line', or 'pie'
 * @param {string} chartData.title - Chart title
 * @param {Array} chartData.data - Chart data points
 * @param {Object} chartData.config - Chart configuration (axes, colors, etc.)
 */
const ChartComponent = ({ chartData }) => {
  if (!chartData || !chartData.data || chartData.data.length === 0) {
    return null;
  }

  const { type, title, data, config = {} } = chartData;

  // Default colors for charts
  const DEFAULT_COLORS = [
    '#3b82f6', // blue
    '#ef4444', // red
    '#22c55e', // green
    '#f59e0b', // amber
    '#8b5cf6', // purple
    '#ec4899', // pink
    '#14b8a6', // teal
    '#f97316', // orange
  ];

  const colors = config.colors || DEFAULT_COLORS;

  // Format month numbers to short month names
  const formatMonth = (value) => {
    // Handle both "1" and "01" formats
    const monthMap = {
      '1': 'Jan', '01': 'Jan',
      '2': 'Feb', '02': 'Feb',
      '3': 'Mar', '03': 'Mar',
      '4': 'Apr', '04': 'Apr',
      '5': 'May', '05': 'May',
      '6': 'Jun', '06': 'Jun',
      '7': 'Jul', '07': 'Jul',
      '8': 'Aug', '08': 'Aug',
      '9': 'Sep', '09': 'Sep',
      '10': 'Oct', '11': 'Nov', '12': 'Dec'
    };
    // Also handle numeric values
    const strValue = String(value);
    return monthMap[strValue] || value;
  };

  // Custom tooltip formatter for better readability
  const CustomTooltip = ({ active, payload, label }) => {
    if (!active || !payload) return null;

    return (
      <div style={{
        backgroundColor: '#1f2937',
        border: '1px solid #374151',
        borderRadius: '6px',
        padding: '10px',
        color: '#ffffff'
      }}>
        <p style={{fontWeight: 'bold', color: '#ffffff' }}>
          {formatMonth(label)}
        </p>
        {payload.map((entry, index) => (
          <p key={index} style={{ color: '#ffffff' }}>
            <span style={{ color: entry.color }}>●</span> {entry.name}: {entry.value}
          </p>
        ))}
      </div>
    );
  };

  // Helper: returns true if a value is numeric or a string that parses as a finite number
  const isNumericValue = (v) => {
    if (typeof v === 'number') return true;
    if (typeof v === 'string' && v.trim() !== '') {
      const n = parseFloat(v.replace(/[^0-9.-]/g, ''));
      return !isNaN(n) && isFinite(n);
    }
    return false;
  };

  // Render Bar Chart
  const renderBarChart = () => {
    // Detect xAxis key — fall back to first string column if specified key isn't in data
    const specifiedX = config.xAxis || 'name';
    const xAxis = (specifiedX in data[0])
      ? specifiedX
      : Object.keys(data[0]).find(k => typeof data[0][k] === 'string') || Object.keys(data[0])[0];

    // Detect yAxis keys — fall back to all numeric columns if none specified or none match.
    // Also handles PostgreSQL Decimal values serialised as strings (e.g. "123.45").
    const specifiedY = Array.isArray(config.yAxis) && config.yAxis.length > 0
      ? config.yAxis.filter(k => k in data[0])
      : [];
    const yAxes = specifiedY.length > 0
      ? specifiedY
      : Object.keys(data[0]).filter(k => k !== xAxis && isNumericValue(data[0][k]));

    // Coerce y values to numbers in case SQL returned string numerics
    const coercedData = data.map(row => {
      const r = { ...row };
      yAxes.forEach(k => { r[k] = parseFloat(String(r[k]).replace(/[^0-9.-]/g, '')) || 0; });
      return r;
    });

    const xAxisLabel = config.xAxisLabel || xAxis;
    const yAxisLabel = config.yAxisLabel || (yAxes.length === 1 ? yAxes[0] : 'Value');

    if (yAxes.length === 0) return <div style={{color:'#9ca3af',padding:'16px',textAlign:'center'}}>No numeric columns to chart.</div>;

    return (
      <div style={{ width: '100%', height: 300 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={coercedData}
            margin={{ top: 5, right: 10, left: 10, bottom: 40 }}
            onClick={null}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis
              dataKey={xAxis}
              stroke="#9ca3af"
              tick={{ fill: '#9ca3af', fontSize: 10 }}
              angle={-35}
              textAnchor="end"
              interval={0}
              height={60}
            />
            <YAxis
              stroke="#9ca3af"
              tick={{ fill: '#9ca3af', fontSize: 10 }}
              width={45}
              tickFormatter={v => (v >= 1000 ? `${(v/1000).toFixed(1)}k` : v)}
            />
            <Tooltip content={<CustomTooltip />} />
            {yAxes.map((key, index) => (
              <Bar
                key={key}
                dataKey={key}
                name={key.replace(/_/g, ' ')}
                fill={colors[index % colors.length]}
                radius={[3, 3, 0, 0]}
                onClick={null}
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  };

  // Render Line Chart
  const renderLineChart = () => {
    // Same resilient key detection as bar chart
    const specifiedX = config.xAxis || 'name';
    const xAxis = (specifiedX in data[0])
      ? specifiedX
      : Object.keys(data[0]).find(k => typeof data[0][k] === 'string') || Object.keys(data[0])[0];
    const specifiedY = Array.isArray(config.yAxis) && config.yAxis.length > 0
      ? config.yAxis.filter(k => k in data[0])
      : [];
    const yAxes = specifiedY.length > 0
      ? specifiedY
      : Object.keys(data[0]).filter(k => k !== xAxis && isNumericValue(data[0][k]));
    const coercedData = data.map(row => {
      const r = { ...row };
      yAxes.forEach(k => { r[k] = parseFloat(String(r[k]).replace(/[^0-9.-]/g, '')) || 0; });
      return r;
    });
    const xAxisLabel = config.xAxisLabel || xAxis;
    const yAxisLabel = config.yAxisLabel || (yAxes.length === 1 ? yAxes[0] : 'Value');

    if (yAxes.length === 0) return <div style={{color:'#9ca3af',padding:'16px',textAlign:'center'}}>No numeric columns to chart.</div>;

    return (
      <div style={{ width: '100%', height: 300 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={coercedData}
            margin={{ top: 5, right: 10, left: 10, bottom: 40 }}
            onClick={null}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis
              dataKey={xAxis}
              stroke="#9ca3af"
              tick={{ fill: '#9ca3af', fontSize: 10 }}
              tickFormatter={formatMonth}
              angle={-35}
              textAnchor="end"
              interval={0}
              height={60}
            />
            <YAxis
              stroke="#9ca3af"
              tick={{ fill: '#9ca3af', fontSize: 10 }}
              width={45}
              tickFormatter={v => (v >= 1000 ? `${(v/1000).toFixed(1)}k` : v)}
            />
            <Tooltip content={<CustomTooltip />} />
            {yAxes.map((key, index) => (
              <Line
                key={key}
                type="monotone"
                dataKey={key}
                name={key.replace(/_/g, ' ')}
                stroke={colors[index % colors.length]}
                strokeWidth={2}
                dot={{ fill: colors[index % colors.length], r: 4 }}
                activeDot={{ r: 6 }}
                onClick={null}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    );
  };

  // Render Pie Chart
  const renderPieChart = () => {
    // Resilient key detection
    const specifiedName = config.nameKey || config.xAxis || 'name';
    const nameKey = (specifiedName in data[0])
      ? specifiedName
      : Object.keys(data[0]).find(k => typeof data[0][k] === 'string') || Object.keys(data[0])[0];

    const specifiedValue = config.valueKey || (config.yAxis && config.yAxis[0]) || 'value';
    const valueKey = (specifiedValue in data[0])
      ? specifiedValue
      : Object.keys(data[0]).find(k => k !== nameKey && typeof data[0][k] === 'number') || Object.keys(data[0])[1];

    // Ensure data has the correct format for pie chart
    const pieData = data.map(item => ({
      name: item[nameKey],
      value: parseFloat(String(item[valueKey] || '0').replace(/[^0-9.-]/g, '')) || 0
    }));

    // Custom label that stays visible (not just on hover)
    const renderCustomLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, percent, name }) => {
      const RADIAN = Math.PI / 180;
      const radius = outerRadius + 20;
      const x = cx + radius * Math.cos(-midAngle * RADIAN);
      const y = cy + radius * Math.sin(-midAngle * RADIAN);

      // Only show label if percentage is > 5% (to avoid cluttering small slices)
      if (percent < 0.05) return null;

      return (
        <text
          x={x}
          y={y}
          fill="#9ca3af"
          textAnchor={x > cx ? 'start' : 'end'}
          dominantBaseline="central"
          style={{ fontSize: '11px', fontWeight: '500' }}
        >
          {`${name}: ${(percent * 100).toFixed(1)}%`}
        </text>
      );
    };

    // Custom pie tooltip with white text
    const PieTooltip = ({ active, payload }) => {
      if (!active || !payload || !payload[0]) return null;

      const data = payload[0];
      const total = pieData.reduce((sum, d) => sum + d.value, 0);
      const percent = ((data.value / total) * 100).toFixed(1);

      return (
        <div style={{
          backgroundColor: '#1f2937',
          border: '1px solid #374151',
          borderRadius: '6px',
          padding: '10px',
          color: '#ffffff'
        }}>
          <p style={{ margin: '0', fontWeight: 'bold', color: '#ffffff' }}>
            {data.name}
          </p>
          <p style={{ margin: '3px 0 0 0', color: '#ffffff' }}>
            {data.value} ({percent}%)
          </p>
        </div>
      );
    };

    return (
      <div style={{ width: '100%', height: 350 }}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart onClick={null}>
            <Pie
              data={pieData}
              cx="50%"
              cy="50%"
              labelLine={{
                stroke: '#9ca3af',
                strokeWidth: 1
              }}
              label={renderCustomLabel}
              outerRadius={100}
              fill="#8884d8"
              dataKey="value"
              onClick={null}
            >
              {pieData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={colors[index % colors.length]} />
              ))}
            </Pie>
            <Tooltip content={<PieTooltip />} />
          </PieChart>
        </ResponsiveContainer>
      </div>
    );
  };

  // Render appropriate chart type
  const renderChart = () => {
    switch (type?.toLowerCase()) {
      case 'bar':
        return renderBarChart();
      case 'line':
        return renderLineChart();
      case 'pie':
        return renderPieChart();
      default:
        return <div className="text-red-400">Unsupported chart type: {type}</div>;
    }
  };

  return (
    <div style={{
      display: 'block',
      width: '100%',
      margin: '8px 0',
      padding: '12px',
      backgroundColor: '#1f2937',
      borderRadius: '8px',
      border: '1px solid #374151',
      boxSizing: 'border-box',
    }}>
      {title && (
        <h3 style={{
          fontSize: '0.8rem',
          fontWeight: '600',
          color: '#f3f4f6',
          marginBottom: '10px',
          paddingBottom: '8px',
          borderBottom: '1px solid #374151',
        }}>
          {title}
        </h3>
      )}
      {/* Explicit block + width so ResponsiveContainer always gets a measured pixel width */}
      <div style={{ display: 'block', width: '100%' }}>
        {renderChart()}
      </div>
    </div>
  );
};

export default ChartComponent;
