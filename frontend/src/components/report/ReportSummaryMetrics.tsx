import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { ReportMetrics } from "@/lib/reportApi";

interface ReportSummaryMetricsProps {
  metrics: ReportMetrics;
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

const ReportSummaryMetrics = ({ metrics }: ReportSummaryMetricsProps) => {
  const severityEntries = Object.entries(metrics.by_severity).sort((a, b) => {
    const order = { extreme: 0, high: 1, medium: 2, low: 3 };
    return (order[a[0] as keyof typeof order] ?? 4) - (order[b[0] as keyof typeof order] ?? 4);
  });

  const agentEntries = Object.entries(metrics.by_agent).sort((a, b) => b[1] - a[1]);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {/* Total Findings */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Total Findings</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-3xl font-bold">{metrics.total_findings}</div>
        </CardContent>
      </Card>

      {/* Files Affected */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Files Affected</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-3xl font-bold">{metrics.files_affected}</div>
        </CardContent>
      </Card>

      {/* By Severity */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">By Severity</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {severityEntries.map(([severity, count]) => (
              <Badge key={severity} className={getSeverityColor(severity)}>
                {severity}: {count}
              </Badge>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* By Agent */}
      <Card className="md:col-span-2 lg:col-span-3">
        <CardHeader>
          <CardTitle className="text-base">By Agent</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {agentEntries.map(([agent, count]) => (
              <Badge key={agent} variant="outline">
                {agent}: {count}
              </Badge>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default ReportSummaryMetrics;
