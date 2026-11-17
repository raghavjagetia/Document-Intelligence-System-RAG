import { lazy, Suspense, type ReactNode } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { Toaster } from "sonner";
import { useAuth } from "./hooks/useAuth";
import { useTheme } from "./hooks/useTheme";
import { AppLayout } from "./components/layout/AppLayout";
import { Logo } from "./components/Brand";

const AuthPage = lazy(() => import("./pages/AuthPage"));
const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const DocumentsPage = lazy(() => import("./pages/DocumentsPage"));
const ChatPage = lazy(() => import("./pages/ChatPage"));
const InsightsPage = lazy(() => import("./pages/InsightsPage"));
const EvaluationPage = lazy(() => import("./pages/EvaluationPage"));
const SettingsPage = lazy(() => import("./pages/SettingsPage"));
const AdminPage = lazy(() => import("./pages/AdminPage"));
const NotFoundPage = lazy(() => import("./pages/NotFoundPage"));

function FullScreenLoader() {
  return (
    <div className="flex h-[100dvh] items-center justify-center" role="status" aria-label="Loading">
      <div className="animate-pulse">
        <Logo />
      </div>
    </div>
  );
}

function PageLoader() {
  return (
    <div className="flex h-64 items-center justify-center" role="status" aria-label="Loading page">
      <div className="h-6 w-6 animate-spin rounded-full border-2 border-indigo-500/30 border-t-indigo-500" />
    </div>
  );
}

function Protected({ children }: { children: ReactNode }) {
  const { isAuthenticated, loading } = useAuth();
  const location = useLocation();
  if (loading) return <FullScreenLoader />;
  if (!isAuthenticated) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  return <>{children}</>;
}

function PublicOnly({ children }: { children: ReactNode }) {
  const { isAuthenticated, loading } = useAuth();
  if (loading) return <FullScreenLoader />;
  if (isAuthenticated) return <Navigate to="/" replace />;
  return <>{children}</>;
}

export default function App() {
  const { theme } = useTheme();
  return (
    <>
      <Suspense fallback={<FullScreenLoader />}>
        <Routes>
          <Route
            path="/login"
            element={
              <PublicOnly>
                <AuthPage mode="login" />
              </PublicOnly>
            }
          />
          <Route
            path="/register"
            element={
              <PublicOnly>
                <AuthPage mode="register" />
              </PublicOnly>
            }
          />
          <Route
            element={
              <Protected>
                <AppLayout />
              </Protected>
            }
          >
            <Route index element={<Lazy><DashboardPage /></Lazy>} />
            <Route path="documents" element={<Lazy><DocumentsPage /></Lazy>} />
            <Route path="chat/:conversationId?" element={<Lazy><ChatPage /></Lazy>} />
            <Route path="insights" element={<Lazy><InsightsPage /></Lazy>} />
            <Route path="evaluation" element={<Lazy><EvaluationPage /></Lazy>} />
            <Route path="settings" element={<Lazy><SettingsPage /></Lazy>} />
            <Route path="admin" element={<Lazy><AdminPage /></Lazy>} />
            <Route path="*" element={<Lazy><NotFoundPage /></Lazy>} />
          </Route>
        </Routes>
      </Suspense>
      <Toaster theme={theme} position="bottom-right" richColors closeButton toastOptions={{ className: "font-sans" }} />
    </>
  );
}

function Lazy({ children }: { children: ReactNode }) {
  return <Suspense fallback={<PageLoader />}>{children}</Suspense>;
}
