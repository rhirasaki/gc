import React from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell,
} from 'recharts';
import type { AnalyticsData } from '../../types/electron.d';

const COLORS = ['#3b82f6', '#6366f1', '#8b5cf6', '#a78bfa', '#c4b5fd'];

const Dashboard: React.FC = () => {
  const { data, isLoading } = useQuery<AnalyticsData>({
    queryKey: ['analytics'],
    queryFn: () => window.electronAPI.imagesAnalytics(),
    staleTime: 60000,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-48 text-gray-500">
        <div className="flex items-center gap-3">
          <div className="w-5 h-5 border-2 border-gray-600 border-t-blue-500 rounded-full animate-spin" />
          Loading analytics...
        </div>
      </div>
    );
  }

  const pieData = [
    { name: 'RAW', value: data?.rawCount ?? 0 },
    { name: 'JPG', value: data?.jpgCount ?? 0 },
  ].filter((d) => d.value > 0);

  const uploadPieData = [
    { name: 'Uploaded', value: data?.uploadedCount ?? 0 },
    { name: 'Pending', value: (data?.totalImages ?? 0) - (data?.uploadedCount ?? 0) },
  ].filter((d) => d.value > 0);

  return (
    <div className="space-y-6 p-6 overflow-y-auto h-full">
      {/* Top stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Total Photos"
          value={data?.totalImages.toLocaleString() ?? '0'}
          icon={
            <svg className="w-5 h-5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
          }
        />
        <StatCard
          label="RAW Files"
          value={data?.rawCount.toLocaleString() ?? '0'}
          valueColor="text-amber-400"
          icon={
            <svg className="w-5 h-5 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4" />
            </svg>
          }
        />
        <StatCard
          label="Uploaded"
          value={data?.uploadedCount.toLocaleString() ?? '0'}
          valueColor="text-green-400"
          icon={
            <svg className="w-5 h-5 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
          }
        />
        <StatCard
          label="Geotagged"
          value={data?.withLocation.toLocaleString() ?? '0'}
          icon={
            <svg className="w-5 h-5 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          }
        />
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Photos by month */}
        <div className="card lg:col-span-2">
          <h3 className="text-white font-medium mb-4">Photos by Month</h3>
          {data?.byDate && data.byDate.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={[...data.byDate].reverse()}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                <XAxis
                  dataKey="month"
                  tick={{ fill: '#6b7280', fontSize: 11 }}
                  tickFormatter={(v) => v?.slice(5) ?? v}
                />
                <YAxis tick={{ fill: '#6b7280', fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#111827', border: '1px solid #374151', borderRadius: '8px' }}
                  labelStyle={{ color: '#e5e7eb' }}
                  itemStyle={{ color: '#93c5fd' }}
                />
                <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-48 flex items-center justify-center text-gray-600 text-sm">No data yet</div>
          )}
        </div>

        {/* File type breakdown */}
        <div className="card">
          <h3 className="text-white font-medium mb-4">File Types</h3>
          {pieData.length > 0 ? (
            <div>
              <ResponsiveContainer width="100%" height={150}>
                <PieChart>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={40}
                    outerRadius={65}
                    paddingAngle={3}
                    dataKey="value"
                  >
                    {pieData.map((_, index) => (
                      <Cell key={`cell-${index}`} fill={index === 0 ? '#f59e0b' : '#3b82f6'} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{ backgroundColor: '#111827', border: '1px solid #374151', borderRadius: '8px' }}
                    itemStyle={{ color: '#e5e7eb' }}
                  />
                </PieChart>
              </ResponsiveContainer>
              <div className="flex justify-center gap-4 mt-2">
                {pieData.map((entry, i) => (
                  <div key={entry.name} className="flex items-center gap-1.5 text-xs text-gray-400">
                    <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: i === 0 ? '#f59e0b' : '#3b82f6' }} />
                    {entry.name}: {entry.value.toLocaleString()}
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="h-48 flex items-center justify-center text-gray-600 text-sm">No data yet</div>
          )}
        </div>
      </div>

      {/* Camera breakdown */}
      {data?.byCamera && data.byCamera.length > 0 && (
        <div className="card">
          <h3 className="text-white font-medium mb-4">Photos by Camera</h3>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={data.byCamera} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" horizontal={false} />
              <XAxis type="number" tick={{ fill: '#6b7280', fontSize: 11 }} />
              <YAxis
                type="category"
                dataKey="camera_model"
                width={150}
                tick={{ fill: '#9ca3af', fontSize: 11 }}
              />
              <Tooltip
                contentStyle={{ backgroundColor: '#111827', border: '1px solid #374151', borderRadius: '8px' }}
                labelStyle={{ color: '#e5e7eb' }}
                itemStyle={{ color: '#93c5fd' }}
              />
              <Bar dataKey="count" fill="#6366f1" radius={[0, 4, 4, 0]}>
                {data.byCamera.map((_, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Upload status */}
      {uploadPieData.length > 0 && (
        <div className="card">
          <h3 className="text-white font-medium mb-4">Upload Status</h3>
          <div className="flex items-center gap-6">
            <div className="w-32 h-32">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={uploadPieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={30}
                    outerRadius={50}
                    paddingAngle={2}
                    dataKey="value"
                  >
                    {uploadPieData.map((_, index) => (
                      <Cell key={index} fill={index === 0 ? '#22c55e' : '#374151'} />
                    ))}
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="space-y-2">
              {uploadPieData.map((entry, i) => (
                <div key={entry.name} className="flex items-center gap-3">
                  <div className="w-3 h-3 rounded-full" style={{ backgroundColor: i === 0 ? '#22c55e' : '#374151' }} />
                  <span className="text-sm text-gray-400">{entry.name}:</span>
                  <span className="text-sm text-white font-medium">{entry.value.toLocaleString()}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const StatCard: React.FC<{
  label: string;
  value: string;
  valueColor?: string;
  icon: React.ReactNode;
}> = ({ label, value, valueColor = 'text-white', icon }) => (
  <div className="card flex items-center gap-4">
    <div className="w-10 h-10 bg-gray-800 rounded-lg flex items-center justify-center flex-shrink-0">
      {icon}
    </div>
    <div>
      <div className={`text-2xl font-bold ${valueColor}`}>{value}</div>
      <div className="text-xs text-gray-500 mt-0.5">{label}</div>
    </div>
  </div>
);

export default Dashboard;
