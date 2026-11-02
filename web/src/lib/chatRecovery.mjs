export function recoveryKey(owner, vehicleId) {
  return `roadie-chat:${owner}:${vehicleId || 'general'}`;
}

export function newChatSession() {
  return { id: crypto.randomUUID(), token: crypto.randomUUID() + crypto.randomUUID(), created: false, messages: [] };
}

export function readChatRecovery(storage, key) {
  const raw = storage.getItem(key);
  if (!raw) return null;
  const value = JSON.parse(raw);
  if (value.cleared === true) return null;
  if (typeof value.session_id !== 'string' || !value.session_id) throw new Error('The saved conversation could not be read. Start a new conversation to reset its device reference.');
  if (value.pending && (value.pending.session_id !== value.session_id || typeof value.pending.request_id !== 'string' || typeof value.pending.message !== 'string')) {
    throw new Error('The pending question could not be read. Its recovery data has been kept.');
  }
  return value;
}

export function writeChatRecovery(storage, key, sessionId, pending = null) {
  const request = pending ? { ...pending } : null;
  if (request) delete request.session_token;
  storage.setItem(key, JSON.stringify({ session_id: sessionId, ...(request ? { pending: request } : {}) }));
}

export function restoredChat(data, pending = null) {
  if (!data?.session_id || !data.session_token || !Array.isArray(data.messages)) throw new Error('The restored conversation is invalid. Retry restoring.');
  const messages = data.messages.map(message => message.role === 'assistant'
    ? { ...message.reply, id: message.id, role: 'assistant', answer: message.content }
    : { id: message.id, role: 'user', answer: message.content });
  const unfinished = pending && !messages.some(message => message.id === pending.request_id);
  if (unfinished) messages.push({ id: pending.request_id + ':user', role: 'user', answer: pending.message });
  return { session: { id: data.session_id, token: data.session_token, created: true, messages },
    pending: unfinished ? { ...pending, session_token: data.session_token } : null };
}
