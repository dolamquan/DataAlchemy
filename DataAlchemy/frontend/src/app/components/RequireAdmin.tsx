import { useEffect, useState } from "react";
import { Navigate, Outlet, useLocation } from "react-router";
import { fetchAdminAccess } from "../lib/uploadsApi";

export function RequireAdmin() {
  const location = useLocation();
  const [loading, setLoading] = useState(true);
  const [isAdmin, setIsAdmin] = useState(false);

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const access = await fetchAdminAccess();
        if (!active) return;
        setIsAdmin(access.is_admin);
      } catch {
        if (!active) return;
        setIsAdmin(false);
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  if (loading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center text-muted-foreground">
        Checking admin access...
      </div>
    );
  }

  if (!isAdmin) {
    return <Navigate to="/app/upload" replace state={{ from: location }} />;
  }

  return <Outlet />;
}
