import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { DEFAULT_WORKSPACE_PATH } from '@/lib/dashboard-nav';
import { AuthProvider } from '@/components/AuthProvider';
import { AppLayout } from '@/components/layout/AppLayout';
import ProtectedRoute from '@/components/ProtectedRoute';
import { Toaster } from '@/components/ui/toaster';
import LoginPage from '@/pages/login';
import { DashboardNotFoundPage } from '@/pages/DashboardNotFoundPage';
import PricingPage from '@/pages/pricing';
import ProductResearchPage from '@/pages/product-research';
import PublishTaskPage from '@/pages/publish-task';
import TaskBoardPage from '@/pages/task-board';
import TaskDetailPage from '@/pages/TaskDetailPage';
import WorkspaceSettingsPage from '@/pages/workspace-settings';

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Toaster />
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<ProtectedRoute />}>
            <Route element={<AppLayout />}>
              <Route path="/" element={<Navigate to={DEFAULT_WORKSPACE_PATH} replace />} />
              <Route path="/pricing" element={<PricingPage />} />
              <Route path="/workspace-settings" element={<WorkspaceSettingsPage />} />
              <Route path="/publish-task" element={<PublishTaskPage />} />
              <Route path="/product-research" element={<ProductResearchPage />} />
              <Route path="/product-research/proposals/:proposalId" element={<ProductResearchPage />} />
              <Route path="/product-research/features" element={<ProductResearchPage />} />
              <Route
                path="/product-research/features/:featureId"
                element={<Navigate to="/product-research/features" replace />}
              />
              <Route path="/task-board" element={<TaskBoardPage />} />
              <Route path="/workspace" element={<Navigate to={DEFAULT_WORKSPACE_PATH} replace />} />
              <Route
                path="/workspace/workspace-settings"
                element={<Navigate to="/workspace-settings" replace />}
              />
              <Route path="/workspace/publish-task" element={<Navigate to="/publish-task" replace />} />
              <Route
                path="/workspace/product-research"
                element={<Navigate to="/product-research" replace />}
              />
              <Route
                path="/workspace/product-research/proposals/:proposalId"
                element={<Navigate to="/product-research" replace />}
              />
              <Route
                path="/workspace/product-research/features"
                element={<Navigate to="/product-research/features" replace />}
              />
              <Route
                path="/workspace/product-research/features/:featureId"
                element={<Navigate to="/product-research/features" replace />}
              />
              <Route path="/workspace/task-board" element={<Navigate to="/task-board" replace />} />
              <Route path="/overview" element={<Navigate to={DEFAULT_WORKSPACE_PATH} replace />} />
              <Route
                path="/overview/:projectId"
                element={<Navigate to={DEFAULT_WORKSPACE_PATH} replace />}
              />
              <Route path="/task/:taskId" element={<TaskDetailPage />} />
              <Route path="*" element={<DashboardNotFoundPage />} />
            </Route>
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
