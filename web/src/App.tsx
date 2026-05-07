import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { DEFAULT_WORKSPACE_PATH } from '@/lib/dashboard-nav';
import { AppLayout } from '@/components/layout/AppLayout';
import { Toaster } from '@/components/ui/toaster';
import { NexusReviewPage } from './pages/nexus-review';
import ProcessTrackingPage from './pages/process-tracking';
import PublishTaskPage from './pages/publish-task';
import TaskBoardPage from './pages/task-board';
import TaskDetailPage from './pages/TaskDetailPage';

function App() {
  return (
    <BrowserRouter>
      <Toaster />
      <Routes>
        <Route
          path="/workspace/code-review/nexus/tasks/:taskId/pull-requests/:virtualPrId"
          element={<NexusReviewPage mode="pull-request" />}
        />
        <Route
          path="/code-review/nexus/tasks/:taskId/pull-requests/:virtualPrId"
          element={<NexusReviewPage mode="pull-request" />}
        />
        <Route element={<AppLayout />}>
          <Route path="/" element={<Navigate to={DEFAULT_WORKSPACE_PATH} replace />} />
          <Route path="/publish-task" element={<PublishTaskPage />} />
          <Route path="/process-tracking" element={<ProcessTrackingPage />} />
          <Route path="/task-board" element={<TaskBoardPage />} />
          <Route path="/code-review" element={<Navigate to="/code-review/nexus" replace />} />
          <Route
            path="/code-review/nexus"
            element={<NexusReviewPage mode="queue" />}
          />
          <Route
            path="/code-review/nexus/tasks/:taskId"
            element={<NexusReviewPage mode="task" />}
          />
          <Route path="/workspace" element={<Navigate to={DEFAULT_WORKSPACE_PATH} replace />} />
          <Route path="/workspace/publish-task" element={<Navigate to="/publish-task" replace />} />
          <Route
            path="/workspace/process-tracking"
            element={<Navigate to="/process-tracking" replace />}
          />
          <Route path="/workspace/task-board" element={<Navigate to="/task-board" replace />} />
          <Route path="/workspace/code-review" element={<Navigate to="/code-review" replace />} />
          <Route
            path="/workspace/code-review/nexus"
            element={<NexusReviewPage mode="queue" />}
          />
          <Route
            path="/workspace/code-review/nexus/tasks/:taskId"
            element={<NexusReviewPage mode="task" />}
          />
          <Route path="/overview" element={<Navigate to={DEFAULT_WORKSPACE_PATH} replace />} />
          <Route
            path="/overview/:projectId"
            element={<Navigate to={DEFAULT_WORKSPACE_PATH} replace />}
          />

          <Route path="/task/:taskId" element={<TaskDetailPage />} />
          <Route path="*" element={<Navigate to={DEFAULT_WORKSPACE_PATH} replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
