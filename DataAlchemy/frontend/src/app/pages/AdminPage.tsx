import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Download,
  FileText,
  Shield,
  Upload,
  Users,
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "../components/ui/tabs";
import {
  fetchAdminOverview,
  type AdminActivityOverview,
  type AdminOverviewResponse,
  type AdminUserOverview,
} from "../lib/uploadsApi";

function formatDate(value?: string | null) {
  if (!value) return "Never";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Unknown";
  return date.toLocaleString();
}

function activityBadge(status: string) {
  if (status === "completed") return "border-green-500/40 text-green-400";
  if (status === "failed") return "border-red-500/40 text-red-400";
  if (status === "started") return "border-blue-500/40 text-blue-400";
  return "border-slate-500/40 text-slate-300";
}

export function AdminPage() {
  const [overview, setOverview] = useState<AdminOverviewResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [userQuery, setUserQuery] = useState("");
  const [activityQuery, setActivityQuery] = useState("");

  useEffect(() => {
    let active = true;
    void (async () => {
      setLoading(true);
      setError(null);
      try {
        const next = await fetchAdminOverview();
        if (active) {
          setOverview(next);
        }
      } catch (nextError) {
        if (active) {
          setError(nextError instanceof Error ? nextError.message : "Failed to load admin overview");
        }
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

  const users = useMemo(() => {
    const allUsers = overview?.users ?? [];
    const query = userQuery.trim().toLowerCase();
    if (!query) return allUsers;
    return allUsers.filter((user) =>
      [user.email, user.display_name, user.uid].some((value) => (value ?? "").toLowerCase().includes(query)),
    );
  }, [overview?.users, userQuery]);

  const activities = useMemo(() => {
    const allActivities = overview?.activities ?? [];
    const query = activityQuery.trim().toLowerCase();
    if (!query) return allActivities;
    return allActivities.filter((activity) =>
      [
        activity.owner_email,
        activity.owner_uid,
        activity.activity_type,
        activity.resource_name,
        activity.resource_id,
      ].some((value) => (value ?? "").toLowerCase().includes(query)),
    );
  }, [activityQuery, overview?.activities]);

  const summaryCards = [
    {
      label: "Total Users",
      value: overview?.totals.total_users ?? 0,
      icon: Users,
      accent: "text-blue-400",
    },
    {
      label: "Active Users",
      value: overview?.totals.active_users ?? 0,
      icon: Shield,
      accent: "text-cyan-400",
    },
    {
      label: "Uploads",
      value: overview?.totals.total_uploads ?? 0,
      icon: Upload,
      accent: "text-violet-400",
    },
    {
      label: "Reports",
      value: overview?.totals.total_reports ?? 0,
      icon: FileText,
      accent: "text-amber-400",
    },
    {
      label: "Activities",
      value: overview?.totals.total_activities ?? 0,
      icon: Activity,
      accent: "text-green-400",
    },
    {
      label: "Failed Actions",
      value: overview?.totals.failed_activities ?? 0,
      icon: AlertTriangle,
      accent: "text-red-400",
    },
  ];

  return (
    <div className="p-8 max-w-[1600px] mx-auto space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-foreground mb-2">Admin Dashboard</h1>
          <p className="text-muted-foreground">
            Review current Firebase users, account-level activity, and platform usage across the workspace.
          </p>
        </div>
        <Button variant="outline" className="gap-2" onClick={() => window.print()}>
          <Download className="w-4 h-4" />
          Export Snapshot
        </Button>
      </div>

      {error ? (
        <Card className="border-red-500/30 bg-red-500/5">
          <CardContent className="py-6 text-sm text-red-300">{error}</CardContent>
        </Card>
      ) : null}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3 xl:grid-cols-6">
        {summaryCards.map((card) => {
          const Icon = card.icon;
          return (
            <Card key={card.label}>
              <CardHeader className="pb-2">
                <CardDescription>{card.label}</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-3">
                  <Icon className={`h-5 w-5 ${card.accent}`} />
                  <div className="text-3xl text-foreground">{card.value.toLocaleString()}</div>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <Tabs defaultValue="users" className="space-y-6">
        <TabsList>
          <TabsTrigger value="users">Users</TabsTrigger>
          <TabsTrigger value="activities">Activities</TabsTrigger>
        </TabsList>

        <TabsContent value="users" className="space-y-4">
          <Card>
            <CardHeader className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <CardTitle>Current Users</CardTitle>
                <CardDescription>
                  Firebase accounts enriched with upload, report, and activity metrics from the application database.
                </CardDescription>
              </div>
              <Input
                value={userQuery}
                onChange={(event) => setUserQuery(event.target.value)}
                placeholder="Search by email, name, or uid..."
                className="max-w-sm"
              />
            </CardHeader>
            <CardContent>
              {loading ? (
                <p className="text-sm text-muted-foreground">Loading users...</p>
              ) : (
                <div className="rounded-lg border border-border overflow-hidden">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>User</TableHead>
                        <TableHead>UID</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Role</TableHead>
                        <TableHead>Uploads</TableHead>
                        <TableHead>Reports</TableHead>
                        <TableHead>Activities</TableHead>
                        <TableHead>Last Activity</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {users.map((user: AdminUserOverview) => (
                        <TableRow key={user.uid}>
                          <TableCell>
                            <div>
                              <p className="text-foreground">{user.display_name || "Unnamed user"}</p>
                              <p className="text-xs text-muted-foreground">{user.email || "No email available"}</p>
                            </div>
                          </TableCell>
                          <TableCell className="font-mono text-xs text-muted-foreground">{user.uid}</TableCell>
                          <TableCell>
                            <Badge variant="outline" className={user.status === "active" ? "border-green-500/40 text-green-400" : "border-slate-500/40 text-slate-300"}>
                              {user.status}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            <Badge variant="secondary">{user.is_admin ? "Admin" : "User"}</Badge>
                          </TableCell>
                          <TableCell>{user.upload_count}</TableCell>
                          <TableCell>{user.report_count}</TableCell>
                          <TableCell>{user.activity_count}</TableCell>
                          <TableCell>
                            <div className="text-sm">
                              <p>{formatDate(user.last_activity_at)}</p>
                              <p className="text-xs text-muted-foreground">
                                Last sign-in: {formatDate(user.last_sign_in_at)}
                              </p>
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                      {users.length === 0 ? (
                        <TableRow>
                          <TableCell colSpan={8} className="text-center text-muted-foreground">
                            No matching users found.
                          </TableCell>
                        </TableRow>
                      ) : null}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="activities" className="space-y-4">
          <Card>
            <CardHeader className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <CardTitle>Activity Feed</CardTitle>
                <CardDescription>
                  Recent upload, reporting, and supervisor actions captured by the backend audit log.
                </CardDescription>
              </div>
              <Input
                value={activityQuery}
                onChange={(event) => setActivityQuery(event.target.value)}
                placeholder="Search activity, resource, or user..."
                className="max-w-sm"
              />
            </CardHeader>
            <CardContent>
              {loading ? (
                <p className="text-sm text-muted-foreground">Loading activity...</p>
              ) : (
                <div className="space-y-3">
                  {activities.map((activity: AdminActivityOverview, index) => (
                    <div
                      key={`${activity.created_at}-${activity.owner_uid ?? "anon"}-${index}`}
                      className="rounded-2xl border border-border bg-card/40 px-4 py-4"
                    >
                      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <p className="text-sm font-medium text-foreground">{activity.activity_type}</p>
                            <Badge variant="outline" className={activityBadge(activity.status)}>
                              {activity.status}
                            </Badge>
                          </div>
                          <p className="text-sm text-muted-foreground">
                            {activity.owner_email || activity.owner_uid || "Unknown user"}
                          </p>
                          <p className="text-sm text-muted-foreground">
                            Resource: {activity.resource_name || activity.resource_id || "n/a"}
                          </p>
                          {activity.details && Object.keys(activity.details).length > 0 ? (
                            <p className="text-xs leading-6 text-muted-foreground">
                              {JSON.stringify(activity.details)}
                            </p>
                          ) : null}
                        </div>
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                          <Clock3 className="h-3.5 w-3.5" />
                          {formatDate(activity.created_at)}
                        </div>
                      </div>
                    </div>
                  ))}
                  {activities.length === 0 ? (
                    <div className="rounded-xl border border-border px-4 py-8 text-center text-sm text-muted-foreground">
                      No matching activities found.
                    </div>
                  ) : null}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>How Activity Is Counted</CardTitle>
              <CardDescription>
                Completed uploads, report actions, and supervisor interactions are logged by the backend and rolled into the user metrics above.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm text-muted-foreground">
              <div className="flex items-center gap-3">
                <CheckCircle2 className="h-4 w-4 text-green-400" />
                Successful actions increment completion totals and update the user&apos;s last activity time.
              </div>
              <div className="flex items-center gap-3">
                <AlertTriangle className="h-4 w-4 text-red-400" />
                Failed actions are preserved in the feed so admins can inspect errors without opening server logs.
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
