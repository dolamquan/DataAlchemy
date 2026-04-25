import { Navigate, Outlet, useLocation } from "react-router";
import { useAuth } from "../lib/auth";

export function RequireAuth() {
  const { user, loading, configured } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background text-foreground">
        <div className="space-y-2 text-center">
          <p className="text-lg font-medium">Checking session…</p>
          <p className="text-sm text-muted-foreground">Preparing your secure workspace.</p>
        </div>
      </div>
    );
  }

  if (!configured) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background px-6 text-foreground">
        <div className="max-w-xl rounded-2xl border border-border bg-card p-8 text-center shadow-sm">
          <p className="text-lg font-medium">Firebase auth is not configured.</p>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            Add the `VITE_FIREBASE_*` environment variables to the frontend before accessing the app.
          </p>
        </div>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return <Outlet />;
}
