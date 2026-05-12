import { useEffect, useState, useCallback } from "react";
import { Shell } from "../components/Shell";

const WARNING_COLORS = {
  mobile_phone: "bg-red-500/20 border-red-500 text-red-300",
  multi_person: "bg-orange-500/20 border-orange-500 text-orange-300",
  identity_mismatch: "bg-red-600/20 border-red-600 text-red-300",
  eye_gaze: "bg-yellow-500/20 border-yellow-500 text-yellow-300",
  head_pose: "bg-yellow-500/20 border-yellow-500 text-yellow-300",
  partial_human: "bg-orange-500/20 border-orange-500 text-orange-300",
  assistance_suspected: "bg-red-600/20 border-red-600 text-red-300",
  reading_pattern: "bg-yellow-500/20 border-yellow-500 text-yellow-300",
  default: "bg-slate-500/20 border-slate-500 text-slate-300",
};

const WARNING_ICONS = {
  mobile_phone: "📱",
  multi_person: "👥",
  identity_mismatch: "🚫",
  eye_gaze: "👀",
  head_pose: "🔄",
  partial_human: "👤",
  assistance_suspected: "🆘",
  reading_pattern: "📖",
  default: "⚠️",
};

export function AdminDashboard() {
  const [sessions, setSessions] = useState([]);
  const [selectedSession, setSelectedSession] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState("overview"); // overview, sessions, incidents, analytics

  // Fetch sessions
  const fetchSessions = useCallback(async () => {
    try {
      const response = await fetch(
        `${import.meta.env.VITE_API_URL || "http://localhost:8000"}/api/interviews`
      );
      if (!response.ok) throw new Error("Failed to fetch sessions");
      const data = await response.json();
      setSessions(data.interviews || []);
    } catch (err) {
      setError(err.message);
    }
  }, []);

  // Fetch alerts for selected session
  const fetchSessionAlerts = useCallback(async (sessionId) => {
    try {
      const response = await fetch(
        `${import.meta.env.VITE_API_URL || "http://localhost:8000"}/api/proctoring/alerts/${sessionId}?limit=200`
      );
      if (!response.ok) throw new Error("Failed to fetch alerts");
      const data = await response.json();
      setAlerts(data.events || []);
    } catch (err) {
      setError(err.message);
    }
  }, []);

  // Fetch proctoring stats
  const fetchStats = useCallback(async () => {
    try {
      const response = await fetch(
        `${import.meta.env.VITE_API_URL || "http://localhost:8000"}/api/proctoring/health`
      );
      if (!response.ok) throw new Error("Failed to fetch stats");
      const data = await response.json();
      setStats(data);
    } catch (err) {
      console.error("Failed to fetch stats:", err);
    }
  }, []);

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await Promise.all([fetchSessions(), fetchStats()]);
      setLoading(false);
    };
    loadData();
  }, [fetchSessions, fetchStats]);

  useEffect(() => {
    if (selectedSession) {
      fetchSessionAlerts(selectedSession.id);
    }
  }, [selectedSession, fetchSessionAlerts]);

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const getViolationSeverity = (count) => {
    if (count >= 3) return { label: "Critical", color: "text-red-400" };
    if (count === 2) return { label: "High", color: "text-orange-400" };
    if (count === 1) return { label: "Medium", color: "text-yellow-400" };
    return { label: "Low", color: "text-green-400" };
  };

  // Overview Tab
  const renderOverview = () => (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
      <div className="glass-panel rounded-2xl p-6">
        <div className="text-slate-400 text-sm mb-1">Total Sessions</div>
        <div className="text-3xl font-bold text-white">{sessions.length}</div>
        <div className="text-slate-500 text-xs mt-2">All time interviews</div>
      </div>
      
      <div className="glass-panel rounded-2xl p-6">
        <div className="text-slate-400 text-sm mb-1">Active Proctoring</div>
        <div className="text-3xl font-bold text-green-400">
          {stats?.status === "ok" ? "Online" : "Offline"}
        </div>
        <div className="text-slate-500 text-xs mt-2">
          YOLO: {stats?.models?.yolo_available ? "✓" : "✗"} | 
          Face: {stats?.models?.face_pose_available ? "✓" : "✗"}
        </div>
      </div>
      
      <div className="glass-panel rounded-2xl p-6">
        <div className="text-slate-400 text-sm mb-1">Incidents Today</div>
        <div className="text-3xl font-bold text-red-400">
          {alerts.filter(a => 
            new Date(a.timestamp).toDateString() === new Date().toDateString()
          ).length}
        </div>
        <div className="text-slate-500 text-xs mt-2">Security alerts</div>
      </div>
      
      <div className="glass-panel rounded-2xl p-6">
        <div className="text-slate-400 text-sm mb-1">Terminated</div>
        <div className="text-3xl font-bold text-orange-400">
          {sessions.filter(s => s.terminated).length}
        </div>
        <div className="text-slate-500 text-xs mt-2">Due to violations</div>
      </div>
    </div>
  );

  // Sessions Tab
  const renderSessions = () => (
    <div className="glass-panel rounded-2xl overflow-hidden">
      <div className="p-4 border-b border-slate-700">
        <h3 className="text-lg font-semibold text-white">Interview Sessions</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-slate-800/50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-slate-400">Candidate</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-slate-400">Start Time</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-slate-400">Status</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-slate-400">Violations</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-slate-400">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-700">
            {sessions.map((session) => {
              const severity = getViolationSeverity(session.violation_count || 0);
              return (
                <tr 
                  key={session.id} 
                  className="hover:bg-slate-800/30 cursor-pointer"
                  onClick={() => setSelectedSession(session)}
                >
                  <td className="px-4 py-3 text-white">{session.candidate_name || "Anonymous"}</td>
                  <td className="px-4 py-3 text-slate-400">{formatDate(session.created_at)}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-1 rounded-full text-xs ${
                      session.completed ? "bg-green-500/20 text-green-400" :
                      session.terminated ? "bg-red-500/20 text-red-400" :
                      "bg-blue-500/20 text-blue-400"
                    }`}>
                      {session.completed ? "Completed" : session.terminated ? "Terminated" : "In Progress"}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`font-semibold ${severity.color}`}>
                      {session.violation_count || 0} - {severity.label}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <button className="text-cyan-400 hover:text-cyan-300 text-sm">
                      View Details →
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );

  // Incidents Tab (Security Logs)
  const renderIncidents = () => (
    <div className="space-y-4">
      {alerts.length === 0 ? (
        <div className="glass-panel rounded-2xl p-8 text-center">
          <div className="text-6xl mb-4">🛡️</div>
          <h3 className="text-xl font-semibold text-white mb-2">No Security Incidents</h3>
          <p className="text-slate-400">No proctoring violations detected for this session.</p>
        </div>
      ) : (
        alerts.map((alert, index) => (
          <div 
            key={alert.id || index}
            className={`glass-panel rounded-xl p-4 border-l-4 ${
              WARNING_COLORS[alert.rule] || WARNING_COLORS.default
            }`}
          >
            <div className="flex items-start gap-4">
              <div className="text-3xl">
                {WARNING_ICONS[alert.rule] || WARNING_ICONS.default}
              </div>
              <div className="flex-1">
                <div className="flex items-center justify-between mb-1">
                  <h4 className="font-semibold text-white capitalize">
                    {alert.rule.replace(/_/g, " ")}
                  </h4>
                  <span className="text-xs text-slate-400">
                    {formatDate(alert.timestamp)}
                  </span>
                </div>
                <p className="text-slate-300 mb-2">{alert.message}</p>
                
                {/* Details */}
                {alert.details && Object.keys(alert.details).length > 0 && (
                  <div className="mt-2 p-3 bg-slate-900/50 rounded-lg">
                    <div className="text-xs text-slate-400 mb-2">Detection Details:</div>
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      {Object.entries(alert.details).slice(0, 6).map(([key, value]) => (
                        <div key={key} className="flex justify-between">
                          <span className="text-slate-500 capitalize">{key.replace(/_/g, " ")}:</span>
                          <span className="text-slate-300 font-mono">
                            {typeof value === "number" ? value.toFixed(2) : String(value)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                
                {/* Warning Count */}
                {alert.details?.warning_count && (
                  <div className="mt-2 flex items-center gap-2">
                    <span className="text-xs text-slate-400">Strike:</span>
                    <div className="flex gap-1">
                      {[1, 2, 3].map((strike) => (
                        <div
                          key={strike}
                          className={`w-5 h-5 rounded-full flex items-center justify-center text-xs ${
                            strike <= alert.details.warning_count
                              ? "bg-red-500 text-white"
                              : "bg-slate-700 text-slate-500"
                          }`}
                        >
                          {strike}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        ))
      )}
    </div>
  );

  // Analytics Tab
  const renderAnalytics = () => {
    const ruleCounts = alerts.reduce((acc, alert) => {
      acc[alert.rule] = (acc[alert.rule] || 0) + 1;
      return acc;
    }, {});

    const sortedRules = Object.entries(ruleCounts).sort((a, b) => b[1] - a[1]);

    return (
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="glass-panel rounded-2xl p-6">
          <h3 className="text-lg font-semibold text-white mb-4">Violation Types</h3>
          <div className="space-y-3">
            {sortedRules.length === 0 ? (
              <p className="text-slate-400 text-center py-8">No data available</p>
            ) : (
              sortedRules.map(([rule, count]) => (
                <div key={rule} className="flex items-center gap-3">
                  <div className="text-xl">{WARNING_ICONS[rule] || WARNING_ICONS.default}</div>
                  <div className="flex-1">
                    <div className="flex justify-between mb-1">
                      <span className="text-slate-300 capitalize">{rule.replace(/_/g, " ")}</span>
                      <span className="text-white font-semibold">{count}</span>
                    </div>
                    <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-gradient-to-r from-cyan-500 to-blue-500"
                        style={{ width: `${(count / sortedRules[0][1]) * 100}%` }}
                      />
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="glass-panel rounded-2xl p-6">
          <h3 className="text-lg font-semibold text-white mb-4">System Health</h3>
          <div className="space-y-4">
            <div className="flex items-center justify-between p-3 bg-slate-800/50 rounded-lg">
              <span className="text-slate-300">YOLO Object Detection</span>
              <span className={`px-2 py-1 rounded text-xs ${
                stats?.models?.yolo_available 
                  ? "bg-green-500/20 text-green-400" 
                  : "bg-red-500/20 text-red-400"
              }`}>
                {stats?.models?.yolo_available ? "Operational" : "Offline"}
              </span>
            </div>
            <div className="flex items-center justify-between p-3 bg-slate-800/50 rounded-lg">
              <span className="text-slate-300">Face/Pose Detection</span>
              <span className={`px-2 py-1 rounded text-xs ${
                stats?.models?.face_pose_available 
                  ? "bg-green-500/20 text-green-400" 
                  : "bg-red-500/20 text-red-400"
              }`}>
                {stats?.models?.face_pose_available ? "Operational" : "Offline"}
              </span>
            </div>
            <div className="flex items-center justify-between p-3 bg-slate-800/50 rounded-lg">
              <span className="text-slate-300">Alert Log Storage</span>
              <span className="px-2 py-1 rounded text-xs bg-blue-500/20 text-blue-400">
                {stats?.alerts?.total_alerts || 0} alerts stored
              </span>
            </div>
            <div className="flex items-center justify-between p-3 bg-slate-800/50 rounded-lg">
              <span className="text-slate-300">Last Updated</span>
              <span className="text-slate-400 text-sm">
                {stats?.timestamp ? formatDate(stats.timestamp) : "N/A"}
              </span>
            </div>
          </div>
        </div>
      </div>
    );
  };

  if (loading) {
    return (
      <Shell>
        <div className="flex items-center justify-center h-64">
          <div className="text-cyan-400 animate-pulse">Loading dashboard...</div>
        </div>
      </Shell>
    );
  }

  return (
    <Shell>
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold text-white">Admin Dashboard</h1>
            <p className="text-slate-400">Proctoring & Security Monitoring</p>
          </div>
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${stats?.status === "ok" ? "bg-green-500 animate-pulse" : "bg-red-500"}`} />
            <span className="text-sm text-slate-400">
              {stats?.status === "ok" ? "System Online" : "System Offline"}
            </span>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="flex gap-2 mb-6">
          {["overview", "sessions", "incidents", "analytics"].map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-2 rounded-lg font-medium text-sm transition-colors ${
                activeTab === tab
                  ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/30"
                  : "text-slate-400 hover:text-white hover:bg-slate-800"
              }`}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </div>

        {/* Error Display */}
        {error && (
          <div className="mb-6 p-4 bg-red-500/20 border border-red-500 rounded-xl text-red-200">
            {error}
          </div>
        )}

        {/* Tab Content */}
        {activeTab === "overview" && renderOverview()}
        {activeTab === "sessions" && renderSessions()}
        {activeTab === "incidents" && renderIncidents()}
        {activeTab === "analytics" && renderAnalytics()}

        {/* Session Detail Modal */}
        {selectedSession && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div 
              className="absolute inset-0 bg-black/70 backdrop-blur-sm"
              onClick={() => setSelectedSession(null)}
            />
            <div className="relative w-full max-w-4xl max-h-[80vh] overflow-y-auto glass-panel rounded-2xl p-6">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-xl font-bold text-white">
                  Session Details: {selectedSession.candidate_name || "Anonymous"}
                </h2>
                <button 
                  onClick={() => setSelectedSession(null)}
                  className="text-slate-400 hover:text-white"
                >
                  ✕
                </button>
              </div>
              
              {/* Session Info */}
              <div className="grid grid-cols-2 gap-4 mb-6">
                <div className="bg-slate-800/50 rounded-lg p-3">
                  <div className="text-xs text-slate-400">Session ID</div>
                  <div className="text-white font-mono text-sm">{selectedSession.id}</div>
                </div>
                <div className="bg-slate-800/50 rounded-lg p-3">
                  <div className="text-xs text-slate-400">Started</div>
                  <div className="text-white">{formatDate(selectedSession.created_at)}</div>
                </div>
                <div className="bg-slate-800/50 rounded-lg p-3">
                  <div className="text-xs text-slate-400">Status</div>
                  <div className={`font-semibold ${
                    selectedSession.terminated ? "text-red-400" : 
                    selectedSession.completed ? "text-green-400" : "text-blue-400"
                  }`}>
                    {selectedSession.terminated ? "Terminated" : 
                     selectedSession.completed ? "Completed" : "In Progress"}
                  </div>
                </div>
                <div className="bg-slate-800/50 rounded-lg p-3">
                  <div className="text-xs text-slate-400">Violations</div>
                  <div className={`font-semibold ${getViolationSeverity(selectedSession.violation_count).color}`}>
                    {selectedSession.violation_count || 0} detected
                  </div>
                </div>
              </div>

              {/* Alert Timeline */}
              <h3 className="text-lg font-semibold text-white mb-4">Security Alert Timeline</h3>
              {renderIncidents()}
            </div>
          </div>
        )}
      </div>
    </Shell>
  );
}
