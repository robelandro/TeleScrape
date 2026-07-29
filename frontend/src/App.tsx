import { useState, useEffect } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Login from "./components/Login";
import Dashboard from "./components/Dashboard";
import Jobs from "./components/Jobs";
import Channels from "./components/Channels";
import Settings from "./components/Settings";
import { LogOut, BarChart3, Briefcase, Radio, User as UserIcon, Settings as SettingsIcon, Menu, X, FileText } from "lucide-react";

const queryClient = new QueryClient();

export default function App() {
  const [token, setToken] = useState<string | null>(null);
  const [username, setUsername] = useState<string | null>(null);
  const [role, setRole] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"dashboard" | "jobs" | "channels" | "settings">("dashboard");
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

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
      <div className="min-h-screen bg-gray-50 flex font-sans">
        {/* Sidebar */}
        <aside className={`${isSidebarOpen ? 'w-64' : 'w-20'} bg-white border-r border-gray-100 shadow-sm flex flex-col transition-all duration-300 z-50 sticky top-0 h-screen`}>
          <div className="flex justify-between items-center h-16 px-4 border-b border-gray-100">
            {isSidebarOpen && (
              <div className="flex items-center space-x-3 overflow-hidden">
                <div className="bg-blue-600 p-2 rounded-lg text-white flex-shrink-0">
                  <BarChart3 className="w-5 h-5" />
                </div>
                <span className="text-xl font-black text-gray-900 tracking-tight whitespace-nowrap">TeleScrape</span>
              </div>
            )}
            <button
              onClick={() => setIsSidebarOpen(!isSidebarOpen)}
              className="p-2 rounded-lg text-gray-500 hover:bg-gray-50 flex-shrink-0 cursor-pointer mx-auto"
            >
              {isSidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>

          <nav className="flex-1 px-3 py-6 space-y-2 overflow-y-auto">
            <button
              onClick={() => setActiveTab("dashboard")}
              className={`w-full flex items-center space-x-3 px-3 py-3 rounded-lg text-sm font-semibold transition duration-150 cursor-pointer ${activeTab === "dashboard" ? "bg-blue-50 text-blue-700" : "text-gray-500 hover:bg-gray-50 hover:text-gray-900"}`}
              title={!isSidebarOpen ? "Dashboard" : undefined}
            >
              <BarChart3 className="w-5 h-5 flex-shrink-0" />
              {isSidebarOpen && <span>Dashboard</span>}
            </button>

            <button
              onClick={() => setActiveTab("jobs")}
              className={`w-full flex items-center space-x-3 px-3 py-3 rounded-lg text-sm font-semibold transition duration-150 cursor-pointer ${activeTab === "jobs" ? "bg-blue-50 text-blue-700" : "text-gray-500 hover:bg-gray-50 hover:text-gray-900"}`}
              title={!isSidebarOpen ? "Jobs" : undefined}
            >
              <Briefcase className="w-5 h-5 flex-shrink-0" />
              {isSidebarOpen && <span>Jobs</span>}
            </button>

            <button
              onClick={() => setActiveTab("channels")}
              className={`w-full flex items-center space-x-3 px-3 py-3 rounded-lg text-sm font-semibold transition duration-150 cursor-pointer ${activeTab === "channels" ? "bg-blue-50 text-blue-700" : "text-gray-500 hover:bg-gray-50 hover:text-gray-900"}`}
              title={!isSidebarOpen ? "Channels" : undefined}
            >
              <Radio className="w-5 h-5 flex-shrink-0" />
              {isSidebarOpen && <span>Channels</span>}
            </button>

            <button
              onClick={() => setActiveTab("settings")}
              className={`w-full flex items-center space-x-3 px-3 py-3 rounded-lg text-sm font-semibold transition duration-150 cursor-pointer ${activeTab === "settings" ? "bg-blue-50 text-blue-700" : "text-gray-500 hover:bg-gray-50 hover:text-gray-900"}`}
              title={!isSidebarOpen ? "Settings" : undefined}
            >
              <SettingsIcon className="w-5 h-5 flex-shrink-0" />
              {isSidebarOpen && <span>Settings</span>}
            </button>

            <a
              href="http://localhost:8000/docs"
              target="_blank"
              rel="noopener noreferrer"
              className="w-full flex items-center space-x-3 px-3 py-3 rounded-lg text-sm font-semibold text-gray-500 hover:bg-gray-50 hover:text-gray-900 transition duration-150 cursor-pointer"
              title={!isSidebarOpen ? "API Docs" : undefined}
            >
              <FileText className="w-5 h-5 flex-shrink-0" />
              {isSidebarOpen && <span>API Docs</span>}
            </a>
          </nav>

          <div className="p-4 border-t border-gray-100 space-y-4">
            {isSidebarOpen && (
              <div className="flex items-center space-x-2 bg-gray-50 px-3 py-2 rounded-lg border border-gray-100">
                <UserIcon className="w-4 h-4 text-gray-400 flex-shrink-0" />
                <span className="text-sm font-medium text-gray-700 truncate">{username}</span>
                <span className="text-xs font-bold text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded uppercase flex-shrink-0">
                  {role}
                </span>
              </div>
            )}
            <button
              onClick={handleLogout}
              className={`w-full flex items-center justify-center space-x-2 text-gray-500 hover:text-red-600 px-3 py-2 rounded-lg text-sm font-semibold transition duration-150 cursor-pointer hover:bg-red-50`}
              title="Sign Out"
            >
              <LogOut className="w-5 h-5 flex-shrink-0" />
              {isSidebarOpen && <span>Sign Out</span>}
            </button>
          </div>
        </aside>

        {/* Main Content Area */}
        <div className="flex-1 flex flex-col min-h-screen overflow-hidden">
          <main className="flex-grow w-full p-8 overflow-y-auto">
            <div className="max-w-6xl mx-auto">
              {activeTab === "dashboard" && <Dashboard />}
              {activeTab === "jobs" && <Jobs />}
              {activeTab === "channels" && <Channels />}
              {activeTab === "settings" && <Settings />}
            </div>
          </main>

          {/* Footer */}
          <footer className="bg-white border-t border-gray-100 py-6 text-center text-xs text-gray-400 mt-auto">
            <p>© {new Date().getFullYear()} TeleScrape Job Analytics. Local, safe, and open-source.</p>
          </footer>
        </div>
      </div>
    </QueryClientProvider>
  );
}
