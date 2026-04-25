import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router";
import { Database, LockKeyhole, Mail, Sparkles } from "lucide-react";
import { FirebaseError } from "firebase/app";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { useAuth } from "../lib/auth";

function formatAuthError(error: unknown) {
  if (error instanceof FirebaseError) {
    return error.message.replace("Firebase: ", "").replace(/\s*\(auth\/[^)]+\)\.?/, ".");
  }
  if (error instanceof Error) return error.message;
  return "Authentication failed.";
}

export function LoginPage() {
  const { configured, signInWithEmail, signUpWithEmail } = useAuth();
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();
  const location = useLocation();
  const redirectTo = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname ?? "/app";

  async function handleSubmit() {
    setSubmitting(true);
    setError(null);
    try {
      if (mode === "signin") {
        await signInWithEmail(email, password);
      } else {
        await signUpWithEmail(email, password);
      }
      navigate(redirectTo, { replace: true });
    } catch (nextError) {
      setError(formatAuthError(nextError));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,rgba(59,130,246,0.18),transparent_30%),linear-gradient(180deg,#020617,#0f172a_45%,#020617)] px-6 py-10 text-white">
      <div className="mx-auto flex min-h-[calc(100vh-5rem)] max-w-6xl items-center gap-10 lg:grid lg:grid-cols-[1.1fr_0.9fr]">
        <div className="space-y-8">
          <Link to="/" className="inline-flex items-center gap-3 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-blue-100 transition hover:bg-white/10">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-cyan-400">
              <Database className="h-5 w-5 text-white" />
            </div>
            <span>DataAlchemy Secure Workspace</span>
          </Link>

          <div className="space-y-4">
            <p className="inline-flex items-center gap-2 rounded-full border border-cyan-400/20 bg-cyan-400/10 px-3 py-1 text-xs uppercase tracking-[0.24em] text-cyan-200">
              <Sparkles className="h-3.5 w-3.5" />
              Firebase Auth Enabled
            </p>
            <h1 className="max-w-2xl text-5xl font-semibold tracking-tight text-white">
              Sign in to protect datasets, reports, and live agent sessions.
            </h1>
            <p className="max-w-2xl text-lg leading-8 text-slate-300">
              Each workspace is now scoped to the authenticated user, so uploads and report artifacts stay tied to the right account.
            </p>
          </div>
        </div>

        <Card className="border-white/10 bg-slate-950/75 text-white shadow-2xl shadow-blue-950/30 backdrop-blur">
          <CardHeader className="space-y-2">
            <CardTitle className="text-2xl">{mode === "signin" ? "Welcome back" : "Create your account"}</CardTitle>
            <CardDescription className="text-slate-400">
              {configured
                ? "Use email/password to access your workspace."
                : "Firebase client config is missing. Add your VITE_FIREBASE_* variables first."}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="grid gap-2">
              <Label htmlFor="email" className="text-slate-200">Email</Label>
              <div className="relative">
                <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
                <Input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder="you@company.com"
                  className="h-11 border-white/10 bg-white/5 pl-10 text-white placeholder:text-slate-500"
                />
              </div>
            </div>

            <div className="grid gap-2">
              <Label htmlFor="password" className="text-slate-200">Password</Label>
              <div className="relative">
                <LockKeyhole className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
                <Input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="At least 6 characters"
                  className="h-11 border-white/10 bg-white/5 pl-10 text-white placeholder:text-slate-500"
                />
              </div>
            </div>

            {error ? <p className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">{error}</p> : null}

            <Button className="h-11 w-full" onClick={() => void handleSubmit()} disabled={!configured || submitting || !email || password.length < 6}>
              {submitting ? "Working..." : mode === "signin" ? "Sign In" : "Create Account"}
            </Button>

            <div className="flex items-center justify-between border-t border-white/10 pt-4 text-sm text-slate-400">
              <span>{mode === "signin" ? "Need an account?" : "Already have an account?"}</span>
              <button
                type="button"
                onClick={() => setMode((current) => (current === "signin" ? "signup" : "signin"))}
                className="font-medium text-blue-200 transition hover:text-white"
              >
                {mode === "signin" ? "Create one" : "Sign in"}
              </button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
