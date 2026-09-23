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
import { chatOption } from "@/components/chatbot/chatScopes";
import { sendChatMessage } from "@/lib/chatApi.mjs";
import { usePrototype } from "@/components/PrototypeProvider";
import NextLink from "next/link";

export default function ChatbotPage() {
  const { documents } = usePrototype();
  const [selectedScope, setSelectedScope] = useState("general");
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
  const optionLabel = chatOption.find((item) => item.value === option).label;

  useEffect(() => () => activeRequest.current?.abort(), []);

  useEffect(() => {
    if (conversation.current) {
      conversation.current.scrollTop = conversation.current.scrollHeight;
    }
  }, [session, pending]);

  function startChat(nextScope) {
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
      answer.length > 4000 ||
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
      car_model: session.option,
      conversation: session.messages
        .filter((message) => !message.failed)
        .slice(-6)
        .map((message) => ({ role: message.role, content: message.answer })),
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
      <Field.Label htmlFor="chat-option">Vehicle / Chat Scope</Field.Label>
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
          {chatOption.map((item) => (
            <option
              key={item.value}
              value={item.value}
              disabled={item.disabled}
            >
              {item.label}
            </option>
          ))}
        </NativeSelect.Field>
        <NativeSelect.Indicator />
      </NativeSelect.Root>
    </Field.Root>
  );

  return (
    <AdminLayout
      title="Chatbot Preview"
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
        <Text>Vehicle: {optionLabel}</Text>
        <Badge variant="outline">RAG chat preview</Badge>
      </Flex>
      <Text fontSize="sm" color="gray.600" mb={4}>
        {
          documents.filter((document) => document.status === "Processed (demo)")
            .length
        }{" "}
        documents processed in the local demo. They are not in this chat’s real
        index.{" "}
        <NextLink href="/user/kb" style={{ textDecoration: "underline" }}>
          Manage documents
        </NextLink>
      </Text>

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
              Choose a vehicle model to preview its chat experience, or select
              General for a chat without a specific vehicle.
            </Text>
            {optionSelector}
            <Button
              colorPalette="blue"
              onClick={() => startChat(selectedScope)}
            >
              Start Chat
            </Button>
            <Text fontSize="xs" color="gray.500">
              Conversations stay in this page and are cleared when you leave or
              reload. Vehicle selection scopes the owner manual; related videos
              use the existing shared collection.
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
                  maxLength={4000}
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
