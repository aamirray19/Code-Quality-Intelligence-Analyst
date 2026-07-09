import type { ChatMessageRecord } from "@/lib/chatApi";
import { Badge } from "@/components/ui/badge";
import MarkdownReportView from "@/components/report/MarkdownReportView";
import { cn } from "@/lib/utils";

interface ChatMessageBubbleProps {
  message: ChatMessageRecord;
}

const ChatMessageBubble = ({ message }: ChatMessageBubbleProps) => {
  const isUser = message.role === "user";

  // Safely extract source labels from unknown[] payload
  const sourceLabels = message.sources
    .map((source, index) => {
      if (!source || typeof source !== "object") return null;
      
      const payload = source as Record<string, unknown>;
      const filePath = payload.file_path as string | undefined;
      const title = payload.title as string | undefined;
      const label = filePath ?? title ?? "source";
      
      // Truncate long labels
      const truncated = label.length > 40 ? `${label.slice(0, 37)}...` : label;
      return { key: index, label: truncated };
    })
    .filter((item): item is { key: number; label: string } => item !== null);

  return (
    <div
      className={cn(
        "flex",
        isUser ? "justify-end" : "justify-start"
      )}
    >
      <div
        className={cn(
          "max-w-[85%] rounded-lg px-4 py-3",
          isUser
            ? "bg-primary text-primary-foreground"
            : "bg-muted text-foreground"
        )}
      >
        <div className={cn(isUser && "[&_.prose]:text-primary-foreground")}>
          <MarkdownReportView markdown={message.content} />
        </div>
        
        {sourceLabels.length > 0 && (
          <div className="mt-3 pt-2 border-t border-current/10 flex flex-wrap gap-1.5">
            <span className="text-xs font-medium opacity-70 mr-1">Sources:</span>
            {sourceLabels.map(({ key, label }) => (
              <Badge
                key={key}
                variant="outline"
                className={cn(
                  "text-xs",
                  isUser
                    ? "border-primary-foreground/30 text-primary-foreground"
                    : "border-muted-foreground/30 text-muted-foreground"
                )}
              >
                {label}
              </Badge>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default ChatMessageBubble;
