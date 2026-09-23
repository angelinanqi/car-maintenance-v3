"use client";

import { useEffect, useRef, useState } from "react";
import { Badge, Box, Button, Dialog, Field, Flex, Heading, NativeSelect, Spinner, Stack, Text, Textarea } from "@chakra-ui/react";
import AdminLayout from "@/components/layouts/AdminLayout";
import ChatMessage from "@/components/chatbot/ChatMessage";
import { chatScopes, createMockReply } from "@/components/chatbot/mockChat";

export default function ChatbotPage() {
  const [selectedScope, setSelectedScope] = useState("general");
  const [session, setSession] = useState(null);
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState(false);
  const [confirmation, setConfirmation] = useState(null);
  const replyTimer = useRef(null);
  const conversation = useRef(null);
  const input = useRef(null);
  const cancelButton = useRef(null);
  const scope = session ? session.scope : selectedScope;
  const scopeLabel = chatScopes.find((item) => item.value === scope).label;

  useEffect(() => () => clearTimeout(replyTimer.current), []);

  useEffect(() => {
    if (conversation.current) {
      conversation.current.scrollTop = conversation.current.scrollHeight;
    }
  }, [session, pending]);

  function startChat(nextScope) {
    clearTimeout(replyTimer.current);
    replyTimer.current = null;
    setPending(false);
    setDraft("");
    setSelectedScope(nextScope);
    setSession({ id: crypto.randomUUID(), scope: nextScope, messages: [] });
    setConfirmation(null);
  }

  function requestNewChat(nextScope) {
    if (session.messages.length > 0 || draft.trim()) {
      setConfirmation({ scope: nextScope });
    } else {
      startChat(nextScope);
    }
  }

  function sendMessage(event) {
    event.preventDefault();
    const answer = draft.trim();
    if (!answer || pending || replyTimer.current !== null) return;

    const sessionId = session.id;
    setSession((current) => ({ ...current, messages: [...current.messages, { id: crypto.randomUUID(), role: "user", answer }] }));
    setDraft("");
    setPending(true);
    input.current?.focus();

    // A short local delay previews the loading state. No network request is made.
    replyTimer.current = setTimeout(() => {
      const reply = { ...createMockReply(session.scope), id: crypto.randomUUID() };
      setSession((current) => current?.id === sessionId
        ? { ...current, messages: [...current.messages, reply] }
        : current);
      replyTimer.current = null;
      setPending(false);
    }, 700);
  }

  const scopeSelector = (
    <Field.Root maxW={{ base: "100%", md: "260px" }}>
      <Field.Label htmlFor="chat-scope">Vehicle / Chat Scope</Field.Label>
      <NativeSelect.Root bg="white">
        <NativeSelect.Field id="chat-scope" value={scope} onChange={(event) => {
          const nextScope = event.target.value;
          if (nextScope === scope) return;
          if (session) requestNewChat(nextScope);
          else setSelectedScope(nextScope);
        }}>
          {chatScopes.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
        </NativeSelect.Field>
        <NativeSelect.Indicator />
      </NativeSelect.Root>
    </Field.Root>
  );

  return (
    <AdminLayout title="Chatbot Preview" description="Preview the chatbot experience with a local sample conversation.">
      <Flex gap={2} wrap="wrap" align="center" mb={4} fontSize="xs" color="gray.600">
        <Text>Vehicle: {scopeLabel}</Text>
        <Badge colorPalette="green" variant="subtle">Knowledge: Ready (mock)</Badge>
        <Badge variant="outline">Mock responses</Badge>
      </Flex>

      {!session ? (
        <Box bg="white" borderWidth="1px" borderColor="gray.200" borderRadius="lg" p={{ base: 6, md: 10 }}>
          <Stack maxW="480px" mx="auto" gap={5} py={{ base: 4, md: 10 }} align="start">
            <Heading size="lg">Try a conversation</Heading>
            <Text color="gray.600" fontSize="sm">Choose a vehicle model to preview its chat experience, or select General for a chat without a specific vehicle.</Text>
            {scopeSelector}
            <Button colorPalette="blue" onClick={() => startChat(selectedScope)}>Start Chat</Button>
            <Text fontSize="xs" color="gray.500">Replies are sample text. Conversations stay in this page and are cleared when you leave or reload.</Text>
          </Stack>
        </Box>
      ) : (
        <Flex direction="column" h="min(720px, 80dvh)" minH="400px" bg="white" borderWidth="1px" borderColor="gray.200" borderRadius="lg" overflow="hidden">
          <Flex p={4} gap={3} align="end" justify="space-between" wrap="wrap" borderBottomWidth="1px" borderColor="gray.200" flexShrink={0}>
            {scopeSelector}
            <Button variant="outline" onClick={() => requestNewChat(session.scope)}>New chat</Button>
          </Flex>

          <Stack ref={conversation} role="log" aria-label="Conversation" aria-live="polite" tabIndex={0}
            flex={1} minH={0} overflowY="auto" overscrollBehavior="contain" p={{ base: 3, md: 5 }} gap={4} bg="gray.50">
            {session.messages.length === 0 && (
              <Box p={4}>
                <Heading size="md" mb={2}>How can I help?</Heading>
                <Text fontSize="sm" color="gray.600">{session.scope === "general" ? "Ask a general vehicle question." : `Ask a question about the ${scopeLabel}.`} This preview uses mock replies.</Text>
              </Box>
            )}
            {session.messages.map((message) => <ChatMessage key={message.id} message={message} />)}
            {pending && <Flex align="center" gap={2} color="gray.600"><Spinner size="sm" /><Text fontSize="sm">Preparing mock reply…</Text></Flex>}
          </Stack>

          <Box as="form" onSubmit={sendMessage} p={4} borderTopWidth="1px" borderColor="gray.200" flexShrink={0}>
            <Flex gap={2} align="end">
              <Field.Root flex={1} minW={0}>
                <Field.Label htmlFor="chat-message">Message</Field.Label>
                <Textarea ref={input} id="chat-message" value={draft} onChange={(event) => setDraft(event.target.value)}
                  placeholder="Ask a vehicle question…" rows={2} resize="none" maxLength={4000}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
                      event.preventDefault();
                      sendMessage(event);
                    }
                  }} />
              </Field.Root>
              <Button type="submit" colorPalette="blue" disabled={pending || !draft.trim()}>Send</Button>
            </Flex>
            <Text fontSize="xs" color="gray.500" mt={2}>Enter to send · Shift + Enter for a new line · Mock preview</Text>
          </Box>
        </Flex>
      )}

      <Dialog.Root open={confirmation !== null} onOpenChange={(event) => !event.open && setConfirmation(null)} initialFocusEl={() => cancelButton.current}>
        <Dialog.Backdrop />
        <Dialog.Positioner p={4}>
          <Dialog.Content>
            <Dialog.Header><Dialog.Title>Start a new chat?</Dialog.Title></Dialog.Header>
            <Dialog.Body>
              <Text fontSize="sm" color="gray.600">
                {confirmation?.scope !== scope ? `Changing to ${chatScopes.find((item) => item.value === confirmation?.scope)?.label} starts a new chat.` : "Start a fresh conversation with the same scope."}
                {" "}The current messages and any unsent draft will be cleared.
              </Text>
            </Dialog.Body>
            <Dialog.Footer>
              <Button ref={cancelButton} variant="outline" onClick={() => setConfirmation(null)}>Cancel</Button>
              <Button colorPalette="blue" onClick={() => startChat(confirmation.scope)}>Start new chat</Button>
            </Dialog.Footer>
          </Dialog.Content>
        </Dialog.Positioner>
      </Dialog.Root>
    </AdminLayout>
  );
}
