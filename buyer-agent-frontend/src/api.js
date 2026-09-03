const BASE_URL = import.meta.env.VITE_BUYER_AGENT_URL || "http://localhost:8010";

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      /* no JSON body */
    }
    throw new Error(detail);
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  // Chat - talks to /buyer/chat only. Never touches registry data.
  sendMessage: (message, chatId) =>
    request("/buyer/chat", {
      method: "POST",
      body: JSON.stringify({ message, chatId: chatId || undefined }),
    }),
  listChats: () => request("/buyer/chats"),
  getChat: (chatId) => request(`/buyer/chats/${chatId}`),
  renameChat: (chatId, title) =>
    request(`/buyer/chats/${chatId}`, {
      method: "PATCH",
      body: JSON.stringify({ title }),
    }),
  deleteChat: (chatId) => request(`/buyer/chats/${chatId}`, { method: "DELETE" }),

  // Registry - completely separate surface, never returns conversation data.
  listMerchants: () => request("/registry"),
  addMerchant: (manifest) =>
    request("/registry", { method: "POST", body: JSON.stringify(manifest) }),
  deleteMerchant: (id) => request(`/registry/${id}`, { method: "DELETE" }),
};
