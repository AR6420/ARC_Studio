/**
 * React hook for agent interview chat via the orchestrator proxy.
 *
 * Manages local chat history and uses useMutation to send messages
 * through POST /api/campaigns/{id}/agents/{agentId}/chat.
 */

import { useCallback, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { chatAgent } from '@/api/campaigns';

export interface ChatMessage {
  role: 'user' | 'agent';
  content: string;
}

export function useAgentChat(campaignId: string, agentId: string) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  const mutation = useMutation({
    mutationFn: (message: string) => chatAgent(campaignId, agentId, message),
    onSuccess: (data) => {
      setMessages((prev) => [
        ...prev,
        { role: 'agent', content: data.response },
      ]);
    },
    onError: () => {
      setMessages((prev) => [
        ...prev,
        {
          role: 'agent',
          content: 'Unable to reach agent. MiroFish may be unavailable.',
        },
      ]);
    },
  });

  const sendMessage = useCallback(
    (message: string) => {
      const trimmed = message.trim();
      if (!trimmed) return;
      setMessages((prev) => [...prev, { role: 'user', content: trimmed }]);
      mutation.mutate(trimmed);
    },
    [mutation],
  );

  const clearHistory = useCallback(() => {
    setMessages([]);
  }, []);

  return {
    messages,
    sendMessage,
    clearHistory,
    isLoading: mutation.isPending,
    error: mutation.error,
  };
}
