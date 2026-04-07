import { Outlet, Link, useLocation } from "react-router";
import {
  Upload,
  FileText,
  FolderKanban,
  Bot,
  BarChart3,
  FileSpreadsheet,
  Shield,
  Settings,
  Search,
  Circle,
} from "lucide-react";
import { Avatar, AvatarFallback } from "./ui/avatar";
import { Badge } from "./ui/badge";
import { Input } from "./ui/input";

const navigation = [
  { name: "Upload Dataset", href: "/app/upload", icon: Upload, comingSoon: false },
  { name: "Schema Profile", href: "/app/schema", icon: FileText, comingSoon: false },
  { name: "Projects", href: "/app/projects", icon: FolderKanban, comingSoon: false },
  { name: "Agents", href: "/app/agents", icon: Bot, comingSoon: false },
  { name: "Reports", href: "/app/reports", icon: BarChart3, comingSoon: true },
  { name: "Power BI Exports", href: "/app/powerbi", icon: FileSpreadsheet, comingSoon: true },
  { name: "Admin", href: "/app/admin", icon: Shield, comingSoon: false },
  { name: "Settings", href: "/app/settings", icon: Settings, comingSoon: true },
];

export function AppLayout() {
  const location = useLocation();
  const currentPath = location.pathname === "/app" ? "/app/upload" : location.pathname;
  const currentPage = navigation.find((item) => currentPath.startsWith(item.href));

  return (
    <div className="dark min-h-screen flex bg-background">
      {/* Sidebar */}
      <aside className="w-64 border-r border-border bg-sidebar flex flex-col">
        <div className="p-6 border-b border-sidebar-border">
          <Link to="/" className="flex items-center gap-3 hover:opacity-80 transition-opacity">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
              <span className="text-white text-xl font-bold">DA</span>
            </div>
            <div>
              <h1 className="text-sidebar-foreground">DataAlchemy</h1>
              <p className="text-xs text-muted-foreground">AI Data Workflows</p>
            </div>
          </Link>
        </div>

        <nav className="flex-1 p-4 space-y-1">
          {navigation.map((item) => {
            const Icon = item.icon;
            const isActive = currentPath.startsWith(item.href);

            return (
              <Link
                key={item.name}
                to={item.href}
                className={`
                  flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors group relative
                  ${isActive
                    ? "bg-sidebar-accent text-sidebar-accent-foreground"
                    : "text-sidebar-foreground hover:bg-sidebar-accent/50 hover:text-sidebar-accent-foreground"
                  }
                  ${item.comingSoon ? "opacity-60" : ""}
                `}
              >
                <Icon className="w-5 h-5 flex-shrink-0" />
                <span className="flex-1">{item.name}</span>
                {item.comingSoon && (
                  <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
                    Soon
                  </Badge>
                )}
              </Link>
            );
          })}
        </nav>

        <div className="p-4 border-t border-sidebar-border">
          <div className="flex items-center gap-2 text-xs">
            <Circle className="w-2 h-2 fill-green-500 text-green-500" />
            <span className="text-muted-foreground">Backend Online</span>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col min-h-screen">
        {/* Header */}
        <header className="h-16 border-b border-border bg-card px-6 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <h2 className="text-card-foreground">{currentPage?.name || "DataAlchemy"}</h2>
          </div>

          <div className="flex items-center gap-4">
            <div className="relative w-80">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="Quick command..."
                className="pl-9 bg-muted/50 border-muted"
              />
            </div>

            <Badge variant="outline" className="gap-1.5">
              <Circle className="w-2 h-2 fill-green-500 text-green-500" />
              Docker Agent Connected
            </Badge>

            <Avatar className="w-9 h-9">
              <AvatarFallback className="bg-gradient-to-br from-blue-500 to-purple-600 text-white">
                JD
              </AvatarFallback>
            </Avatar>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
