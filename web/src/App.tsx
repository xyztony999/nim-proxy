import { Navigate, Route, Routes } from "react-router-dom";
import { getToken } from "./api/client";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import UpstreamKeys from "./pages/UpstreamKeys";
import ClientKeys from "./pages/ClientKeys";
import Usage from "./pages/Usage";
import RequestLogs from "./pages/RequestLogs";
import Config from "./pages/Config";

function RequireAuth({ children }: { children: React.ReactNode }) {
  if (!getToken()) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route path="/" element={<Dashboard />} />
        <Route path="/upstream-keys" element={<UpstreamKeys />} />
        <Route path="/client-keys" element={<ClientKeys />} />
        <Route path="/usage" element={<Usage />} />
        <Route path="/request-logs" element={<RequestLogs />} />
        <Route path="/config" element={<Config />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
