import { useEffect, useState, useRef } from "react";
import { Loader2, Send } from "lucide-react";
import { toast } from "sonner";
import {
  listChatMessages,
  sendChatMessage,
  type ChatMessageRecord,
} from "@/lib/chatApi";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import ChatMessageBubble from "./ChatMessageBubble";

interface ChatPanelProps {
  scanId: string;
  sessionId: string | null;
}

const ChatPanel = ({ scanId, sessionId }: ChatPanelProps) => {
  const [messages, setMessages] = useState<ChatMessageRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Scroll to bottom when messages change
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  // Load messages when session changes
  useEffect(() => {
    if (!sessionId) {
      setMessages([]);
      return;
    }

    const loadMessages = async () => {
      try {
        setLoading(true);
        const data = await listChatMessages(scanId, sessionId);
        setMessages(data);
      } catch (err) {
        toast.error("Failed to load messages");
        console.error("Failed to load messages:", err);
      } finally {
        setLoading(false);
      }
    };

    loadMessages();
  }, [scanId, sessionId]);

  const handleSend = async () => {
    if (!sessionId || !input.trim() || isSending) return;

    const userContent = input.trim();
    setInput("");

    // Optimistically append user message
    const optimisticUserMessage: ChatMessageRecord = {
      id: crypto.randomUUID(),
      session_id: sessionId,
      role: "user",
      content: userContent,
      sources: [],
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, optimisticUserMessage]);
    setIsSending(true);

    try {
      // Send message and get assistant response
      const assistantMessage = await sendChatMessage(scanId, sessionId, userContent);
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      toast.error("Failed to send message. Please try again.");
      console.error("Failed to send message:", err);
      // Remove optimistic user message on error
      setMessages((prev) => prev.filter((msg) => msg.id !== optimisticUserMessage.id));
      // Restore input
      setInput(userContent);
    } finally {
      setIsSending(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  if (!sessionId) {
    return (
      <Card className="h-full">
        <CardContent className="flex items-center justify-center h-full py-12">
          <p className="text-muted-foreground">
            Select or start a conversation
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="h-full flex flex-col">
      <CardContent className="p-0 flex flex-col h-full">
        {/* Messages area */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
            </div>
          ) : messages.length === 0 ? (
            <div className="flex items-center justify-center py-8">
              <p className="text-sm text-muted-foreground">
                No messages yet — start the conversation!
              </p>
            </div>
          ) : (
            <>
              {messages.map((message) => (
                <ChatMessageBubble key={message.id} message={message} />
              ))}
              <div ref={messagesEndRef} />
            </>
          )}
        </div>

        {/* Input area */}
        <div className="border-t border-border p-4">
          <div className="flex gap-2">
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask a question about this repository..."
              disabled={isSending}
            />
            <Button
              onClick={handleSend}
              disabled={!input.trim() || isSending}
              size="icon"
            >
              {isSending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default ChatPanel;
