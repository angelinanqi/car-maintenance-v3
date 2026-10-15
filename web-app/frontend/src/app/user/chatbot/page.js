"use client";

import { useEffect, useRef, useState } from "react";
import {
  Badge,
  Box,
  Button,
  Dialog,
  Field,
  Flex,
  Heading,
  NativeSelect,
  Spinner,
  Stack,
  Text,
  Textarea,
} from "@chakra-ui/react";
import AdminLayout from "@/components/layouts/AdminLayout";
import ChatMessage from "@/components/chatbot/ChatMessage";
import { CHAT_MAX_MESSAGE_LENGTH as DEFAULT_MESSAGE_LIMIT } from "@/lib/config.mjs";
import { sendChatMessage } from "@/lib/chatApi.mjs";
import { useContent } from "@/components/ContentProvider";
import NextLink from "next/link";

export default function ChatbotPage() {
  const { documents, configuration, loading, refresh } = useContent();
  const chatOption = (configuration?.knowledge_scopes || []).map((scope) => ({
    ...scope, value: `${scope.scope_type}:${scope.scope_id}`, disabled: !scope.available,
  }));
  const CHAT_MAX_MESSAGE_LENGTH = configuration?.chat_max_message_length || DEFAULT_MESSAGE_LIMIT;
  const [selectedScope, setSelectedScope] = useState("");
  const [session, setSession] = useState(null);
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState(false);
  const [confirmation, setConfirmation] = useState(null);
  const [error, setError] = useState("");
  const [failedRequest, setFailedRequest] = useState(null);
  const activeRequest = useRef(null);
  const conversation = useRef(null);
  const input = useRef(null);
  const cancelButton = useRef(null);
  const option = session ? session.option : selectedScope;
  const optionLabel = chatOption.find((item) => item.value === option)?.label || option;

  useEffect(() => () => activeRequest.current?.abort(), []);

  useEffect(() => {
    if (conversation.current) {
      conversation.current.scrollTop = conversation.current.scrollHeight;
    }
  }, [session, pending]);

  function startChat(nextScope) {
    if (!chatOption.some((item) => item.value === nextScope && !item.disabled)) return;
    activeRequest.current?.abort();
    activeRequest.current = null;
    setError("");
    setFailedRequest(null);
    setPending(false);
    setDraft("");
    setSelectedScope(nextScope);
    setSession({ id: crypto.randomUUID(), option: nextScope, messages: [] });
    setConfirmation(null);
  }

  function requestNewChat(nextScope) {
    if (session.messages.length > 0 || draft.trim()) {
      setConfirmation({ option: nextScope });
    } else {
      startChat(nextScope);
    }
  }

  async function sendMessage(event, retry = null) {
    event.preventDefault();
    const answer = retry ? retry.message : draft.trim();
    if (
      !session ||
      !answer ||
      answer.length > CHAT_MAX_MESSAGE_LENGTH ||
      pending ||
      activeRequest.current !== null
    )
      return;

    const sessionId = session.id;
    const controller = new AbortController();
    activeRequest.current = controller;
    setError("");
    const payload = retry || {
      message: answer,
      scope_type: session.option.split(":")[0],
      scope_id: session.option.split(":")[1],
      ...(session.serverId ? { session_id: session.serverId, session_token: session.token } : {}),
    };
    const messageId = retry ? failedRequest.messageId : crypto.randomUUID();
    setFailedRequest(null);
    if (!retry) {
      setSession((current) => ({
        ...current,
        messages: [
          ...current.messages,
          { id: messageId, role: "user", answer },
        ],
      }));
      setDraft("");
    }
    setPending(true);
    input.current?.focus();

    try {
      const result = await sendChatMessage(payload, controller.signal);
      const reply = { ...result, role: "assistant", id: crypto.randomUUID() };
      setSession((current) =>
        current?.id === sessionId
          ? {
              ...current,
              serverId: result.session_id,
              token: result.session_token,
              messages: [
                ...current.messages.map((message) =>
                  message.id === messageId
                    ? { ...message, failed: false }
                    : message,
                ),
                reply,
              ],
            }
          : current,
      );
    } catch (failure) {
      if (!controller.signal.aborted && activeRequest.current === controller) {
        setFailedRequest({ payload, messageId });
        setSession((current) =>
          current?.id === sessionId
            ? {
                ...current,
                messages: current.messages.map((message) =>
                  message.id === messageId
                    ? { ...message, failed: true }
                    : message,
                ),
              }
            : current,
        );
        setError(
          failure instanceof TypeError
            ? "Could not reach the chatbot. Make sure the backend is running and try again."
            : failure.message,
        );
      }
    } finally {
      if (activeRequest.current === controller) {
        activeRequest.current = null;
        setPending(false);
      }
    }
  }

  const optionSelector = (
    <Field.Root maxW={{ base: "100%", md: "260px" }}>
      <Field.Label htmlFor="chat-option">Vehicle / Category</Field.Label>
      <NativeSelect.Root bg="white">
        <NativeSelect.Field
          id="chat-option"
          value={option}
          onChange={(event) => {
            const nextScope = event.target.value;
            if (nextScope === option) return;
            if (session) requestNewChat(nextScope);
            else setSelectedScope(nextScope);
          }}
        >
          <option value="" disabled>Select a published knowledge scope</option>
          {chatOption.map((item) => (
            <option
              key={item.value}
              value={item.value}
              disabled={item.disabled}
            >
              {item.label}{item.disabled ? " (no indexed documents)" : ""}
            </option>
          ))}
        </NativeSelect.Field>
        <NativeSelect.Indicator />
      </NativeSelect.Root>
    </Field.Root>
  );

  return (
    <AdminLayout
      title="Chatbot Testing"
      description="Ask questions using the existing manuals and related videos."
    >
      <Flex
        gap={2}
        wrap="wrap"
        align="center"
        mb={4}
        fontSize="xs"
        color="gray.600"
      >
        <Text>Scope: {optionLabel || "Select a vehicle or category"}</Text>
        <Badge variant="outline">RAG chat preview</Badge>
      </Flex>
      <Text fontSize="sm" color="gray.600" mb={4}>
        {
          documents.filter((document) => document.status === "processed" && document.indexed_revision)
            .length
        }{" "}
        documents have confirmed indexing.{" "}
        <NextLink href="/user/kb" style={{ textDecoration: "underline" }}>
          Manage documents
        </NextLink>
      </Text>

      {configuration?.rag_configured === false && <Text role="status" mb={4} color="orange.700">
        This backend has no RAG service connection configured. Test requests use the real backend and report its response. Check RAG_SERVICE_URL and RAG_SERVICE_TOKEN on the backend.
      </Text>}
      <Text fontSize="xs" color="gray.600" mb={3}>
        AI guidance is for learning and reference and may be incomplete or incorrect.
        Confirm repairs and specifications with a qualified mechanic.
      </Text>
      <Button mb={4} variant="outline" onClick={() => refresh({ documentsOnly: true })}>Refresh scopes and processing status</Button>
      {!loading && !chatOption.some((item) => !item.disabled) && <Text role="status" mb={4}>No supported scope is currently available. Publish a vehicle or category scope and add a published reference document, learning guide, or reviewed emergency protocol, then refresh.</Text>}

      {!session ? (
        <Box
          bg="white"
          borderWidth="1px"
          borderColor="gray.200"
          borderRadius="lg"
          p={{ base: 6, md: 10 }}
        >
          <Stack
            maxW="480px"
            mx="auto"
            gap={5}
            py={{ base: 4, md: 10 }}
            align="start"
          >
            <Heading size="lg">Try a conversation</Heading>
            <Text color="gray.600" fontSize="sm">
              Choose a published vehicle or category. The chatbot searches only
              assigned reference documents and videos, published learning guides,
              and reviewed emergency protocols available in that scope.
            </Text>
            {optionSelector}
            <Button
              colorPalette="blue"
              disabled={!chatOption.some((item) => item.value === selectedScope && !item.disabled)}
              onClick={() => startChat(selectedScope)}
            >
              Start Chat
            </Button>
            <Text fontSize="xs" color="gray.500">
              Changing the knowledge scope starts a new conversation. Refresh
              this page to load newly published scopes.
            </Text>
          </Stack>
        </Box>
      ) : (
        <Flex
          direction="column"
          h="min(720px, 80dvh)"
          minH="400px"
          bg="white"
          borderWidth="1px"
          borderColor="gray.200"
          borderRadius="lg"
          overflow="hidden"
        >
          <Flex
            p={4}
            gap={3}
            align="end"
            justify="space-between"
            wrap="wrap"
            borderBottomWidth="1px"
            borderColor="gray.200"
            flexShrink={0}
          >
            {optionSelector}
            <Button
              variant="outline"
              onClick={() => requestNewChat(session.option)}
            >
              New chat
            </Button>
          </Flex>

          <Stack
            ref={conversation}
            role="log"
            aria-label="Conversation"
            aria-live="polite"
            tabIndex={0}
            flex={1}
            minH={0}
            overflowY="auto"
            overscrollBehavior="contain"
            p={{ base: 3, md: 5 }}
            gap={4}
            bg="gray.50"
          >
            {session.messages.length === 0 && (
              <Box p={4}>
                <Heading size="md" mb={2}>
                  How can I help?
                </Heading>
                <Text fontSize="sm" color="gray.600">
                  {session.option === "general"
                    ? "Ask a general vehicle question."
                    : `Ask a question about the ${optionLabel}.`}
                </Text>
              </Box>
            )}
            {session.messages.map((message) => (
              <ChatMessage key={message.id} message={message} />
            ))}
            {pending && (
              <Flex align="center" gap={2} color="gray.600">
                <Spinner size="sm" />
                <Text fontSize="sm">Preparing answer…</Text>
              </Flex>
            )}
            {error && (
              <Text role="alert" color="red.700" fontSize="sm">
                {error}
              </Text>
            )}
            {failedRequest && (
              <Button
                alignSelf="start"
                variant="outline"
                disabled={pending}
                onClick={(event) => sendMessage(event, failedRequest.payload)}
              >
                Retry failed message
              </Button>
            )}
          </Stack>

          <Box
            as="form"
            onSubmit={sendMessage}
            p={4}
            borderTopWidth="1px"
            borderColor="gray.200"
            flexShrink={0}
          >
            <Flex gap={2} align="end">
              <Field.Root flex={1} minW={0}>
                <Field.Label htmlFor="chat-message">Message</Field.Label>
                <Textarea
                  ref={input}
                  id="chat-message"
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  placeholder="Ask a vehicle question…"
                  rows={2}
                  resize="none"
                  maxLength={CHAT_MAX_MESSAGE_LENGTH}
                  onKeyDown={(event) => {
                    if (
                      event.key === "Enter" &&
                      !event.shiftKey &&
                      !event.nativeEvent.isComposing
                    ) {
                      event.preventDefault();
                      sendMessage(event);
                    }
                  }}
                />
              </Field.Root>
              <Button
                type="submit"
                colorPalette="blue"
                disabled={pending || !draft.trim()}
              >
                Send
              </Button>
            </Flex>
            <Text fontSize="xs" color="gray.500" mt={2}>
              Enter to send · Shift + Enter for a new line
            </Text>
          </Box>
        </Flex>
      )}

      <Dialog.Root
        open={confirmation !== null}
        onOpenChange={(event) => !event.open && setConfirmation(null)}
        initialFocusEl={() => cancelButton.current}
      >
        <Dialog.Backdrop />
        <Dialog.Positioner p={4}>
          <Dialog.Content>
            <Dialog.Header>
              <Dialog.Title>Start a new chat?</Dialog.Title>
            </Dialog.Header>
            <Dialog.Body>
              <Text fontSize="sm" color="gray.600">
                {confirmation?.option !== option
                  ? `Changing to ${chatOption.find((item) => item.value === confirmation?.option)?.label} starts a new chat.`
                  : "Start a fresh conversation with the same option."}{" "}
                The current messages and any unsent draft will be cleared.
              </Text>
            </Dialog.Body>
            <Dialog.Footer>
              <Button
                ref={cancelButton}
                variant="outline"
                onClick={() => setConfirmation(null)}
              >
                Cancel
              </Button>
              <Button
                colorPalette="blue"
                onClick={() => startChat(confirmation.option)}
              >
                Start new chat
              </Button>
            </Dialog.Footer>
          </Dialog.Content>
        </Dialog.Positioner>
      </Dialog.Root>
    </AdminLayout>
  );
}
