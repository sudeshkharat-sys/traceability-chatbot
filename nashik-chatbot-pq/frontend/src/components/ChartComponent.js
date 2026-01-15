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

  // Render Bar Chart
  const renderBarChart = () => {
    const xAxis = config.xAxis || 'name';
    const yAxes = config.yAxis || Object.keys(data[0]).filter(key => key !== xAxis);
    const xAxisLabel = config.xAxisLabel || xAxis;
    const yAxisLabel = config.yAxisLabel || (yAxes.length === 1 ? yAxes[0] : 'Value');

    return (
      <ResponsiveContainer width="100%" height={320}>
        <BarChart
          data={data}
          onClick={null}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis
            dataKey={xAxis}
            stroke="#9ca3af"
            style={{ fontSize: '12px' }}
            label={{
              value: xAxisLabel,
              position: 'insideBottom',
              offset: -10,
              style: { fill: '#9ca3af', fontSize: '14px', fontWeight: 'bold' }
            }}
          />
          <YAxis
            stroke="#9ca3af"
            style={{ fontSize: '12px' }}
            label={{
              value: yAxisLabel,
              angle: -90,
              position: 'insideLeft',
              style: { fill: '#9ca3af', fontSize: '14px', fontWeight: 'bold', textAnchor: 'middle' }
            }}
          />
          <Tooltip content={<CustomTooltip />} />
          {yAxes.map((key, index) => (
            <Bar
              key={key}
              dataKey={key}
              fill={colors[index % colors.length]}
              radius={[4, 4, 0, 0]}
              onClick={null}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    );
  };

  // Render Line Chart
  const renderLineChart = () => {
    const xAxis = config.xAxis || 'name';
    const yAxes = config.yAxis || Object.keys(data[0]).filter(key => key !== xAxis);
    const xAxisLabel = config.xAxisLabel || xAxis;
    const yAxisLabel = config.yAxisLabel || (yAxes.length === 1 ? yAxes[0] : 'Value');

    return (
      <ResponsiveContainer width="100%" height={320}>
        <LineChart
          data={data}
          onClick={null}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis
            dataKey={xAxis}
            stroke="#9ca3af"
            style={{ fontSize: '12px' }}
            tickFormatter={formatMonth}
            label={{
              value: xAxisLabel,
              position: 'insideBottom',
              offset: -10,
              style: { fill: '#9ca3af', fontSize: '14px', fontWeight: 'bold' }
            }}
          />
          <YAxis
            stroke="#9ca3af"
            style={{ fontSize: '12px' }}
            label={{
              value: yAxisLabel,
              angle: -90,
              position: 'insideLeft',
              style: { fill: '#9ca3af', fontSize: '14px', fontWeight: 'bold', textAnchor: 'middle' }
            }}
          />
          <Tooltip content={<CustomTooltip />} />
          {yAxes.map((key, index) => (
            <Line
              key={key}
              type="monotone"
              dataKey={key}
              stroke={colors[index % colors.length]}
              strokeWidth={2}
              dot={{ fill: colors[index % colors.length], r: 4 }}
              activeDot={{ r: 6 }}
              onClick={null}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    );
  };

  // Render Pie Chart
  const renderPieChart = () => {
    const nameKey = config.nameKey || 'name';
    const valueKey = config.valueKey || 'value';

    // Ensure data has the correct format for pie chart
    const pieData = data.map(item => ({
      name: item[nameKey],
      value: parseFloat(item[valueKey]) || 0
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
      <ResponsiveContainer width="100%" height={350}>
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
    <div className="chart-container my-3 p-3 bg-gray-800 rounded-lg border border-gray-700">
      {title && (
        <h3 className="text-sm font-semibold text-gray-100 mb-3 pb-2 border-b border-gray-700">
          {title}
        </h3>
      )}
      <div className="chart-wrapper">
        {renderChart()}
      </div>
    </div>
  );
};

export default ChartComponent;
