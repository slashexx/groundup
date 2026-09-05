import { useState } from "react";
import PageBoundary from './components/PageBoundary';
import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import CreateProjectPage from "./pages/CreateProjectPage";
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
import { CadastreProvider } from "./data/useCadastre";
import { setProjectPath } from "./data/cadastreApi";

export default function App() {
  const location = useLocation();
  const [selectedProject, setSelectedProject] = useState(null);
  // One operator, no sign-in. Everything from upload through approval to export happens
  // as a single account, so an auth gate in front of it is ceremony with nothing behind
  // it. Who decided what is recorded by the sidecar in `review.decided_by`, not here.
  const user = { name: 'Operator', role: 'GIS Operator', initials: 'OP' };

  // Creating a project is the only way in. There is no list of existing projects to
  // choose from, because a project this app did not build is one whose numbers came from
  // nowhere — and a dashboard of invented figures that looks authoritative is the exact
  // failure this system exists to prevent.
  if (!selectedProject) {
    return (
      <PageBoundary><CreateProjectPage
        onCreated={(project) => {
          // Point every later call at the project that was just built, before any screen
          // mounts and asks for it.
          setProjectPath(project.db_path);
          setSelectedProject(project);
        }}
      /></PageBoundary>
    );
  }

  // One document for the whole session: the shell and the page it frames must never
  // disagree about whether they are showing the real project.
  return (
    <CadastreProvider>
    <AppShell project={selectedProject} user={user} onChangeProject={() => setSelectedProject(null)}>
      {/* Keyed on the path so a failure on one screen clears when you leave it, rather
          than following you to the next. */}
      <PageBoundary key={location.pathname}>
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
      </PageBoundary>
    </AppShell>
    </CadastreProvider>
  );
}
