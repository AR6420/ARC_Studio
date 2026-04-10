/**
 * Agent interview — minimalist chat modal.
 *
 * Terminal-styled message log with user messages right-aligned and
 * agent messages left-aligned. No avatars, no bubbles — distinction
 * comes from alignment and a small prefix glyph.
 */

import { useEffect, useRef, useState } from 'react';
import { Loader2, Send } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
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
  'Would you share this with peers?',
  'What are your biggest concerns?',
];

function MessageRow({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user';
  return (
    <div
      className={cn(
        'flex flex-col gap-0.5',
        isUser ? 'items-end' : 'items-start',
      )}
    >
      <span
        className={cn(
          'font-mono text-[0.54rem] tracking-[0.12em] uppercase',
          isUser ? 'text-primary/70' : 'text-mirofish/70',
        )}
      >
        {isUser ? 'you' : 'agent'}
      </span>
      <p
        className={cn(
          'max-w-[85%] px-3 py-2 text-[0.82rem] leading-relaxed',
          isUser
            ? 'border-l border-primary/40 text-foreground/90'
            : 'border-l border-mirofish/40 text-foreground/80',
        )}
      >
        {message.content}
      </p>
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

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  useEffect(() => {
    if (!open) {
      setInput('');
      clearHistory();
    }
  }, [open, clearHistory]);

  function handleSend() {
    const trimmed = input.trim();
    if (!trimmed || isLoading) return;
    sendMessage(trimmed);
    setInput('');
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[80vh] flex-col gap-0 sm:max-w-lg">
        <DialogHeader className="pb-3">
          <DialogTitle className="font-mono text-[0.72rem] tracking-[0.08em] uppercase">
            <span className="text-muted-foreground/60">interview ·</span>{' '}
            <span className="text-foreground">{agentName}</span>
          </DialogTitle>
          <DialogDescription className="text-[0.72rem] text-muted-foreground/65">
            Chat with this simulated MiroFish agent to probe their reasoning.
          </DialogDescription>
        </DialogHeader>

        <div
          ref={scrollRef}
          className="flex min-h-[260px] flex-1 flex-col gap-4 overflow-y-auto border-t border-b border-border px-1 py-4"
        >
          {messages.length === 0 && !isLoading && (
            <div className="flex flex-1 flex-col items-center justify-center gap-4 text-center">
              <span className="font-mono text-[0.62rem] tracking-[0.12em] text-muted-foreground/60 uppercase">
                start a conversation
              </span>
              <div className="flex flex-col gap-1.5">
                {SUGGESTED_PROMPTS.map((prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    onClick={() => sendMessage(prompt)}
                    className="border border-border px-3 py-1.5 text-left text-[0.74rem] text-muted-foreground/80 transition-colors hover:border-primary/40 hover:text-foreground"
                  >
                    › {prompt}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, idx) => (
            <MessageRow key={idx} message={msg} />
          ))}

          {isLoading && (
            <div className="flex items-start gap-2">
              <span className="font-mono text-[0.54rem] tracking-[0.12em] uppercase text-mirofish/70">
                agent
              </span>
              <Loader2 className="mt-0.5 size-3 animate-spin text-muted-foreground" />
            </div>
          )}
        </div>

        <div className="flex items-center gap-2 pt-3">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="message…"
            disabled={isLoading}
            className="h-8 flex-1 border border-input bg-sidebar px-2.5 font-mono text-[0.78rem] text-foreground placeholder:text-muted-foreground/50 focus:border-primary/60 focus:outline-none disabled:opacity-40"
          />
          <Button
            size="icon-sm"
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
            className="shrink-0"
          >
            <Send className="size-3" />
            <span className="sr-only">Send</span>
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
