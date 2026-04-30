import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { DEFAULT_OVERVIEW_PATH, DEFAULT_WORKSPACE_PATH } from '@/lib/dashboard-nav';
import { AppLayout } from '@/components/layout/AppLayout';
import { Toaster } from '@/components/ui/toaster';
import LogPage from './pages/LogPage';
import { NexusReviewPage } from './pages/nexus-review';
import TaskDetailPage from './pages/TaskDetailPage';
import WorkspacePage from './pages/workspace';

function App() {
  return (
    <BrowserRouter>
      <Toaster />
      <Routes>
        <Route
          path="/workspace/code-review/nexus/tasks/:taskId/pull-requests/:virtualPrId"
          element={<NexusReviewPage mode="pull-request" />}
        />
        <Route element={<AppLayout />}>
          <Route path="/" element={<Navigate to={DEFAULT_WORKSPACE_PATH} replace />} />
          <Route
            path="/workspace"
            element={<Navigate to={DEFAULT_WORKSPACE_PATH} replace />}
          />
          <Route
            path="/workspace/code-review"
            element={<Navigate to="/workspace/code-review/nexus" replace />}
          />
          <Route
            path="/workspace/code-review/nexus"
            element={<NexusReviewPage mode="queue" />}
          />
          <Route
            path="/workspace/code-review/nexus/tasks/:taskId"
            element={<NexusReviewPage mode="task" />}
          />
          <Route path="/workspace/:section" element={<WorkspacePage />} />

          <Route path="/overview" element={<Navigate to={DEFAULT_OVERVIEW_PATH} replace />} />
          <Route path="/overview/:projectId" element={<LogPage />} />

          <Route path="/task/:taskId" element={<TaskDetailPage />} />
          <Route path="*" element={<Navigate to={DEFAULT_WORKSPACE_PATH} replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
