import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { format } from "date-fns";

interface ReportHeaderProps {
  riskScore: number;
  generatedAt: string;
}

const getRiskLevel = (score: number): { label: string; className: string } => {
  if (score < 0.3) {
    return { label: "Low", className: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30" };
  } else if (score < 0.6) {
    return { label: "Medium", className: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30" };
  } else if (score < 0.85) {
    return { label: "High", className: "bg-orange-500/20 text-orange-400 border-orange-500/30" };
  } else {
    return { label: "Critical", className: "bg-red-500/20 text-red-400 border-red-500/30" };
  }
};

const ReportHeader = ({ riskScore, generatedAt }: ReportHeaderProps) => {
  const { label, className } = getRiskLevel(riskScore);
  const formattedDate = format(new Date(generatedAt), "MMM d, yyyy 'at' h:mm a");

  return (
    <Card>
      <CardHeader>
        <CardTitle>Code Quality Report</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h3 className="text-sm font-medium text-muted-foreground mb-2">Risk Score</h3>
            <div className="flex items-baseline gap-3">
              <span className="text-4xl font-bold">{(riskScore * 100).toFixed(1)}</span>
              <Badge className={className}>{label}</Badge>
            </div>
          </div>
          <div className="text-sm text-muted-foreground">
            <span className="block">Generated</span>
            <span className="font-medium text-foreground">{formattedDate}</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default ReportHeader;
