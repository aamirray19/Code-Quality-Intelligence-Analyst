import { useEffect, useState } from "react";
import { Loader2, Plus } from "lucide-react";
import { toast } from "sonner";
import {
  listChatSessions,
  createChatSession,
  type ChatSessionRecord,
} from "@/lib/chatApi";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface ChatSessionListProps {
  scanId: string;
  selectedSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
  onSessionCreated: (session: ChatSessionRecord) => void;
}

const formatRelativeDate = (dateStr: string): string => {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
};

const ChatSessionList = ({
  scanId,
  selectedSessionId,
  onSelectSession,
  onSessionCreated,
}: ChatSessionListProps) => {
  const [sessions, setSessions] = useState<ChatSessionRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    const loadSessions = async () => {
      try {
        setLoading(true);
        const data = await listChatSessions(scanId);
        setSessions(data);
      } catch (err) {
        toast.error("Failed to load chat sessions");
        console.error("Failed to load sessions:", err);
      } finally {
        setLoading(false);
      }
    };

    loadSessions();
  }, [scanId]);

  const handleNewChat = async () => {
    try {
      setCreating(true);
      const newSession = await createChatSession(scanId);
      setSessions((prev) => [newSession, ...prev]);
      onSessionCreated(newSession);
      toast.success("New conversation created");
    } catch (err) {
      toast.error("Failed to create new chat");
      console.error("Failed to create session:", err);
    } finally {
      setCreating(false);
    }
  };

  if (loading) {
    return (
      <Card className="h-full">
        <CardContent className="flex items-center justify-center py-8">
          <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="h-full flex flex-col">
      <CardContent className="p-4 flex flex-col h-full">
        <Button
          onClick={handleNewChat}
          disabled={creating}
          className="w-full mb-4"
          size="sm"
        >
          {creating ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Plus className="w-4 h-4" />
          )}
          New Chat
        </Button>

        <div className="flex-1 overflow-y-auto space-y-2">
          {sessions.length === 0 ? (
            <p className="text-center text-sm text-muted-foreground py-8">
              No conversations yet — start one!
            </p>
          ) : (
            sessions.map((session) => (
              <button
                key={session.id}
                onClick={() => onSelectSession(session.id)}
                className={cn(
                  "w-full text-left px-3 py-2 rounded-md transition-colors",
                  "hover:bg-accent/50",
                  selectedSessionId === session.id
                    ? "bg-accent text-accent-foreground"
                    : "bg-background text-foreground"
                )}
              >
                <p className="text-sm font-medium truncate">
                  {session.title ?? "New conversation"}
                </p>
                <p className="text-xs text-muted-foreground">
                  {formatRelativeDate(session.created_at)}
                </p>
              </button>
            ))
          )}
        </div>
      </CardContent>
    </Card>
  );
};

export default ChatSessionList;
