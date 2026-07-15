import { useQuery } from "@tanstack/react-query";
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from "recharts";
import { apiFetch } from "../api";
import { Briefcase, Radio, TrendingUp, AlertCircle, RefreshCw } from "lucide-react";

export default function Dashboard() {
  const { data: summary, error: summaryError, isLoading: summaryLoading, refetch: refetchSummary } = useQuery({
    queryKey: ["dashboard-summary"],
    queryFn: () => apiFetch("/dashboard/summary"),
    refetchInterval: 10000, // Refetch every 10s for real-time feel
  });

  const { data: charts, error: chartsError, isLoading: chartsLoading, refetch: refetchCharts } = useQuery({
    queryKey: ["dashboard-charts"],
    queryFn: () => apiFetch("/dashboard/charts"),
    refetchInterval: 10000,
  });

  const handleRefresh = () => {
    refetchSummary();
    refetchCharts();
  };

  if (summaryLoading || chartsLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-20 space-y-4">
        <RefreshCw className="animate-spin text-blue-600 w-10 h-10" />
        <span className="text-gray-500 font-medium">Loading local analytics and trend calculations...</span>
      </div>
    );
  }

  if (summaryError || chartsError) {
    return (
      <div className="bg-red-50 border border-red-200 text-red-700 p-6 rounded-lg flex items-start space-x-3 max-w-2xl mx-auto my-10">
        <AlertCircle className="w-6 h-6 flex-shrink-0" />
        <div>
          <h4 className="font-semibold text-lg">Error loading dashboard</h4>
          <p className="mt-1 text-sm">{(summaryError as Error)?.message || (chartsError as Error)?.message || "Could not connect to the local API."}</p>
        </div>
      </div>
    );
  }

  // Pick random colors for Recharts Lines
  const colors = ["#2563eb", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#14b8a6"];

  // Unique categories from charts.category_trends to draw lines dynamically
  const categories: string[] = [];
  if (charts?.category_trends && charts.category_trends.length > 0) {
    const firstPoint = charts.category_trends[0];
    Object.keys(firstPoint).forEach((key) => {
      if (key !== "date_str") {
        categories.push(key);
      }
    });
  }

  return (
    <div className="space-y-8 animate-fadeIn">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-extrabold text-gray-900 tracking-tight">System Dashboard</h1>
          <p className="text-gray-500 mt-1">Real-time local job market growth rates and channel performance metrics.</p>
        </div>
        <button
          onClick={handleRefresh}
          className="flex items-center space-x-2 bg-blue-50 border border-blue-200 hover:bg-blue-100 text-blue-700 px-4 py-2 rounded-lg text-sm font-semibold transition duration-150 cursor-pointer"
        >
          <RefreshCw className="w-4 h-4" />
          <span>Refresh Data</span>
        </button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 flex items-center justify-between">
          <div className="space-y-1">
            <span className="text-sm font-semibold text-gray-400 uppercase tracking-wider">Total Scraped Jobs</span>
            <h3 className="text-3xl font-bold text-gray-900" id="kpi-total-jobs">{summary?.total_jobs_scraped ?? 0}</h3>
          </div>
          <div className="bg-blue-50 p-4 rounded-xl text-blue-600">
            <Briefcase className="w-6 h-6" />
          </div>
        </div>

        <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 flex items-center justify-between">
          <div className="space-y-1">
            <span className="text-sm font-semibold text-gray-400 uppercase tracking-wider">Monitored Sources</span>
            <h3 className="text-3xl font-bold text-gray-900" id="kpi-monitored-channels">{summary?.monitored_sources ?? 0}</h3>
          </div>
          <div className="bg-emerald-50 p-4 rounded-xl text-emerald-600">
            <Radio className="w-6 h-6" />
          </div>
        </div>

        <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 flex items-center justify-between">
          <div className="space-y-1">
            <span className="text-sm font-semibold text-gray-400 uppercase tracking-wider">Fastest Growing Category</span>
            <h3 className="text-xl font-bold text-gray-900 mt-1" id="kpi-fastest-growing">{summary?.fastest_growing ?? "N/A"}</h3>
          </div>
          <div className="bg-amber-50 p-4 rounded-xl text-amber-600">
            <TrendingUp className="w-6 h-6" />
          </div>
        </div>
      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Daily Ingestion Volume Chart */}
        <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 space-y-4">
          <div>
            <h3 className="text-lg font-bold text-gray-900">Daily Ingestion Volume</h3>
            <p className="text-xs text-gray-400">Total job postings scraped across all channels per day (last 14 days).</p>
          </div>
          <div className="h-80" id="chart-volume">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={charts?.volume_by_day ?? []}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="date_str" tick={{ fontSize: 11 }} />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="post_count" fill="#2563eb" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Category Trends Chart */}
        <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 space-y-4">
          <div>
            <h3 className="text-lg font-bold text-gray-900">Weekly Category Trends</h3>
            <p className="text-xs text-gray-400">Comparing relative weekly post volume per category (spacy matched NLP terms).</p>
          </div>
          <div className="h-80" id="chart-trends">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={charts?.category_trends ?? []}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="date_str" tick={{ fontSize: 11 }} />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                {categories.map((cat, idx) => (
                  <Line
                    key={cat}
                    type="monotone"
                    dataKey={cat}
                    stroke={colors[idx % colors.length]}
                    strokeWidth={2}
                    dot={{ r: 3 }}
                    activeDot={{ r: 5 }}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
}
