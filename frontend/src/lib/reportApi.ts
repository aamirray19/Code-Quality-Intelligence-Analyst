const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export interface ErrorResponse {
  success: false;
  error_code: string;
  message: string;
}

export interface ReportMetrics {
  total_findings: number;
  by_severity: Record<string, number>;
  by_agent: Record<string, number>;
  files_affected: number;
}

export interface ReportRecord {
  id: string;
  scan_id: string;
  summary_markdown: string;
  metrics: ReportMetrics;
  risk_score: number;
  created_at: string;
}

export interface Finding {
  id: string | null;
  scan_id: string;
  agent: string;
  title: string;
  description: string;
  severity: string;
  confidence: number;
  file_id: string | null;
  symbol_id: string | null;
  file_path: string | null;
  symbol_name: string | null;
  start_line: number | null;
  end_line: number | null;
  evidence: string[];
  recommendation: string | null;
  fingerprint: string;
  related_agents: string[];
  created_at: string | null;
}

export async function fetchReport(scanId: string): Promise<ReportRecord> {
  const response = await fetch(`${API_BASE_URL}/scans/${scanId}/report`);
  const data = (await response.json()) as ReportRecord | ErrorResponse;
  if (!response.ok) {
    throw new Error((data as ErrorResponse).message ?? "Unable to fetch report.");
  }
  return data as ReportRecord;
}

export async function fetchFindings(
  scanId: string,
  filters?: { severity?: string; agent?: string; file_path?: string }
): Promise<Finding[]> {
  const params = new URLSearchParams();
  if (filters?.severity) {
    params.append("severity", filters.severity);
  }
  if (filters?.agent) {
    params.append("agent", filters.agent);
  }
  if (filters?.file_path) {
    params.append("file_path", filters.file_path);
  }
  
  const queryString = params.toString();
  const url = queryString 
    ? `${API_BASE_URL}/scans/${scanId}/findings?${queryString}`
    : `${API_BASE_URL}/scans/${scanId}/findings`;

  const response = await fetch(url);
  const data = (await response.json()) as Finding[] | ErrorResponse;
  if (!response.ok) {
    throw new Error((data as ErrorResponse).message ?? "Unable to fetch findings.");
  }
  return data as Finding[];
}
