import React, { useState, useEffect } from "react";
import { apiFetch } from "../api";
import { Settings as SettingsIcon, Save, AlertCircle, CheckCircle } from "lucide-react";

export default function Settings() {
  const [apiId, setApiId] = useState("");
  const [apiHash, setApiHash] = useState("");
  const [isConfigured, setIsConfigured] = useState(false);
  const [loading, setLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  useEffect(() => {
    // Check if telegram client is already configured
    apiFetch("/telegram/config")
      .then((data) => {
        setIsConfigured(data.is_configured);
      })
      .catch((err) => {
        console.error("Failed to fetch telegram config status:", err);
      });
  }, []);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setStatusMessage(null);

    try {
      await apiFetch("/telegram/config", {
        method: "POST",
        body: JSON.stringify({ api_id: apiId, api_hash: apiHash }),
      });
      setStatusMessage({ type: "success", text: "Telegram configuration saved successfully." });
      setIsConfigured(true);
      // Optional: clear fields after saving so they aren't visible
      setApiId("");
      setApiHash("");
    } catch (err: any) {
      setStatusMessage({ type: "error", text: err.message || "Failed to save configuration." });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-8 animate-fadeIn max-w-2xl">
      <div>
        <h1 className="text-3xl font-extrabold text-gray-900 tracking-tight flex items-center space-x-3">
          <SettingsIcon className="w-8 h-8 text-gray-400" />
          <span>Settings</span>
        </h1>
        <p className="text-gray-500 mt-1">Configure your system preferences and external connections.</p>
      </div>

      <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
        <h3 className="text-lg font-bold text-gray-900 mb-4">Telegram Client Configuration</h3>

        {isConfigured ? (
          <div className="mb-6 bg-green-50 border border-green-200 text-green-800 p-4 rounded-lg flex items-start space-x-3">
            <CheckCircle className="w-5 h-5 flex-shrink-0 text-green-600 mt-0.5" />
            <div>
              <p className="font-semibold">Telegram Client is Configured</p>
              <p className="text-sm mt-1">
                The scraper is set up to run against real Telegram channels. You can override the existing configuration by submitting the form below.
              </p>
            </div>
          </div>
        ) : (
          <div className="mb-6 bg-amber-50 border border-amber-200 text-amber-800 p-4 rounded-lg flex items-start space-x-3">
            <AlertCircle className="w-5 h-5 flex-shrink-0 text-amber-600 mt-0.5" />
            <div>
              <p className="font-semibold">Simulation Mode Active</p>
              <p className="text-sm mt-1">
                Because Telegram credentials are not configured, the system is currently falling back to generating simulated mock data.
              </p>
            </div>
          </div>
        )}

        {statusMessage && (
          <div className={`mb-6 p-4 rounded-lg text-sm ${statusMessage.type === "success" ? "bg-green-50 text-green-700 border border-green-200" : "bg-red-50 text-red-700 border border-red-200"}`}>
            {statusMessage.text}
          </div>
        )}

        <form onSubmit={handleSave} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Telegram API ID</label>
            <input
              type="text"
              required
              value={apiId}
              onChange={(e) => setApiId(e.target.value)}
              className="appearance-none rounded-md relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
              placeholder="e.g. 1234567"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Telegram API Hash</label>
            <input
              type="text"
              required
              value={apiHash}
              onChange={(e) => setApiHash(e.target.value)}
              className="appearance-none rounded-md relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
              placeholder="e.g. a1b2c3d4e5f6g7h8i9j0"
            />
          </div>

          <div className="pt-2">
            <button
              type="submit"
              disabled={loading}
              className="flex items-center justify-center space-x-2 py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:bg-blue-400 cursor-pointer"
            >
              <Save className="w-4 h-4" />
              <span>{loading ? "Saving..." : "Save Configuration"}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
