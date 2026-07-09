import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { Finding } from "@/lib/reportApi";

interface FindingsListProps {
  findings: Finding[];
}

const getSeverityColor = (severity: string): string => {
  const severityLower = severity.toLowerCase();
  if (severityLower === "extreme") {
    return "bg-red-600/20 text-red-400 border-red-600/30";
  } else if (severityLower === "high") {
    return "bg-orange-500/20 text-orange-400 border-orange-500/30";
  } else if (severityLower === "medium") {
    return "bg-yellow-500/20 text-yellow-400 border-yellow-500/30";
  } else {
    return "bg-blue-500/20 text-blue-400 border-blue-500/30";
  }
};

const FindingsList = ({ findings }: FindingsListProps) => {
  if (findings.length === 0) {
    return (
      <Card>
        <CardContent className="py-8">
          <p className="text-center text-muted-foreground">
            No findings match your filters.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {findings.map((finding, index) => {
        const locationText = finding.file_path
          ? finding.start_line && finding.end_line
            ? `${finding.file_path}:${finding.start_line}-${finding.end_line}`
            : finding.file_path
          : null;

        return (
          <Card key={finding.id ?? `finding-${index}`}>
            <CardHeader>
              <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2">
                <CardTitle className="text-lg">{finding.title}</CardTitle>
                <div className="flex items-center gap-2">
                  <Badge className={getSeverityColor(finding.severity)}>
                    {finding.severity}
                  </Badge>
                  <Badge variant="outline">{finding.agent}</Badge>
                </div>
              </div>
              {locationText && (
                <p className="text-sm text-muted-foreground font-mono mt-1">
                  {locationText}
                </p>
              )}
            </CardHeader>
            <CardContent className="space-y-3">
              <div>
                <p className="text-sm text-foreground">{finding.description}</p>
              </div>
              {finding.recommendation && (
                <div className="border-l-2 border-primary/50 pl-3">
                  <p className="text-sm font-medium text-muted-foreground mb-1">
                    Recommendation:
                  </p>
                  <p className="text-sm italic text-foreground">
                    {finding.recommendation}
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
};

export default FindingsList;
