import { useState } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import LoginPage from "./pages/LoginPage";
import ProjectSelectPage from "./pages/ProjectSelectPage";
import AppShell from "./components/layout/AppShell";
import DashboardPage from "./pages/DashboardPage";
import MapPage from "./pages/MapPage";
import UploadDataPage from "./pages/UploadDataPage";
import Create3DUnitPage from "./pages/Create3DUnitPage";
import AIToolsPage from "./pages/AIToolsPage";
import ErrorCheckPage from "./pages/ErrorCheckPage";
import ReviewPage from "./pages/ReviewPage";
import SearchPage from "./pages/SearchPage";
import ExportPage from "./pages/ExportPage";
import HistoryPage from "./pages/HistoryPage";
import SettingsPage from "./pages/SettingsPage";
import { mockProjects, mockUser } from "./data/mockData";

export default function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [selectedProject, setSelectedProject] = useState(null);
  const [user, setUser] = useState(mockUser);

  if (!isLoggedIn) {
    return <LoginPage onLogin={(role) => {
      setUser({ ...mockUser, role });
      setIsLoggedIn(true);
    }} />;
  }

  if (!selectedProject) {
    return (
      <ProjectSelectPage
        projects={mockProjects}
        user={user}
        onSelectProject={(project) => setSelectedProject(project)}
        onLogout={() => setIsLoggedIn(false)}
      />
    );
  }

  return (
    <AppShell project={selectedProject} user={user} onChangeProject={() => setSelectedProject(null)} onLogout={() => { setIsLoggedIn(false); setSelectedProject(null); }}>
      <Routes>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<DashboardPage project={selectedProject} />} />
        <Route path="/map-2d" element={<MapPage project={selectedProject} view="2d" />} />
        <Route path="/map-3d" element={<MapPage project={selectedProject} view="3d" />} />
        <Route path="/upload" element={<UploadDataPage />} />
        <Route path="/create-3d" element={<Create3DUnitPage />} />
        <Route path="/ai-tools" element={<AIToolsPage />} />
        <Route path="/errors" element={<ErrorCheckPage />} />
        <Route path="/review" element={<ReviewPage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/export" element={<ExportPage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/settings" element={<SettingsPage project={selectedProject} />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </AppShell>
  );
}
