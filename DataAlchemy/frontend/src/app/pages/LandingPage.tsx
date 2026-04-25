import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Link } from "react-router";
import {
  Upload,
  Activity,
  Zap,
  CheckCircle2,
  Database,
  BarChart3,
  Workflow,
  FileSpreadsheet,
  ChevronRight,
  Github,
  Twitter,
  Linkedin,
  MessageSquare,
  Users,
  Sparkles,
  TrendingUp,
  Target,
  DollarSign,
  ArrowRight,
  Code2,
  Clock,
} from "lucide-react";

const steps = [
  {
    number: "01",
    title: "User Ingest",
    description: "Upload your CSV dataset through a simple interface with no preprocessing required.",
    icon: Upload,
    iconWrapClass: "bg-blue-500/10",
    iconClass: "text-blue-400",
  },
  {
    number: "02",
    title: "Supervisor Chat",
    description: "Tell the supervisor what you want in plain English and let it build the execution plan.",
    icon: MessageSquare,
    iconWrapClass: "bg-cyan-500/10",
    iconClass: "text-cyan-300",
  },
  {
    number: "03",
    title: "Agent Execution",
    description: "Specialized workers clean, engineer features, train, and evaluate models autonomously.",
    icon: Users,
    iconWrapClass: "bg-orange-500/10",
    iconClass: "text-orange-300",
  },
  {
    number: "04",
    title: "BI Insight",
    description: "Receive technical reports, artifacts, and exports that are ready for downstream dashboards.",
    icon: BarChart3,
    iconWrapClass: "bg-emerald-500/10",
    iconClass: "text-emerald-300",
  },
];

const features = [
  {
    title: "Autonomous Preprocessing",
    description:
      "Cleaning agents automatically handle missing values, outliers, encoding, and normalization without manual intervention.",
    icon: Sparkles,
    iconWrapClass: "bg-blue-500/10",
    iconClass: "text-blue-400",
  },
  {
    title: "Multi-Model Swarm",
    description:
      "Multiple model trainers work in parallel, comparing algorithms and hyperparameters to find the best performing solution.",
    icon: Users,
    iconWrapClass: "bg-violet-500/10",
    iconClass: "text-violet-300",
  },
  {
    title: "LLM-Powered Summaries",
    description:
      "Executive summaries in plain English explain model performance, insights, and recommendations for business stakeholders.",
    icon: MessageSquare,
    iconWrapClass: "bg-orange-500/10",
    iconClass: "text-orange-300",
  },
  {
    title: "One-Click Power BI Export",
    description:
      "Pre-formatted exports optimized for Power BI visualization, ready to integrate into existing dashboards.",
    icon: BarChart3,
    iconWrapClass: "bg-emerald-500/10",
    iconClass: "text-emerald-300",
  },
];

const useCases = [
  {
    title: "Customer Churn Prediction",
    description:
      "Identify at-risk customers before they leave and deploy retention strategies based on AI-driven insights.",
    icon: TrendingUp,
    metric: "92% accuracy",
  },
  {
    title: "Sales Forecasting",
    description:
      "Predict revenue trends with confidence and optimize inventory and resourcing for peak periods.",
    icon: DollarSign,
    metric: "15% improvement",
  },
  {
    title: "Lead Scoring",
    description:
      "Prioritize high-value prospects automatically and increase conversion rates with intelligent ranking.",
    icon: Target,
    metric: "2.3x conversion",
  },
];

const roadmap = [
  {
    title: "Supervisor Chat",
    description: "Conversational interface to define ML goals and orchestrate agent execution.",
    icon: MessageSquare,
  },
  {
    title: "Agent Workers",
    description: "Specialized agents for cleaning, feature engineering, model training, and evaluation.",
    icon: Users,
  },
  {
    title: "Model Comparison",
    description: "Automatic benchmarking across multiple algorithms with hyperparameter tuning.",
    icon: BarChart3,
  },
  {
    title: "Power BI Integration",
    description: "One-click exports with pre-built visualizations and dashboards.",
    icon: Workflow,
  },
];

