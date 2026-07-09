import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { fetchReport, fetchFindings, type ReportRecord, type Finding } from "@/lib/reportApi";
import Navbar from "@/components/Navbar";
import ReportHeader from "@/components/report/ReportHeader";
import ReportSummaryMetrics from "@/components/report/ReportSummaryMetrics";
import MarkdownReportView from "@/components/report/MarkdownReportView";
import FindingsFilterBar from "@/components/report/FindingsFilterBar";
import FindingsList from "@/components/report/FindingsList";
import ChatSessionList from "@/components/chat/ChatSessionList";
import ChatPanel from "@/components/chat/ChatPanel";

// Canonical severity and agent values from backend
const AVAILABLE_SEVERITIES = ["extreme", "high", "medium", "low"];
const AVAILABLE_AGENTS = ["security", "performance", "complexity", "duplication", "reliability"];

const ReportPage = () => {
  const { scanId } = useParams<{ scanId: string }>();
  const [report, setReport] = useState<ReportRecord | null>(null);
  const [findings, setFindings] = useState<Finding[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Filter state
  const [severity, setSeverity] = useState<string | undefined>(undefined);
  const [agent, setAgent] = useState<string | undefined>(undefined);
  const [filePath, setFilePath] = useState<string | undefined>(undefined);

  // Chat session state
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);

  // Initial load: fetch report and findings
  useEffect(() => {
    const loadData = async () => {
      if (!scanId) {
        setError("No scan ID provided");
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        setError(null);
        const reportData = await fetchReport(scanId);
        setReport(reportData);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to load report");
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [scanId]);

  // Separate effect for findings with filters
  useEffect(() => {
    const loadFindings = async () => {
      if (!scanId) return;

      try {
        const findingsData = await fetchFindings(scanId, {
          severity,
          agent,
          file_path: filePath,
        });
        setFindings(findingsData);
      } catch (err) {
        console.error("Failed to load findings:", err);
        setFindings([]);
      }
    };

    loadFindings();
  }, [scanId, severity, agent, filePath]);

  if (loading) {
    return (
      <div className="min-h-screen bg-background">
        <Navbar />
        <main className="flex items-center justify-center min-h-[calc(100vh-64px)]">
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="w-8 h-8 animate-spin text-primary" />
            <p className="text-sm text-muted-foreground">Loading report…</p>
          </div>
        </main>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-background">
        <Navbar />
        <main className="flex items-center justify-center min-h-[calc(100vh-64px)]">
          <div className="text-center">
            <h1 className="mb-4 text-2xl font-bold text-destructive">Error Loading Report</h1>
            <p className="mb-4 text-muted-foreground">{error}</p>
            <a href="/" className="text-primary underline hover:text-primary/90">
              Return to Home
            </a>
          </div>
        </main>
      </div>
    );
  }

  if (!report || !findings) {
    return (
      <div className="min-h-screen bg-background">
        <Navbar />
        <main className="flex items-center justify-center min-h-[calc(100vh-64px)]">
          <div className="text-center">
            <p className="text-muted-foreground">No report data available</p>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main className="container mx-auto px-4 py-8">
        <div className="max-w-6xl mx-auto space-y-8">
          {/* Report Header */}
          <ReportHeader
            riskScore={report.risk_score}
            generatedAt={report.created_at}
          />

          {/* Summary Metrics */}
          <ReportSummaryMetrics metrics={report.metrics} />

          {/* Markdown Report Body */}
          <div className="bg-card border border-border rounded-lg p-6">
            <h2 className="text-xl font-semibold mb-4">Report Summary</h2>
            <MarkdownReportView markdown={report.summary_markdown} />
          </div>

          {/* Findings Section */}
          <div className="bg-card border border-border rounded-lg p-6">
            <h2 className="text-xl font-semibold mb-6">Findings</h2>
            <FindingsFilterBar
              severity={severity}
              agent={agent}
              filePath={filePath}
              onSeverityChange={setSeverity}
              onAgentChange={setAgent}
              onFilePathChange={setFilePath}
              availableSeverities={AVAILABLE_SEVERITIES}
              availableAgents={AVAILABLE_AGENTS}
            />
            <FindingsList findings={findings ?? []} />
          </div>

          {/* Chat Panel */}
          <div className="bg-card border border-border rounded-lg p-6">
            <h2 className="text-xl font-semibold mb-6">Ask About This Repository</h2>
            <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-4" style={{ height: "600px" }}>
              <ChatSessionList
                scanId={scanId!}
                selectedSessionId={selectedSessionId}
                onSelectSession={setSelectedSessionId}
                onSessionCreated={(session) => setSelectedSessionId(session.id)}
              />
              <ChatPanel scanId={scanId!} sessionId={selectedSessionId} />
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default ReportPage;
