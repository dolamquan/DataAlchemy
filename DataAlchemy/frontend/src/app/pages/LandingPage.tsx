import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Link } from "react-router";
import {
  Upload,
  FileSearch,
  Activity,
  Zap,
  CheckCircle2,
  Database,
  BarChart3,
  Workflow,
  FileSpreadsheet,
  Shield,
  GitBranch,
  Brain,
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

export function LandingPage() {
  return (
    <div className="min-h-screen bg-background">
      {/* Navigation */}
      <nav className="border-b border-border">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-violet-500 flex items-center justify-center">
              <Database className="w-5 h-5 text-white" />
            </div>
            <span className="text-xl font-semibold">DataAlchemy</span>
          </div>
          <div className="flex items-center gap-6">
            <a href="#features" className="text-sm text-muted-foreground hover:text-foreground">
              Features
            </a>
            <a href="#how-it-works" className="text-sm text-muted-foreground hover:text-foreground">
              How It Works
            </a>
            <a href="#pricing" className="text-sm text-muted-foreground hover:text-foreground">
              Pricing
            </a>
            <Button variant="ghost">Login</Button>
            <Button>Request Demo</Button>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="max-w-7xl mx-auto px-6 py-20">
        <div className="grid lg:grid-cols-2 gap-12 items-center">
          <div className="space-y-6">
            <Badge variant="secondary" className="w-fit">
              Autonomous Multi-Agent ML Platform
            </Badge>
            <h1 className="text-5xl leading-tight">
              Turning raw data into business gold
            </h1>
            <p className="text-xl text-muted-foreground">
              Orchestrate a swarm of specialized AI agents to clean data, train
              models, and generate Power BI ready insights—without writing a
              single line of code.
            </p>
            <div className="flex gap-4">
              <Link to="/app">
                <Button size="lg" className="gap-2">
                  Get Started for Free
                  <ChevronRight className="w-4 h-4" />
                </Button>
              </Link>
              <Button size="lg" variant="outline">
                Watch Demo
              </Button>
            </div>
            <div className="flex items-center gap-6 pt-4 text-sm text-muted-foreground">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-green-500" />
                <span>No coding required</span>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-green-500" />
                <span>Power BI ready</span>
              </div>
            </div>
          </div>
          <div className="relative">
            <div className="absolute inset-0 bg-gradient-to-r from-blue-500/20 to-violet-500/20 blur-3xl" />
            <Card className="relative border-2">
              <CardHeader className="border-b bg-muted/30">
                <div className="flex items-center gap-2 text-sm">
                  <MessageSquare className="w-4 h-4" />
                  <span className="text-muted-foreground">Supervisor Agent</span>
                </div>
              </CardHeader>
              <CardContent className="p-6 space-y-4">
                <div className="space-y-3">
                  <div className="p-3 rounded-lg bg-blue-500/10 border border-blue-500/20">
                    <p className="text-sm">
                      "Build a churn prediction model from customer_data.csv"
                    </p>
                  </div>
                  <div className="flex justify-end">
                    <div className="p-3 rounded-lg bg-muted max-w-[80%]">
                      <p className="text-sm text-muted-foreground">
                        Analyzing dataset... Deploying cleaning agent, feature
                        engineer, and model trainers.
                      </p>
                    </div>
                  </div>
                </div>
                <div className="pt-2 border-t border-border">
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <Users className="w-3 h-3" />
                    <span>4 agents working</span>
                    <div className="flex gap-1 ml-2">
                      <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                      <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                      <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* Problem/Solution Section */}
      <section className="max-w-7xl mx-auto px-6 py-20">
        <div className="grid md:grid-cols-2 gap-8">
          <Card className="border-2 border-red-500/20 bg-red-500/5">
            <CardHeader>
              <div className="flex items-center gap-3 mb-2">
                <Code2 className="w-6 h-6 text-red-500" />
                <CardTitle>The Old Way</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center gap-3 text-sm text-muted-foreground">
                <Clock className="w-4 h-4" />
                <span>Weeks of manual coding and debugging</span>
              </div>
              <div className="flex items-center gap-3 text-sm text-muted-foreground">
                <Code2 className="w-4 h-4" />
                <span>Complex data science expertise required</span>
              </div>
              <div className="flex items-center gap-3 text-sm text-muted-foreground">
                <Activity className="w-4 h-4" />
                <span>Error-prone manual preprocessing</span>
              </div>
              <div className="flex items-center gap-3 text-sm text-muted-foreground">
                <FileSpreadsheet className="w-4 h-4" />
                <span>Manual export and BI integration</span>
              </div>
            </CardContent>
          </Card>

          <Card className="border-2 border-green-500/20 bg-green-500/5">
            <CardHeader>
              <div className="flex items-center gap-3 mb-2">
                <Sparkles className="w-6 h-6 text-green-500" />
                <CardTitle>The DataAlchemy Way</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center gap-3 text-sm text-muted-foreground">
                <Zap className="w-4 h-4 text-green-500" />
                <span>Minutes from upload to insights</span>
              </div>
              <div className="flex items-center gap-3 text-sm text-muted-foreground">
                <MessageSquare className="w-4 h-4 text-green-500" />
                <span>Natural language conversational interface</span>
              </div>
              <div className="flex items-center gap-3 text-sm text-muted-foreground">
                <Users className="w-4 h-4 text-green-500" />
                <span>Autonomous agent swarm handles everything</span>
              </div>
              <div className="flex items-center gap-3 text-sm text-muted-foreground">
                <BarChart3 className="w-4 h-4 text-green-500" />
                <span>One-click Power BI export</span>
              </div>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* The Agentic Swarm - How It Works */}
      <section id="how-it-works" className="max-w-7xl mx-auto px-6 py-20">
        <div className="text-center space-y-4 mb-12">
          <Badge variant="secondary" className="mx-auto w-fit">
            The Agentic Swarm
          </Badge>
          <h2 className="text-3xl">How DataAlchemy works</h2>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Four seamless steps from raw CSV to actionable business intelligence
          </p>
        </div>
        <div className="grid md:grid-cols-4 gap-6">
          {[
            {
              number: "01",
              title: "User Ingest",
              description: "Upload your CSV dataset through our simple interface. No preprocessing needed.",
              icon: Upload,
              color: "blue",
            },
            {
              number: "02",
              title: "Supervisor Chat",
              description: "Tell the Supervisor Agent your business goal in plain English.",
              icon: MessageSquare,
              color: "violet",
            },
            {
              number: "03",
              title: "Agent Execution",
              description: "Specialized workers autonomously clean, engineer features, train, and evaluate models.",
              icon: Users,
              color: "orange",
            },
            {
              number: "04",
              title: "BI Insight",
              description: "Receive executive summaries and Power BI export files ready for visualization.",
              icon: BarChart3,
              color: "green",
            },
          ].map((step, i) => (
            <div key={i} className="relative">
              <Card className="border-2 h-full">
                <CardHeader>
                  <div className="flex items-center justify-between mb-4">
                    <span className="text-3xl font-bold text-muted-foreground/30">
                      {step.number}
                    </span>
                    <div className={`w-12 h-12 rounded-xl bg-${step.color}-500/10 flex items-center justify-center`}>
                      <step.icon className={`w-6 h-6 text-${step.color}-500`} />
                    </div>
                  </div>
                  <CardTitle className="text-lg">{step.title}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">
                    {step.description}
                  </p>
                </CardContent>
              </Card>
              {i < 3 && (
                <div className="hidden md:block absolute top-1/2 -right-3 z-10">
                  <ArrowRight className="w-6 h-6 text-muted-foreground/30" />
                </div>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* Key Features */}
      <section id="features" className="max-w-7xl mx-auto px-6 py-20">
        <div className="text-center space-y-4 mb-12">
          <h2 className="text-3xl">Built for automation and output</h2>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Enterprise-grade ML pipelines, delivered autonomously
          </p>
        </div>
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
          <Card className="border-2">
            <CardHeader>
              <div className="w-12 h-12 rounded-lg bg-blue-500/10 flex items-center justify-center mb-4">
                <Sparkles className="w-6 h-6 text-blue-500" />
              </div>
              <CardTitle>Autonomous Preprocessing</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Cleaning agents automatically handle missing values, outliers,
                encoding, and normalization without manual intervention.
              </p>
            </CardContent>
          </Card>

          <Card className="border-2">
            <CardHeader>
              <div className="w-12 h-12 rounded-lg bg-violet-500/10 flex items-center justify-center mb-4">
                <Users className="w-6 h-6 text-violet-500" />
              </div>
              <CardTitle>Multi-Model Swarm</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Multiple model trainers work in parallel, comparing algorithms
                and hyperparameters to find the best performing solution.
              </p>
            </CardContent>
          </Card>

          <Card className="border-2">
            <CardHeader>
              <div className="w-12 h-12 rounded-lg bg-orange-500/10 flex items-center justify-center mb-4">
                <MessageSquare className="w-6 h-6 text-orange-500" />
              </div>
              <CardTitle>LLM-Powered Summaries</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Executive summaries in plain English explain model performance,
                insights, and recommendations for business stakeholders.
              </p>
            </CardContent>
          </Card>

          <Card className="border-2">
            <CardHeader>
              <div className="w-12 h-12 rounded-lg bg-green-500/10 flex items-center justify-center mb-4">
                <BarChart3 className="w-6 h-6 text-green-500" />
              </div>
              <CardTitle>One-Click Power BI Export</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Pre-formatted exports optimized for Power BI visualization,
                ready to integrate into your existing dashboards.
              </p>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* Use Case Carousel */}
      <section className="max-w-7xl mx-auto px-6 py-20">
        <div className="text-center space-y-4 mb-12">
          <h2 className="text-3xl">Proven use cases across industries</h2>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            From customer analytics to financial forecasting
          </p>
        </div>
        <div className="grid md:grid-cols-3 gap-6">
          {[
            {
              title: "Customer Churn Prediction",
              description:
                "Identify at-risk customers before they leave. Deploy retention strategies based on AI-driven insights.",
              icon: TrendingUp,
              metric: "92% accuracy",
            },
            {
              title: "Sales Forecasting",
              description:
                "Predict revenue trends with confidence. Optimize inventory and resource allocation for peak periods.",
              icon: DollarSign,
              metric: "15% improvement",
            },
            {
              title: "Lead Scoring",
              description:
                "Prioritize high-value prospects automatically. Increase conversion rates with intelligent lead ranking.",
              icon: Target,
              metric: "2.3x conversion",
            },
          ].map((useCase, i) => (
            <Card key={i} className="border-2">
              <CardHeader>
                <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-blue-500/10 to-violet-500/10 flex items-center justify-center mb-4">
                  <useCase.icon className="w-6 h-6 text-blue-500" />
                </div>
                <CardTitle className="text-lg">{useCase.title}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="text-sm text-muted-foreground">
                  {useCase.description}
                </p>
                <Badge variant="secondary" className="text-xs">
                  {useCase.metric}
                </Badge>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      {/* Future Roadmap Section */}
      <section className="max-w-7xl mx-auto px-6 py-20">
        <div className="text-center space-y-4 mb-12">
          <Badge variant="secondary" className="mx-auto w-fit">
            Product Roadmap
          </Badge>
          <h2 className="text-3xl">Building toward full orchestration</h2>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Current V1 focuses on ingestion and profiling. Future milestones will
            unlock the complete agentic ML platform.
          </p>
        </div>
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
          {[
            {
              title: "Supervisor Chat",
              description:
                "Conversational interface to define ML goals and orchestrate agent execution",
              icon: MessageSquare,
            },
            {
              title: "Agent Workers",
              description:
                "Specialized agents for cleaning, feature engineering, model training, and evaluation",
              icon: Users,
            },
            {
              title: "Model Comparison",
              description:
                "Automatic benchmarking across multiple algorithms with hyperparameter tuning",
              icon: BarChart3,
            },
            {
              title: "Power BI Integration",
              description:
                "One-click exports with pre-built visualizations and dashboards",
              icon: Workflow,
            },
          ].map((item, i) => (
            <Card key={i} className="border-2 relative overflow-hidden">
              <div className="absolute top-4 right-4">
                <Badge variant="outline" className="text-xs">
                  Coming Soon
                </Badge>
              </div>
              <CardHeader>
                <div className="w-12 h-12 rounded-lg bg-muted flex items-center justify-center mb-4">
                  <item.icon className="w-6 h-6 text-muted-foreground" />
                </div>
                <CardTitle className="text-lg">{item.title}</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  {item.description}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      {/* Final CTA Section */}
      <section id="pricing" className="max-w-7xl mx-auto px-6 py-20">
        <Card className="border-2 relative overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-r from-blue-500/10 to-violet-500/10" />
          <CardContent className="relative p-12 text-center space-y-6">
            <h2 className="text-3xl">
              Ready to accelerate your data-to-insights workflow?
            </h2>
            <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
              Join teams who are building ML pipelines without coding. Start with
              CSV upload and schema profiling today, unlock the full agentic
              platform soon.
            </p>
            <div className="flex gap-4 justify-center">
              <Link to="/app">
                <Button size="lg" className="gap-2">
                  Get Started for Free
                  <ChevronRight className="w-4 h-4" />
                </Button>
              </Link>
              <Button size="lg" variant="outline">
                Schedule a Demo
              </Button>
            </div>
            <div className="flex items-center justify-center gap-6 pt-4 text-sm text-muted-foreground">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-green-500" />
                <span>No credit card required</span>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-green-500" />
                <span>Free schema profiling</span>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-green-500" />
                <span>Enterprise support available</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </section>

      {/* Footer */}
      <footer className="border-t border-border mt-20">
        <div className="max-w-7xl mx-auto px-6 py-12">
          <div className="grid md:grid-cols-4 gap-8">
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-violet-500 flex items-center justify-center">
                  <Database className="w-5 h-5 text-white" />
                </div>
                <span className="text-xl font-semibold">DataAlchemy</span>
              </div>
              <p className="text-sm text-muted-foreground">
                Autonomous multi-agent ML platform for business teams
              </p>
            </div>
            <div>
              <h3 className="font-semibold mb-4">Product</h3>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li>
                  <Link to="/app" className="hover:text-foreground">
                    Upload Dataset
                  </Link>
                </li>
                <li>
                  <Link to="/app/schema" className="hover:text-foreground">
                    Schema Profile
                  </Link>
                </li>
                <li>
                  <a href="#features" className="hover:text-foreground">
                    Features
                  </a>
                </li>
                <li>
                  <a href="#pricing" className="hover:text-foreground">
                    Pricing
                  </a>
                </li>
              </ul>
            </div>
            <div>
              <h3 className="font-semibold mb-4">Resources</h3>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li>Documentation</li>
                <li>API Reference</li>
                <li>Use Cases</li>
                <li>Support</li>
              </ul>
            </div>
            <div>
              <h3 className="font-semibold mb-4">Company</h3>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li>About</li>
                <li>Blog</li>
                <li>Careers</li>
                <li>Contact</li>
              </ul>
            </div>
          </div>
          <div className="flex items-center justify-between pt-8 mt-8 border-t border-border">
            <p className="text-sm text-muted-foreground">
              © 2026 DataAlchemy. All rights reserved.
            </p>
            <div className="flex items-center gap-4">
              <Github className="w-5 h-5 text-muted-foreground hover:text-foreground cursor-pointer" />
              <Twitter className="w-5 h-5 text-muted-foreground hover:text-foreground cursor-pointer" />
              <Linkedin className="w-5 h-5 text-muted-foreground hover:text-foreground cursor-pointer" />
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