export function LandingPage() {
  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,rgba(59,130,246,0.16),transparent_32%),linear-gradient(180deg,#040814_0%,#071120_52%,#050814_100%)] text-slate-50">
      <nav className="border-b border-white/8 bg-slate-950/40 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-cyan-400">
              <Database className="h-5 w-5 text-white" />
            </div>
            <span className="text-xl font-semibold text-white">DataAlchemy</span>
          </div>
          <div className="flex items-center gap-6">
            <a href="#features" className="text-sm text-slate-400 transition hover:text-white">
              Features
            </a>
            <a href="#how-it-works" className="text-sm text-slate-400 transition hover:text-white">
              How It Works
            </a>
            <a href="#pricing" className="text-sm text-slate-400 transition hover:text-white">
              Pricing
            </a>
            <Link to="/login">
              <Button variant="ghost" className="text-slate-200 hover:bg-white/5 hover:text-white">
                Login
              </Button>
            </Link>
            <Link to="/login">
              <Button className="bg-white text-slate-950 hover:bg-slate-100">Get Started</Button>
            </Link>
          </div>
        </div>
      </nav>

      <section className="mx-auto max-w-7xl px-6 py-20">
        <div className="grid items-center gap-12 lg:grid-cols-2">
          <div className="space-y-6">
            <Badge variant="secondary" className="w-fit border border-cyan-400/20 bg-cyan-400/10 text-cyan-100">
              Autonomous Multi-Agent ML Platform
            </Badge>
            <h1 className="text-5xl leading-tight text-white">
              Turning raw data into business gold
            </h1>
            <p className="text-xl text-slate-300">
              Orchestrate a swarm of specialized AI agents to clean data, train models, and generate Power BI-ready insights without writing a single line of code.
            </p>
            <div className="flex gap-4">
              <Link to="/login">
                <Button size="lg" className="gap-2 bg-white text-slate-950 hover:bg-slate-100">
                  Get Started for Free
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </Link>
              <Button size="lg" variant="outline" className="border-white/10 bg-white/5 text-slate-100 hover:bg-white/10 hover:text-white">
                Watch Demo
              </Button>
            </div>
            <div className="flex items-center gap-6 pt-4 text-sm text-slate-400">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-green-500" />
                <span>No coding required</span>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-green-500" />
                <span>Power BI ready</span>
              </div>
            </div>
          </div>

          <div className="relative">
            <div className="absolute inset-0 bg-gradient-to-r from-blue-500/20 to-violet-500/20 blur-3xl" />
            <Card className="relative border border-white/10 bg-slate-950/75 shadow-2xl shadow-blue-950/25 backdrop-blur">
              <CardHeader className="border-b border-white/10 bg-white/[0.03]">
                <div className="flex items-center gap-2 text-sm">
                  <MessageSquare className="h-4 w-4 text-cyan-300" />
                  <span className="text-slate-400">Supervisor Agent</span>
                </div>
              </CardHeader>
              <CardContent className="space-y-4 p-6">
                <div className="space-y-3">
                  <div className="rounded-lg border border-blue-500/20 bg-blue-500/10 p-3">
                    <p className="text-sm text-slate-100">
                      "Build a churn prediction model from customer_data.csv"
                    </p>
                  </div>
                  <div className="flex justify-end">
                    <div className="max-w-[80%] rounded-lg border border-white/10 bg-white/[0.05] p-3">
                      <p className="text-sm text-slate-300">
                        Analyzing dataset, deploying cleaning agents, feature engineering, and model trainers.
                      </p>
                    </div>
                  </div>
                </div>
                <div className="border-t border-white/10 pt-2">
                  <div className="flex items-center gap-2 text-xs text-slate-400">
                    <Users className="h-3 w-3" />
                    <span>4 agents working</span>
                    <div className="ml-2 flex gap-1">
                      <div className="h-2 w-2 animate-pulse rounded-full bg-green-500" />
                      <div className="h-2 w-2 animate-pulse rounded-full bg-green-500" />
                      <div className="h-2 w-2 animate-pulse rounded-full bg-green-500" />
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-6 py-20">
        <div className="grid gap-8 md:grid-cols-2">
          <Card className="border border-red-500/20 bg-red-500/5 text-slate-50">
            <CardHeader>
              <div className="mb-2 flex items-center gap-3">
                <Code2 className="h-6 w-6 text-red-500" />
                <CardTitle>The Old Way</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center gap-3 text-sm text-slate-300">
                <Clock className="h-4 w-4" />
                <span>Weeks of manual coding and debugging</span>
              </div>
              <div className="flex items-center gap-3 text-sm text-slate-300">
                <Code2 className="h-4 w-4" />
                <span>Complex data science expertise required</span>
              </div>
              <div className="flex items-center gap-3 text-sm text-slate-300">
                <Activity className="h-4 w-4" />
                <span>Error-prone manual preprocessing</span>
              </div>
              <div className="flex items-center gap-3 text-sm text-slate-300">
                <FileSpreadsheet className="h-4 w-4" />
                <span>Manual export and BI integration</span>
              </div>
            </CardContent>
          </Card>

          <Card className="border border-green-500/20 bg-green-500/5 text-slate-50">
            <CardHeader>
              <div className="mb-2 flex items-center gap-3">
                <Sparkles className="h-6 w-6 text-green-500" />
                <CardTitle>The DataAlchemy Way</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center gap-3 text-sm text-slate-300">
                <Zap className="h-4 w-4 text-green-500" />
                <span>Minutes from upload to insights</span>
              </div>
              <div className="flex items-center gap-3 text-sm text-slate-300">
                <MessageSquare className="h-4 w-4 text-green-500" />
                <span>Natural language conversational interface</span>
              </div>
              <div className="flex items-center gap-3 text-sm text-slate-300">
                <Users className="h-4 w-4 text-green-500" />
                <span>Autonomous agent swarm handles everything</span>
              </div>
              <div className="flex items-center gap-3 text-sm text-slate-300">
                <BarChart3 className="h-4 w-4 text-green-500" />
                <span>One-click Power BI export</span>
              </div>
            </CardContent>
          </Card>
        </div>
      </section>

      <section id="how-it-works" className="mx-auto max-w-7xl px-6 py-20">
        <div className="mb-12 space-y-4 text-center">
          <Badge variant="secondary" className="mx-auto w-fit border border-white/10 bg-white/5 text-slate-200">
            The Agentic Swarm
          </Badge>
          <h2 className="text-3xl text-white">How DataAlchemy works</h2>
          <p className="mx-auto max-w-2xl text-lg text-slate-400">
            Four seamless steps from raw CSV to actionable business intelligence
          </p>
        </div>
        <div className="grid gap-6 md:grid-cols-4">
          {steps.map((step, index) => (
            <div key={step.number} className="relative">
              <Card className="h-full border border-white/10 bg-white/[0.03] text-slate-50">
                <CardHeader>
                  <div className="mb-4 flex items-center justify-between">
                    <span className="text-3xl font-bold text-slate-600/60">{step.number}</span>
                    <div className={`flex h-12 w-12 items-center justify-center rounded-xl ${step.iconWrapClass}`}>
                      <step.icon className={`h-6 w-6 ${step.iconClass}`} />
                    </div>
                  </div>
                  <CardTitle className="text-lg">{step.title}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-slate-300">{step.description}</p>
                </CardContent>
              </Card>
              {index < steps.length - 1 ? (
                <div className="absolute -right-3 top-1/2 z-10 hidden md:block">
                  <ArrowRight className="h-6 w-6 text-slate-600/60" />
                </div>
              ) : null}
            </div>
          ))}
        </div>
      </section>

      <section id="features" className="mx-auto max-w-7xl px-6 py-20">
        <div className="mb-12 space-y-4 text-center">
          <h2 className="text-3xl text-white">Built for automation and output</h2>
          <p className="mx-auto max-w-2xl text-lg text-slate-400">
            Enterprise-grade ML pipelines, delivered autonomously
          </p>
        </div>
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
          {features.map((feature) => (
            <Card key={feature.title} className="border border-white/10 bg-white/[0.03] text-slate-50">
              <CardHeader>
                <div className={`mb-4 flex h-12 w-12 items-center justify-center rounded-lg ${feature.iconWrapClass}`}>
                  <feature.icon className={`h-6 w-6 ${feature.iconClass}`} />
                </div>
                <CardTitle>{feature.title}</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-slate-300">{feature.description}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-6 py-20">
        <div className="mb-12 space-y-4 text-center">
          <h2 className="text-3xl text-white">Proven use cases across industries</h2>
          <p className="mx-auto max-w-2xl text-lg text-slate-400">
            From customer analytics to financial forecasting
          </p>
        </div>
        <div className="grid gap-6 md:grid-cols-3">
          {useCases.map((useCase) => (
            <Card key={useCase.title} className="border border-white/10 bg-white/[0.03] text-slate-50">
              <CardHeader>
                <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500/10 to-cyan-500/10">
                  <useCase.icon className="h-6 w-6 text-blue-400" />
                </div>
                <CardTitle className="text-lg">{useCase.title}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="text-sm text-slate-300">{useCase.description}</p>
                <Badge variant="secondary" className="border border-white/10 bg-white/5 text-xs text-slate-200">
                  {useCase.metric}
                </Badge>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-6 py-20">
        <div className="mb-12 space-y-4 text-center">
          <Badge variant="secondary" className="mx-auto w-fit border border-white/10 bg-white/5 text-slate-200">
            Product Roadmap
          </Badge>
          <h2 className="text-3xl text-white">Building toward full orchestration</h2>
          <p className="mx-auto max-w-2xl text-lg text-slate-400">
            Current V1 focuses on ingestion and profiling. Future milestones will unlock the complete agentic ML platform.
          </p>
        </div>
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
          {roadmap.map((item) => (
            <Card key={item.title} className="relative overflow-hidden border border-white/10 bg-white/[0.03] text-slate-50">
              <div className="absolute right-4 top-4">
                <Badge variant="outline" className="border-white/10 text-xs text-slate-300">
                  Coming Soon
                </Badge>
              </div>
              <CardHeader>
                <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-white/5">
                  <item.icon className="h-6 w-6 text-slate-300" />
                </div>
                <CardTitle className="text-lg">{item.title}</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-slate-300">{item.description}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      <section id="pricing" className="mx-auto max-w-7xl px-6 py-20">
        <Card className="relative overflow-hidden border border-white/10 bg-slate-950/70 text-slate-50">
          <div className="absolute inset-0 bg-gradient-to-r from-blue-500/12 to-violet-500/12" />
          <CardContent className="relative space-y-6 p-12 text-center">
            <h2 className="text-3xl text-white">Ready to accelerate your data-to-insights workflow?</h2>
            <p className="mx-auto max-w-2xl text-lg text-slate-300">
              Join teams who are building ML pipelines without coding. Start with CSV upload and schema profiling today, then unlock the full agentic platform.
            </p>
            <div className="flex justify-center gap-4">
              <Link to="/login">
                <Button size="lg" className="gap-2 bg-white text-slate-950 hover:bg-slate-100">
                  Get Started for Free
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </Link>
              <Button size="lg" variant="outline" className="border-white/10 bg-white/5 text-slate-100 hover:bg-white/10 hover:text-white">
                Schedule a Demo
              </Button>
            </div>
            <div className="flex items-center justify-center gap-6 pt-4 text-sm text-slate-400">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-green-500" />
                <span>No credit card required</span>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-green-500" />
                <span>Free schema profiling</span>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-green-500" />
                <span>Enterprise support available</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </section>

      <footer className="mt-20 border-t border-white/8 bg-slate-950/40">
        <div className="mx-auto max-w-7xl px-6 py-12">
          <div className="grid gap-8 md:grid-cols-4">
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-blue-500 to-cyan-400">
                  <Database className="h-5 w-5 text-white" />
                </div>
                <span className="text-xl font-semibold text-white">DataAlchemy</span>
              </div>
              <p className="text-sm text-slate-400">
                Autonomous multi-agent ML platform for business teams
              </p>
            </div>
            <div>
              <h3 className="mb-4 font-semibold text-white">Product</h3>
              <ul className="space-y-2 text-sm text-slate-400">
                <li>
                  <Link to="/login" className="hover:text-white">Upload Dataset</Link>
                </li>
                <li>
                  <Link to="/login" className="hover:text-white">Schema Profile</Link>
                </li>
                <li>
                  <a href="#features" className="hover:text-white">Features</a>
                </li>
                <li>
                  <a href="#pricing" className="hover:text-white">Pricing</a>
                </li>
              </ul>
            </div>
            <div>
              <h3 className="mb-4 font-semibold text-white">Resources</h3>
              <ul className="space-y-2 text-sm text-slate-400">
                <li>Documentation</li>
                <li>API Reference</li>
                <li>Use Cases</li>
                <li>Support</li>
              </ul>
            </div>
            <div>
              <h3 className="mb-4 font-semibold text-white">Company</h3>
              <ul className="space-y-2 text-sm text-slate-400">
                <li>About</li>
                <li>Blog</li>
                <li>Careers</li>
                <li>Contact</li>
              </ul>
            </div>
          </div>
          <div className="mt-8 flex items-center justify-between border-t border-white/8 pt-8">
            <p className="text-sm text-slate-400">© 2026 DataAlchemy. All rights reserved.</p>
            <div className="flex items-center gap-4">
              <Github className="h-5 w-5 cursor-pointer text-slate-400 hover:text-white" />
              <Twitter className="h-5 w-5 cursor-pointer text-slate-400 hover:text-white" />
              <Linkedin className="h-5 w-5 cursor-pointer text-slate-400 hover:text-white" />
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
