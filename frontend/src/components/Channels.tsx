import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch, getAuthRole } from "../api";
import { Plus, Trash2, ShieldAlert, CheckCircle2, AlertCircle, RefreshCw, BarChart2, XCircle } from "lucide-react";

// Helper component to format a date to YYYY-MM-DD
const formatDate = (date: Date) => date.toISOString().split("T")[0];

export default function Channels() {
  const [newChannel, setNewChannel] = useState("");
  const [scrapeModalChannelId, setScrapeModalChannelId] = useState<number | null>(null);
  const [startDate, setStartDate] = useState(formatDate(new Date(Date.now() - 30 * 24 * 60 * 60 * 1000))); // Default to 30 days ago
  const [endDate, setEndDate] = useState(formatDate(new Date()));
  const [successMsg, setSuccessMsg] = useState("");
  const [errorMsg, setErrorMsg] = useState("");
  const queryClient = useQueryClient();
  const userRole = getAuthRole();
  const isAdmin = userRole === "admin";

  const { data: channels, error, isLoading } = useQuery({
    queryKey: ["channels"],
    queryFn: () => apiFetch("/channels"),
    refetchInterval: 10000,
  });

  const addMutation = useMutation({
    mutationFn: (channel_name: string) =>
      apiFetch("/channels", {
        method: "POST",
        body: JSON.stringify({ channel_name }),
      }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["channels"] });
      setSuccessMsg(`Monitored source added: ${data.channel_name}`);
      setNewChannel("");
      setTimeout(() => setSuccessMsg(""), 5000);
    },
    onError: (err: any) => {
      setErrorMsg(err.message || "Failed to add channel.");
      setTimeout(() => setErrorMsg(""), 5000);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) =>
      apiFetch(`/channels/${id}`, {
        method: "DELETE",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["channels"] });
      setSuccessMsg("Monitored source successfully deleted.");
      setTimeout(() => setSuccessMsg(""), 5000);
    },
    onError: (err: any) => {
      setErrorMsg(err.message || "Failed to delete channel.");
      setTimeout(() => setErrorMsg(""), 5000);
    },
  });

  const scrapeMutation = useMutation({
    mutationFn: (data: { channelId: number; startDate: string; endDate: string }) =>
      apiFetch(`/channels/${data.channelId}/scrape`, {
        method: "POST",
        body: JSON.stringify({ start_date: data.startDate, end_date: data.endDate }),
      }),
    onSuccess: () => {
      setSuccessMsg("On-demand analysis started.");
      setScrapeModalChannelId(null);
      setTimeout(() => setSuccessMsg(""), 5000);
    },
    onError: (err: any) => {
      setErrorMsg(err.message || "Failed to start analysis.");
      setTimeout(() => setErrorMsg(""), 5000);
    },
  });

  const cancelScrapeMutation = useMutation({
    mutationFn: (channelId: number) =>
      apiFetch(`/channels/${channelId}/cancel_scrape`, {
        method: "POST",
      }),
    onSuccess: () => {
      setSuccessMsg("Scrape task cancelled.");
      setTimeout(() => setSuccessMsg(""), 5000);
    },
    onError: (err: any) => {
      setErrorMsg(err.message || "Failed to cancel scrape.");
      setTimeout(() => setErrorMsg(""), 5000);
    },
  });

  // Fetch statuses for channels to see if they are currently scraping
  // In a real app we might use websockets or a bulk endpoint, but polling individually is fine here
  const { data: scrapeStatuses } = useQuery({
    queryKey: ["scrapeStatuses", channels?.map((c: any) => c.id)],
    queryFn: async () => {
      if (!channels) return {};
      const statuses: Record<number, boolean> = {};
      for (const chan of channels) {
        try {
          const res = await apiFetch(`/channels/${chan.id}/scrape_status`);
          statuses[chan.id] = res.is_scraping;
        } catch (e) {
          statuses[chan.id] = false;
        }
      }
      return statuses;
    },
    enabled: !!channels,
    refetchInterval: 5000,
  });

  const handleAddChannel = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newChannel.trim()) return;
    addMutation.mutate(newChannel.trim());
  };

  return (
    <div className="space-y-6 animate-fadeIn">
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-3xl font-extrabold text-gray-900 tracking-tight">Telegram Channels</h1>
          <p className="text-gray-500 mt-1">Monitored public job posting channels. Incrementally scraped and parsed on interval cycles.</p>
        </div>
      </div>

      {successMsg && (
        <div className="bg-emerald-50 border-l-4 border-emerald-500 p-4 text-sm text-emerald-700 flex items-center space-x-2 rounded-md">
          <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
          <span>{successMsg}</span>
        </div>
      )}

      {errorMsg && (
        <div className="bg-red-50 border-l-4 border-red-500 p-4 text-sm text-red-700 flex items-center space-x-2 rounded-md">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Monitored List */}
        <div className="lg:col-span-2 bg-white p-6 rounded-xl shadow-sm border border-gray-100 space-y-4">
          <h3 className="text-lg font-bold text-gray-900">Active Monitoring Sources</h3>
          {isLoading ? (
            <div className="flex justify-center py-12">
              <RefreshCw className="animate-spin text-blue-600 w-8 h-8" />
            </div>
          ) : error ? (
            <p className="text-sm text-red-500">Error loading channels.</p>
          ) : channels.length === 0 ? (
            <p className="text-sm text-gray-500 py-6">No monitored channels in database.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-100 text-sm">
                <thead>
                  <tr className="text-left text-xs font-bold text-gray-400 uppercase tracking-wider">
                    <th className="py-3 px-4">Channel Name</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4">Last Message ID</th>
                    <th className="py-3 px-4">Last Scraped At</th>
                    {isAdmin && <th className="py-3 px-4 text-right">Actions</th>}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50 text-gray-700">
                  {channels.map((chan: any) => {
                    const isScraping = scrapeStatuses?.[chan.id];
                    return (
                      <tr key={chan.id} className="hover:bg-gray-50 transition duration-75">
                        <td className="py-3 px-4 font-semibold text-gray-900">{chan.channel_name}</td>
                        <td className="py-3 px-4">
                          <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${chan.is_active ? "bg-emerald-50 text-emerald-700" : "bg-gray-100 text-gray-600"}`}>
                            {chan.is_active ? "Active" : "Inactive"}
                          </span>
                        </td>
                        <td className="py-3 px-4 font-mono text-gray-500">{chan.last_scraped_message_id}</td>
                        <td className="py-3 px-4 text-gray-400">
                          {chan.last_scraped_at ? new Date(chan.last_scraped_at).toLocaleString() : "Never"}
                        </td>
                        {isAdmin && (
                          <td className="py-3 px-4 text-right flex justify-end space-x-2">
                            {isScraping ? (
                              <button
                                onClick={() => cancelScrapeMutation.mutate(chan.id)}
                                className="text-amber-500 hover:text-amber-700 p-1.5 hover:bg-amber-50 rounded-lg transition duration-100 cursor-pointer flex items-center space-x-1"
                                title="Cancel ongoing analysis"
                              >
                                <XCircle className="w-4 h-4" />
                                <span className="text-xs font-medium">Cancel</span>
                              </button>
                            ) : (
                              <button
                                onClick={() => setScrapeModalChannelId(chan.id)}
                                className="text-blue-500 hover:text-blue-700 p-1.5 hover:bg-blue-50 rounded-lg transition duration-100 cursor-pointer flex items-center space-x-1"
                                title="Analyze specific date range"
                              >
                                <BarChart2 className="w-4 h-4" />
                                <span className="text-xs font-medium">Analyze</span>
                              </button>
                            )}

                            <button
                              onClick={() => {
                                if (window.confirm(`Are you sure you want to stop monitoring and delete channel ${chan.channel_name}?`)) {
                                  deleteMutation.mutate(chan.id);
                                }
                              }}
                              className="text-red-500 hover:text-red-700 p-1.5 hover:bg-red-50 rounded-lg transition duration-100 cursor-pointer"
                              title="Delete monitoring source"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </td>
                        )}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Add Source Form */}
        <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 space-y-4">
          <h3 className="text-lg font-bold text-gray-900">Add Monitored Source</h3>

          {isAdmin ? (
            <form onSubmit={handleAddChannel} className="space-y-4">
              <div className="space-y-1">
                <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Channel Username</label>
                <input
                  type="text"
                  placeholder="e.g. @react_native_gigs"
                  value={newChannel}
                  onChange={(e) => setNewChannel(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  required
                />
              </div>
              <button
                type="submit"
                disabled={addMutation.isPending}
                className="w-full bg-blue-600 text-white font-semibold py-2 rounded-lg text-sm hover:bg-blue-700 disabled:bg-blue-400 transition duration-150 cursor-pointer flex items-center justify-center space-x-1"
              >
                <Plus className="w-4 h-4" />
                <span>{addMutation.isPending ? "Adding Source..." : "Add Source"}</span>
              </button>
            </form>
          ) : (
            <div className="bg-amber-50 border border-amber-200 p-4 rounded-lg flex items-start space-x-2 text-amber-800 text-sm">
              <ShieldAlert className="w-4 h-4 mt-0.5 flex-shrink-0" />
              <div>
                <span className="font-semibold">Administrator Only</span>
                <p className="mt-1 text-xs text-amber-700">Your viewer role only has permission to read monitoring sources. Adding/removing sources is restricted.</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Scrape Modal */}
      {scrapeModalChannelId && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6 space-y-6">
            <h3 className="text-xl font-bold text-gray-900">On-Demand Analysis</h3>
            <p className="text-sm text-gray-500">Select the date range you want to analyze for this channel.</p>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Start Date</label>
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">End Date</label>
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>

            <div className="flex justify-end space-x-3 pt-4 border-t border-gray-100">
              <button
                onClick={() => setScrapeModalChannelId(null)}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={() => scrapeMutation.mutate({ channelId: scrapeModalChannelId, startDate, endDate })}
                disabled={scrapeMutation.isPending}
                className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg disabled:opacity-50 cursor-pointer"
              >
                {scrapeMutation.isPending ? "Starting..." : "Start Analysis"}
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
