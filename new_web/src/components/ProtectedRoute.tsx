import { Navigate, Outlet, useLocation } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { useAuth } from "@/components/AuthProvider";

export default function ProtectedRoute() {
  const location = useLocation();
  const { status } = useAuth();

  if (status === "checking") {
    return (
      <main className="flex min-h-screen items-center justify-center bg-background text-muted-foreground">
        <div
          className="flex items-center gap-2 text-sm"
          role="status"
          aria-live="polite"
        >
          <Loader2 className="size-4 animate-spin" aria-hidden="true" />
          Verifying login status...
        </div>
      </main>
    );
  }

  if (status === "unauthenticated") {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return <Outlet />;
}
