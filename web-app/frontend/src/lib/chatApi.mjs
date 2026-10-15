import { request } from "../api/client.mjs";

export async function sendChatMessage(payload, signal) {
  const result = await request("/chat", { method: "POST", body: payload, signal });
  if (!result || typeof result.answer !== "string" || !result.answer.trim()) {
    throw new Error(
      "The chatbot returned an empty or invalid answer. Please retry.",
    );
  }
  if (payload.scope_id && (!result.session_id || !result.session_token ||
      result.scope_id !== payload.scope_id || result.scope_type !== payload.scope_type)) {
    throw new Error("The chatbot returned an invalid session or changed scope. Start a new chat and retry.");
  }
  return result;
}
