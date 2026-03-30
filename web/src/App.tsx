import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import LogPage from './pages/LogPage';
import TaskDetailPage from './pages/TaskDetailPage';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LogPage />} />
        <Route path="/task/:taskId" element={<TaskDetailPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
