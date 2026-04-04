import { Sparkles, GitBranch, Brain, BarChart3, Workflow, Clock } from "lucide-react";
import { Badge } from "../components/ui/badge";

interface ComingSoonPageProps {
  title: string;
  description: string;
}

const featureIcons: Record<string, any> = {
  "Projects": GitBranch,
  "Agents": Brain,
  "Reports": BarChart3,
  "Power BI Exports": Workflow,
  "Settings": Sparkles,
};

export function ComingSoonPage({ title, description }: ComingSoonPageProps) {
  const Icon = featureIcons[title] || Sparkles;

  return (
    <div className="flex items-center justify-center min-h-[calc(100vh-4rem)] p-8">
      <div className="max-w-2xl w-full text-center space-y-8">
        {/* Icon with gradient background */}
        <div className="flex justify-center">
          <div className="relative">
            <div className="absolute inset-0 bg-gradient-to-r from-blue-500/20 to-purple-600/20 blur-3xl" />
            <div className="relative w-24 h-24 rounded-2xl bg-gradient-to-br from-blue-500/10 to-purple-600/10 border-2 border-border flex items-center justify-center">
              <Icon className="w-12 h-12 text-blue-500" />
            </div>
          </div>
        </div>

        {/* Title and badge */}
        <div className="space-y-4">
          <div className="flex items-center justify-center gap-3">
            <h1 className="text-4xl">{title}</h1>
            <Badge variant="secondary" className="text-sm px-3 py-1">
              Coming Soon
            </Badge>
          </div>
          <p className="text-lg text-muted-foreground leading-relaxed">
            {description}
          </p>
        </div>

        {/* Status indicator */}
        <div className="flex items-center justify-center gap-3 py-6 border-y border-border">
          <Clock className="w-5 h-5 text-muted-foreground" />
          <span className="text-sm text-muted-foreground">
            This feature is on our roadmap and will be available in a future release
          </span>
        </div>

        {/* Simple visual indicator */}
        <div className="flex justify-center gap-2 pt-4">
          {[...Array(3)].map((_, i) => (
            <div
              key={i}
              className="w-2 h-2 rounded-full bg-muted-foreground/40"
            />
          ))}
        </div>
      </div>
    </div>
  );
}
