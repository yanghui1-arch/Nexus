import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { DEFAULT_OVERVIEW_PATH, DEFAULT_WORKSPACE_PATH } from '@/lib/dashboard-nav';
import LogPage from './pages/LogPage';
import TaskDetailPage from './pages/TaskDetailPage';
import WorkspacePage from './pages/WorkspacePage';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to={DEFAULT_WORKSPACE_PATH} replace />} />
        <Route
          path="/workspace"
          element={<Navigate to={DEFAULT_WORKSPACE_PATH} replace />}
        />
        <Route path="/workspace/:section" element={<WorkspacePage />} />

        <Route path="/overview" element={<Navigate to={DEFAULT_OVERVIEW_PATH} replace />} />
        <Route path="/overview/:projectId" element={<LogPage />} />

        <Route path="/task/:taskId" element={<TaskDetailPage />} />
        <Route path="*" element={<Navigate to={DEFAULT_WORKSPACE_PATH} replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
