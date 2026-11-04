import { request } from "./client.mjs";

export async function sendChatMessage(payload, signal) {
  const result = await request("/chat", { method: "POST", body: payload, signal });
  if (!result || typeof result.answer !== "string" || !result.answer.trim()) {
    throw new Error(
      "The chatbot returned an empty or invalid answer. Please retry.",
    );
  }
  if (!result.session_id || !result.session_token ||
      (payload.scope_id && (result.scope_id !== payload.scope_id || result.scope_type !== payload.scope_type))) {
    throw new Error("The chatbot returned an invalid session or changed scope. Start a new chat and retry.");
  }
  if (['generation_error', 'retrieval_error'].includes(result.response_type)) {
    const error = new Error('The AI service could not complete this answer. Retry shortly.');
    error.status = 503;
    throw error;
  }
  return result;
}

export const createChatSession = (session, signal, scope = {}) => request(`/chat/sessions/${session.id}`, {
  method: 'PUT', body: { session_token: session.token, ...scope }, signal,
});
export const resumeChat = (id, { messageId, signal } = {}) => request(
  `/chat/sessions/${id}/resume${messageId ? `?message_id=${encodeURIComponent(messageId)}` : ''}`,
  { method: 'POST', body: {}, signal },
);
