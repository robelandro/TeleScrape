import React, { useState, useEffect } from "react";
import { apiFetch } from "../api";
import { Settings as SettingsIcon, Save, AlertCircle, CheckCircle, LogIn, LogOut } from "lucide-react";

export default function Settings() {
  const [apiId, setApiId] = useState("");
  const [apiHash, setApiHash] = useState("");
  const [isConfigured, setIsConfigured] = useState(false);
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [loading, setLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // OTP flow state
  const [phoneNumber, setPhoneNumber] = useState("");
  const [phoneCodeHash, setPhoneCodeHash] = useState("");
  const [otpCode, setOtpCode] = useState("");
  const [waitingForOtp, setWaitingForOtp] = useState(false);

  const fetchStatus = () => {
    apiFetch("/telegram/config")
      .then((data) => {
        setIsConfigured(data.is_configured);
      })
      .catch(console.error);

    apiFetch("/telegram/auth/status")
      .then((data) => {
        setIsLoggedIn(data.is_logged_in);
      })
      .catch(console.error);
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  const handleSaveConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setStatusMessage(null);

    try {
      await apiFetch("/telegram/config", {
        method: "POST",
        body: JSON.stringify({ api_id: apiId, api_hash: apiHash }),
      });
      setStatusMessage({ type: "success", text: "Telegram configuration saved to database." });
      setIsConfigured(true);
      setApiId("");
      setApiHash("");
      fetchStatus();
    } catch (err: any) {
      setStatusMessage({ type: "error", text: err.message || "Failed to save configuration." });
    } finally {
      setLoading(false);
    }
  };

  const handleSendCode = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setStatusMessage(null);

    try {
      const data = await apiFetch("/telegram/auth/send_code", {
        method: "POST",
        body: JSON.stringify({ phone_number: phoneNumber }),
      });
      setPhoneCodeHash(data.phone_code_hash);
      setWaitingForOtp(true);
      setStatusMessage({ type: "success", text: "OTP Code sent to your Telegram app." });
    } catch (err: any) {
      setStatusMessage({ type: "error", text: err.message || "Failed to send code." });
    } finally {
      setLoading(false);
    }
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setStatusMessage(null);

    try {
      await apiFetch("/telegram/auth/login", {
        method: "POST",
        body: JSON.stringify({ phone_number: phoneNumber, phone_code_hash: phoneCodeHash, code: otpCode }),
      });
      setStatusMessage({ type: "success", text: "Logged in to Telegram successfully." });
      setWaitingForOtp(false);
      fetchStatus();
    } catch (err: any) {
      setStatusMessage({ type: "error", text: err.message || "Failed to login." });
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = async () => {
    setLoading(true);
    setStatusMessage(null);
    try {
      await apiFetch("/telegram/auth/logout", { method: "POST" });
      setStatusMessage({ type: "success", text: "Logged out from Telegram successfully." });
      fetchStatus();
    } catch (err: any) {
      setStatusMessage({ type: "error", text: err.message || "Failed to log out." });
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

        <form onSubmit={handleSaveConfig} className="space-y-4 mb-8">
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

          <div className="pt-2 border-b border-gray-100 pb-8">
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

        {isConfigured && (
          <div className="mt-8">
            <h3 className="text-lg font-bold text-gray-900 mb-4">Telegram Authentication</h3>

            {isLoggedIn ? (
              <div className="space-y-4">
                <div className="bg-green-50 border border-green-200 text-green-800 p-4 rounded-lg flex items-center space-x-3">
                   <CheckCircle className="w-5 h-5 flex-shrink-0 text-green-600" />
                   <span className="font-semibold">Connected to Telegram via Active Session</span>
                </div>
                <button
                  onClick={handleLogout}
                  disabled={loading}
                  className="flex items-center justify-center space-x-2 py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:bg-red-400 cursor-pointer"
                >
                  <LogOut className="w-4 h-4" />
                  <span>{loading ? "Processing..." : "Log Out of Telegram"}</span>
                </button>
              </div>
            ) : (
              <div className="space-y-4">
                {!waitingForOtp ? (
                  <form onSubmit={handleSendCode} className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Phone Number (International Format)</label>
                      <input
                        type="text"
                        required
                        value={phoneNumber}
                        onChange={(e) => setPhoneNumber(e.target.value)}
                        className="appearance-none rounded-md relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                        placeholder="e.g. +1234567890"
                      />
                    </div>
                    <button
                      type="submit"
                      disabled={loading}
                      className="flex items-center justify-center space-x-2 py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:bg-blue-400 cursor-pointer"
                    >
                      <LogIn className="w-4 h-4" />
                      <span>{loading ? "Sending Code..." : "Send OTP Code"}</span>
                    </button>
                  </form>
                ) : (
                  <form onSubmit={handleLogin} className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">OTP Code</label>
                      <input
                        type="text"
                        required
                        value={otpCode}
                        onChange={(e) => setOtpCode(e.target.value)}
                        className="appearance-none rounded-md relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                        placeholder="Enter the code sent to your Telegram app"
                      />
                    </div>
                    <button
                      type="submit"
                      disabled={loading}
                      className="flex items-center justify-center space-x-2 py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-emerald-600 hover:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-emerald-500 disabled:bg-emerald-400 cursor-pointer"
                    >
                      <CheckCircle className="w-4 h-4" />
                      <span>{loading ? "Logging in..." : "Submit Code & Login"}</span>
                    </button>
                  </form>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
