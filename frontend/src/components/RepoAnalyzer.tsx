import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Github, ArrowRight, Loader2 } from "lucide-react";
import { z } from "zod";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

const githubSchema = z
  .string()
  .trim()
  .url("Enter a valid URL")
  .regex(
    /^https:\/\/github\.com\/[\w.-]+\/[\w.-]+(\.git)?\/?(\/tree\/[\w./-]+)?$/,
    "Use the format https://github.com/owner/repo"
  );

type ScanStatus =
  | "queued"
  | "cloning"
  | "discovering_files"
  | "parsing"
  | "chunking"
  | "storing_indexes"
  | "parsed"
  | "analyzing"
  | "analyzed"
  | "analysis_failed"
  | "generating_report"
  | "reported"
  | "report_failed"
  | "completed"
  | "failed";

interface RepoInfoResponse {
  owner: string;
  name: string;
  full_name: string;
  branch: string;
  default_branch: string;
  clone_url: string;
  html_url: string;
  size_kb: number;
  visibility: string;
}

interface CreateScanResponse {
  success: true;
  scan_id: string;
  status: string;
  message: string;
  repo: RepoInfoResponse;
}

interface ErrorResponse {
  success: false;
  error_code: string;
  message: string;
}

interface ScanStatusResponse {
  scan_id: string;
  status: ScanStatus;
  repo: {
    owner: string;
    name: string;
    full_name: string;
    branch: string;
    html_url: string;
  };
  created_at: string;
  updated_at: string;
  error_message: string | null;
}

const TERMINAL_STATUSES: ScanStatus[] = ["reported", "failed", "analysis_failed", "report_failed", "completed"];

const STATUS_LABELS: Record<ScanStatus, string> = {
  queued: "Queued",
  cloning: "Cloning repository…",
  discovering_files: "Discovering files…",
  parsing: "Parsing code…",
  chunking: "Chunking code…",
  storing_indexes: "Storing indexes…",
  parsed: "Parsing complete",
  analyzing: "Analyzing…",
  analyzed: "Analysis complete",
  analysis_failed: "Analysis failed",
  generating_report: "Generating report…",
  reported: "Report ready",
  report_failed: "Report generation failed",
  completed: "Scan completed",
  failed: "Scan failed",
};

const DEFAULT_ERROR_MESSAGE =
  "Repository is invalid. Please enter a valid public GitHub repository URL.";

async function createScan(githubUrl: string): Promise<CreateScanResponse> {
  const response = await fetch(`${API_BASE_URL}/scans`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ github_url: githubUrl }),
  });
  const data = (await response.json()) as CreateScanResponse | ErrorResponse;
  if (!response.ok) {
    throw new Error((data as ErrorResponse).message ?? DEFAULT_ERROR_MESSAGE);
  }
  return data as CreateScanResponse;
}

async function fetchScanStatus(scanId: string): Promise<ScanStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/scans/${scanId}`);
  const data = (await response.json()) as ScanStatusResponse | ErrorResponse;
  if (!response.ok) {
    throw new Error((data as ErrorResponse).message ?? "Unable to fetch scan status.");
  }
  return data as ScanStatusResponse;
}

const RepoAnalyzer = () => {
  const navigate = useNavigate();
  const [url, setUrl] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [scanId, setScanId] = useState<string | null>(null);
  const [scanStatus, setScanStatus] = useState<ScanStatus | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  const startPolling = (id: string) => {
    stopPolling();
    pollRef.current = setInterval(async () => {
      try {
        const status = await fetchScanStatus(id);
        setScanStatus(status.status);
        if (status.status === "reported") {
          stopPolling();
          navigate(`/report/${id}`);
        } else if (TERMINAL_STATUSES.includes(status.status)) {
          stopPolling();
        }
      } catch (err) {
        stopPolling();
        setError(err instanceof Error ? err.message : "Unable to fetch scan status.");
      }
    }, 2000);
  };

  const handleSubmit = async () => {
    setError(null);
    const result = githubSchema.safeParse(url);
    if (!result.success) {
      setError(result.error.issues[0].message);
      return;
    }

    setIsSubmitting(true);
    setScanId(null);
    setScanStatus(null);
    stopPolling();
    try {
      const scan = await createScan(result.data);
      setScanId(scan.scan_id);
      setScanStatus(scan.status as ScanStatus);
      toast.success("Repository valid. Scan started.");
      startPolling(scan.scan_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : DEFAULT_ERROR_MESSAGE);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto">
      <div className="relative bg-card/60 backdrop-blur-md border border-border/60 rounded-2xl p-4 sm:p-5 shadow-[0_0_40px_-10px_hsl(var(--primary)/0.25)] transition-all duration-300 focus-within:border-primary/50 focus-within:shadow-[0_0_50px_-10px_hsl(var(--primary)/0.45)]">
        <div className="flex flex-col sm:flex-row items-stretch gap-2">
          <div className="flex items-center flex-1 bg-background/60 border border-border/50 rounded-xl px-3 focus-within:border-primary/60 transition-colors">
            <Github className="w-4 h-4 text-muted-foreground flex-shrink-0" aria-hidden />
            <input
              type="url"
              inputMode="url"
              autoComplete="off"
              spellCheck={false}
              value={url}
              onChange={(e) => {
                setUrl(e.target.value);
                if (error) setError(null);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleSubmit();
              }}
              placeholder="https://github.com/owner/repo"
              className="flex-1 bg-transparent border-0 outline-none px-3 py-3 text-sm sm:text-base text-foreground placeholder:text-muted-foreground/60"
              aria-label="GitHub repository URL"
              aria-invalid={!!error}
            />
          </div>
          <button
            onClick={handleSubmit}
            disabled={isSubmitting}
            className="inline-flex items-center justify-center gap-2 h-12 px-5 rounded-xl bg-primary text-primary-foreground font-semibold text-sm hover:brightness-110 active:scale-[0.98] transition disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Validating…
              </>
            ) : (
              <>
                Analyze
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </div>

        {error && (
          <p className="mt-3 text-xs text-destructive text-center" role="alert">
            {error}
          </p>
        )}

        {scanId && scanStatus && !error && (
          <div
            className={cn(
              "mt-4 flex items-center justify-center gap-2 text-sm",
              scanStatus === "failed" ? "text-destructive" : "text-foreground"
            )}
          >
            {!TERMINAL_STATUSES.includes(scanStatus) && (
              <Loader2 className="w-4 h-4 animate-spin text-primary" />
            )}
            <span>{STATUS_LABELS[scanStatus]}</span>
          </div>
        )}
      </div>

      <p className="mt-3 text-xs text-muted-foreground/80 text-center">
        Your code stays private. Reports cover bugs, smells, security, and complexity.
      </p>
    </div>
  );
};

export default RepoAnalyzer;
