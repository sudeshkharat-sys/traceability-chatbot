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
  Legend,
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

  // Render Bar Chart
  const renderBarChart = () => {
    const xAxis = config.xAxis || 'name';
    const yAxes = config.yAxis || Object.keys(data[0]).filter(key => key !== xAxis);

    return (
      <ResponsiveContainer width="100%" height={400}>
        <BarChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis
            dataKey={xAxis}
            stroke="#9ca3af"
            style={{ fontSize: '12px' }}
          />
          <YAxis
            stroke="#9ca3af"
            style={{ fontSize: '12px' }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#1f2937',
              border: '1px solid #374151',
              borderRadius: '6px',
              color: '#f3f4f6'
            }}
          />
          <Legend
            wrapperStyle={{ color: '#9ca3af' }}
          />
          {yAxes.map((key, index) => (
            <Bar
              key={key}
              dataKey={key}
              fill={colors[index % colors.length]}
              radius={[4, 4, 0, 0]}
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

    return (
      <ResponsiveContainer width="100%" height={400}>
        <LineChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis
            dataKey={xAxis}
            stroke="#9ca3af"
            style={{ fontSize: '12px' }}
          />
          <YAxis
            stroke="#9ca3af"
            style={{ fontSize: '12px' }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#1f2937',
              border: '1px solid #374151',
              borderRadius: '6px',
              color: '#f3f4f6'
            }}
          />
          <Legend
            wrapperStyle={{ color: '#9ca3af' }}
          />
          {yAxes.map((key, index) => (
            <Line
              key={key}
              type="monotone"
              dataKey={key}
              stroke={colors[index % colors.length]}
              strokeWidth={2}
              dot={{ fill: colors[index % colors.length], r: 4 }}
              activeDot={{ r: 6 }}
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

    return (
      <ResponsiveContainer width="100%" height={400}>
        <PieChart>
          <Pie
            data={pieData}
            cx="50%"
            cy="50%"
            labelLine={true}
            label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(1)}%`}
            outerRadius={120}
            fill="#8884d8"
            dataKey="value"
          >
            {pieData.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={colors[index % colors.length]} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              backgroundColor: '#1f2937',
              border: '1px solid #374151',
              borderRadius: '6px',
              color: '#f3f4f6'
            }}
          />
          <Legend
            wrapperStyle={{ color: '#9ca3af' }}
          />
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
    <div className="chart-container my-4 p-4 bg-gray-800 rounded-lg border border-gray-700">
      {title && (
        <h3 className="text-lg font-semibold text-gray-100 mb-4 text-center">
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
