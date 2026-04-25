import { createBrowserRouter } from "react-router";
import { AppLayout } from "./components/AppLayout";
import { RequireAdmin } from "./components/RequireAdmin";
import { RequireAuth } from "./components/RequireAuth";
import { LandingPage } from "./pages/LandingPage";
import { LoginPage } from "./pages/LoginPage";
import { UploadDatasetPage } from "./pages/UploadDatasetPage";
import { SchemaProfilePage } from "./pages/SchemaProfilePage";
import { ProjectsPage } from "./pages/ProjectsPage";
import { ComingSoonPage } from "./pages/ComingSoonPage";
import { AdminPage } from "./pages/AdminPage";
import { AgentsPage } from "./pages/AgentsPage";
import { ReportsPage } from "./pages/ReportsPage";

export const router = createBrowserRouter([
  {
    path: "/",
    Component: LandingPage,
  },
  {
    path: "/login",
    Component: LoginPage,
  },
  {
    Component: RequireAuth,
    children: [
      {
        path: "/app",
        Component: AppLayout,
        children: [
          { index: true, Component: UploadDatasetPage },
          { path: "upload", Component: UploadDatasetPage },
          { path: "schema", Component: SchemaProfilePage },
          { path: "projects", Component: ProjectsPage },
          { path: "agents", Component: AgentsPage },
          { path: "reports", Component: ReportsPage },
          {
            path: "powerbi",
            element: <ComingSoonPage
              title="Power BI Exports"
              description="Power BI-compatible exports will be added in the reporting milestone. Seamlessly push your processed datasets to Power BI for enterprise visualization and business intelligence."
            />
          },
          {
            Component: RequireAdmin,
            children: [{ path: "admin", Component: AdminPage }],
          },
          {
            path: "settings",
            element: <ComingSoonPage
              title="Settings"
              description="Comprehensive settings and configuration options will be available soon. Manage user preferences, API keys, integrations, and system settings."
            />
          },
        ],
      },
    ],
  },
]);
