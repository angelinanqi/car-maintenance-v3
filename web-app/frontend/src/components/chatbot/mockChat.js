export const chatScopes = [
  { value: "general", label: "General" },
  { value: "myvi", label: "Perodua Myvi" },
  { value: "axia", label: "Perodua Axia" },
  { value: "bezza", label: "Perodua Bezza" },
];

// Replace this function with the future API request and map its response to
// answer, videos, and external_warning. Scope belongs to the whole session.
export function createMockReply(scope) {
  const label = chatScopes.find((item) => item.value === scope).label;
  return {
    role: "assistant",
    answer: `This is a mock reply for ${label}. Your message has been received. In the connected chatbot, an answer to your question would appear here.`,
    videos: [],
    external_warning: "Preview only — this reply is sample text, not vehicle guidance.",
  };
}
