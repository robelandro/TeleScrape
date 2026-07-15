import { useState, useEffect } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Login from "./components/Login";
import Dashboard from "./components/Dashboard";
import Jobs from "./components/Jobs";
import Channels from "./components/Channels";
import { LogOut, BarChart3, Briefcase, Radio, User as UserIcon } from "lucide-react";

const queryClient = new QueryClient();

export default function App() {
  const [token, setToken] = useState<string | null>(null);
  const [username, setUsername] = useState<string | null>(null);
  const [role, setRole] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"dashboard" | "jobs" | "channels">("dashboard");

  // Read auth info on mount
  useEffect(() => {
    const savedToken = localStorage.getItem("telescrape_token");
    const savedUsername = localStorage.getItem("telescrape_username");
    const savedRole = localStorage.getItem("telescrape_role");

    if (savedToken && savedUsername && savedRole) {
      setToken(savedToken);
      setUsername(savedUsername);
      setRole(savedRole);
    }
  }, []);

  const handleLoginSuccess = (userToken: string, userUsername: string, userRole: string) => {
    setToken(userToken);
    setUsername(userUsername);
    setRole(userRole);
    setActiveTab("dashboard");
  };

  const handleLogout = () => {
    localStorage.removeItem("telescrape_token");
    localStorage.removeItem("telescrape_username");
    localStorage.removeItem("telescrape_role");
    setToken(null);
    setUsername(null);
    setRole(null);
  };

  if (!token) {
    return <Login onLoginSuccess={handleLoginSuccess} />;
  }

  return (
    <QueryClientProvider client={queryClient}>
      <div className="min-h-screen bg-gray-50 flex flex-col font-sans">
        {/* Navigation Navbar */}
        <header className="bg-white border-b border-gray-100 shadow-sm sticky top-0 z-50">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between h-16 items-center">
              <div className="flex items-center space-x-3">
                <div className="bg-blue-600 p-2 rounded-lg text-white">
                  <BarChart3 className="w-5 h-5" />
                </div>
                <span className="text-xl font-black text-gray-900 tracking-tight">TeleScrape</span>
              </div>

              {/* Navigation Tabs */}
              <nav className="flex space-x-1">
                <button
                  id="tab-dashboard"
                  onClick={() => setActiveTab("dashboard")}
                  className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-sm font-semibold transition duration-150 cursor-pointer ${activeTab === "dashboard" ? "bg-blue-50 text-blue-700" : "text-gray-500 hover:bg-gray-50 hover:text-gray-900"}`}
                >
                  <BarChart3 className="w-4 h-4" />
                  <span>Dashboard</span>
                </button>

                <button
                  id="tab-jobs"
                  onClick={() => setActiveTab("jobs")}
                  className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-sm font-semibold transition duration-150 cursor-pointer ${activeTab === "jobs" ? "bg-blue-50 text-blue-700" : "text-gray-500 hover:bg-gray-50 hover:text-gray-900"}`}
                >
                  <Briefcase className="w-4 h-4" />
                  <span>Jobs</span>
                </button>

                <button
                  id="tab-channels"
                  onClick={() => setActiveTab("channels")}
                  className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-sm font-semibold transition duration-150 cursor-pointer ${activeTab === "channels" ? "bg-blue-50 text-blue-700" : "text-gray-500 hover:bg-gray-50 hover:text-gray-900"}`}
                >
                  <Radio className="w-4 h-4" />
                  <span>Channels</span>
                </button>
              </nav>

              {/* User profile & logout */}
              <div className="flex items-center space-x-4">
                <div className="hidden sm:flex items-center space-x-2 bg-gray-50 px-3 py-1.5 rounded-lg border border-gray-100">
                  <UserIcon className="w-4 h-4 text-gray-400" />
                  <span className="text-sm font-medium text-gray-700">{username}</span>
                  <span className="text-xs font-bold text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded uppercase">
                    {role}
                  </span>
                </div>

                <button
                  id="btn-logout"
                  onClick={handleLogout}
                  className="flex items-center space-x-1 text-gray-500 hover:text-red-600 px-3 py-2 rounded-lg text-sm font-semibold transition duration-150 cursor-pointer hover:bg-red-50"
                  title="Sign Out"
                >
                  <LogOut className="w-4 h-4" />
                  <span className="hidden md:inline">Sign Out</span>
                </button>
              </div>
            </div>
          </div>
        </header>

        {/* Main Content Area */}
        <main className="flex-grow max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {activeTab === "dashboard" && <Dashboard />}
          {activeTab === "jobs" && <Jobs />}
          {activeTab === "channels" && <Channels />}
        </main>

        {/* Footer */}
        <footer className="bg-white border-t border-gray-100 py-6 text-center text-xs text-gray-400">
          <p>© {new Date().getFullYear()} TeleScrape Job Analytics. Local, safe, and open-source.</p>
        </footer>
      </div>
    </QueryClientProvider>
  );
}
