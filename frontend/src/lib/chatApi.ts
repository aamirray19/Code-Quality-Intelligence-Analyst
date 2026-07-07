const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export interface ErrorResponse {
  success: false;
  error_code: string;
  message: string;
}

export interface ChatSessionRecord {
  id: string;
  scan_id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export interface ChatMessageRecord {
  id: string;
  session_id: string;
  role: string;
  content: string;
  sources: unknown[];
  created_at: string;
}

export async function createChatSession(
  scanId: string,
  title?: string
): Promise<ChatSessionRecord> {
  const response = await fetch(`${API_BASE_URL}/scans/${scanId}/chat/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title: title ?? null }),
  });
  const data = (await response.json()) as ChatSessionRecord | ErrorResponse;
  if (!response.ok) {
    throw new Error((data as ErrorResponse).message ?? "Unable to create chat session.");
  }
  return data as ChatSessionRecord;
}

export async function listChatSessions(scanId: string): Promise<ChatSessionRecord[]> {
  const response = await fetch(`${API_BASE_URL}/scans/${scanId}/chat/sessions`);
  const data = (await response.json()) as ChatSessionRecord[] | ErrorResponse;
  if (!response.ok) {
    throw new Error((data as ErrorResponse).message ?? "Unable to fetch chat sessions.");
  }
  return data as ChatSessionRecord[];
}

export async function sendChatMessage(
  scanId: string,
  sessionId: string,
  content: string
): Promise<ChatMessageRecord> {
  const response = await fetch(
    `${API_BASE_URL}/scans/${scanId}/chat/sessions/${sessionId}/messages`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    }
  );
  const data = (await response.json()) as ChatMessageRecord | ErrorResponse;
  if (!response.ok) {
    throw new Error((data as ErrorResponse).message ?? "Unable to send chat message.");
  }
  return data as ChatMessageRecord;
}

export async function listChatMessages(
  scanId: string,
  sessionId: string
): Promise<ChatMessageRecord[]> {
  const response = await fetch(
    `${API_BASE_URL}/scans/${scanId}/chat/sessions/${sessionId}/messages`
  );
  const data = (await response.json()) as ChatMessageRecord[] | ErrorResponse;
  if (!response.ok) {
    throw new Error((data as ErrorResponse).message ?? "Unable to fetch chat messages.");
  }
  return data as ChatMessageRecord[];
}
