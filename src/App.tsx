import React, { useEffect, useState, useCallback } from 'react';
import { DashboardData } from './types/portfolio';
import { fetchDashboardData } from './services/portfolioData';
import { Dashboard } from './components/Dashboard';

export const App: React.FC = () => {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);

  const loadData = useCallback(async (isRefresh = false) => {
    if (isRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }

    try {
      const result = await fetchDashboardData();
      setData(result);
    } catch (err) {
      console.error('Error fetching dashboard data:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  if (loading || !data) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 py-8 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto space-y-8 animate-pulse">
        {/* Header Skeleton */}
        <div className="flex items-center justify-between pb-4 border-b border-slate-800">
          <div className="space-y-2">
            <div className="h-8 w-48 bg-slate-900 rounded-lg"></div>
            <div className="h-4 w-64 bg-slate-900/60 rounded"></div>
          </div>
          <div className="h-9 w-24 bg-slate-900 rounded-xl"></div>
        </div>

        {/* Metric Cards Skeleton */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className="h-32 bg-slate-900 border border-slate-800 rounded-2xl p-5"
            ></div>
          ))}
        </div>

        {/* Chart Skeleton */}
        <div className="h-96 bg-slate-900 border border-slate-800 rounded-2xl p-6"></div>
      </div>
    );
  }

  return (
    <Dashboard
      initialData={data}
      onRefresh={() => loadData(true)}
      isRefreshing={refreshing}
    />
  );
};

export default App;
