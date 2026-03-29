/**
 * Agent interview modal dialog (per D-05).
 *
 * Chat interface inside a shadcn Dialog that lets users converse with
 * individual simulated agents. Messages are proxied through the
 * orchestrator to the MiroFish agent chat API.
 *
 * Design per D-07: premium chat interface with distinct user/agent bubbles.
 */

import { useEffect, useRef, useState } from 'react';
import { Loader2, Send, User, Bot } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { useAgentChat } from '@/hooks/use-agent-chat';
import type { ChatMessage } from '@/hooks/use-agent-chat';

interface AgentInterviewProps {
  campaignId: string;
  agentId: string;
  agentName: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const SUGGESTED_PROMPTS = [
  'What did you think about this content?',
  'Would you share this with others?',
  'What concerns do you have?',
];

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user';

  return (
    <div
      className={`flex gap-2.5 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}
    >
      {/* Avatar */}
      <div
        className={`flex size-7 shrink-0 items-center justify-center rounded-full ${
          isUser
            ? 'bg-primary text-primary-foreground'
            : 'bg-muted ring-1 ring-foreground/10'
        }`}
      >
        {isUser ? <User className="size-3.5" /> : <Bot className="size-3.5" />}
      </div>

      {/* Bubble */}
      <div
        className={`max-w-[80%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed ${
          isUser
            ? 'rounded-br-md bg-primary text-primary-foreground'
            : 'rounded-bl-md bg-muted text-foreground ring-1 ring-foreground/5'
        }`}
      >
        {message.content}
      </div>
    </div>
  );
}

export function AgentInterview({
  campaignId,
  agentId,
  agentName,
  open,
  onOpenChange,
}: AgentInterviewProps) {
  const { messages, sendMessage, clearHistory, isLoading } = useAgentChat(
    campaignId,
    agentId,
  );
  const [input, setInput] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  // Clear state when dialog closes
  useEffect(() => {
    if (!open) {
      setInput('');
      clearHistory();
    }
  }, [open, clearHistory]);

  const handleSend = () => {
    const trimmed = input.trim();
    if (!trimmed || isLoading) return;
    sendMessage(trimmed);
    setInput('');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[80vh] flex-col gap-0 sm:max-w-lg">
        <DialogHeader className="pb-3">
          <DialogTitle className="flex items-center gap-2">
            <Bot className="size-4 text-primary" />
            Interview: {agentName}
          </DialogTitle>
          <DialogDescription>
            Chat with this simulated agent to explore their perspective on the
            content.
          </DialogDescription>
        </DialogHeader>

        {/* Message area */}
        <div
          ref={scrollRef}
          className="flex min-h-[240px] flex-1 flex-col gap-3 overflow-y-auto border-t border-b border-foreground/5 px-1 py-4"
        >
          {messages.length === 0 && !isLoading && (
            <div className="flex flex-1 flex-col items-center justify-center gap-4 text-center">
              <div className="flex size-12 items-center justify-center rounded-full bg-muted">
                <Bot className="size-6 text-muted-foreground" />
              </div>
              <div className="space-y-1.5">
                <p className="text-sm font-medium text-foreground">
                  Start a conversation
                </p>
                <p className="text-xs text-muted-foreground">
                  Ask the agent about their reactions to the content.
                </p>
              </div>
              <div className="flex flex-wrap justify-center gap-2">
                {SUGGESTED_PROMPTS.map((prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    onClick={() => sendMessage(prompt)}
                    className="rounded-full border border-foreground/10 bg-muted/50 px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, idx) => (
            <MessageBubble key={idx} message={msg} />
          ))}

          {isLoading && (
            <div className="flex gap-2.5">
              <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-muted ring-1 ring-foreground/10">
                <Bot className="size-3.5" />
              </div>
              <div className="flex items-center gap-1.5 rounded-2xl rounded-bl-md bg-muted px-3.5 py-2.5 ring-1 ring-foreground/5">
                <Loader2 className="size-3.5 animate-spin text-muted-foreground" />
                <span className="text-xs text-muted-foreground">
                  Thinking...
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Input area */}
        <div className="flex items-center gap-2 pt-3">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type your message..."
            disabled={isLoading}
            className="flex-1 rounded-lg border border-foreground/10 bg-muted/50 px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground/60 focus:border-primary/50 focus:outline-none focus:ring-2 focus:ring-primary/20 disabled:opacity-50"
          />
          <Button
            size="icon-sm"
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
            className="shrink-0"
          >
            <Send className="size-3.5" />
            <span className="sr-only">Send</span>
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
