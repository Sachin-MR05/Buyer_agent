import React, { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api.js";
import ChatSidebar from "../components/ChatSidebar.jsx";
import MerchantThread from "../components/MerchantThread.jsx";

function MessageContent({ text }) {
  const parts = text.split(/(https?:\/\/[^\s)]+)/g);

  return parts.map((part, index) => {
    if (!part.startsWith("http://") && !part.startsWith("https://")) {
      return <React.Fragment key={index}>{part}</React.Fragment>;
    }

    const trailingPunctuation = part.match(/[.,!?]+$/)?.[0] || "";
    const url = trailingPunctuation ? part.slice(0, -trailingPunctuation.length) : part;
    return (
      <React.Fragment key={index}>
        <a className="message-link" href={url} target="_blank" rel="noreferrer">
          Open link
        </a>
        {trailingPunctuation}
      </React.Fragment>
    );
  });
}

export default function ChatPage() {
  const { chatId } = useParams();
  const navigate = useNavigate();
  const [chats, setChats] = useState([]);
  const [messages, setMessages] = useState([]);
  const [threads, setThreads] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState(null);
  const scrollRef = useRef(null);

  useEffect(() => {
    api.listChats().then(setChats).catch(() => {});
  }, [chatId]);

  useEffect(() => {
    if (!chatId) {
      setMessages([]);
      setThreads([]);
      return;
    }
    api
      .getChat(chatId)
      .then((res) => {
        setMessages(res.messages);
        setThreads(res.merchantThreads);
      })
      .catch(() => setError("Could not load that chat."));
  }, [chatId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, sending]);

  async function handleSend(e) {
    e.preventDefault();
    const text = input.trim();
    if (!text || sending) return;

    setError(null);
    setInput("");
    setMessages((prev) => [...prev, { role: "user", text }]);
    setSending(true);

    try {
      const res = await api.sendMessage(text, chatId);
      setThreads(res.merchantThreads);
      const responseMessages = res.messages || [];
      const hasResponseMessage = responseMessages.some(
        (message) => message.role === "assistant" && message.text === res.message,
      );
      setMessages(
        hasResponseMessage || !res.message
          ? responseMessages
          : [...responseMessages, { role: "assistant", text: res.message }],
      );
      if (!chatId) {
        navigate(`/chat/${res.chatId}`, { replace: true });
        api.listChats().then(setChats).catch(() => {});
      }
    } catch (err) {
      setError(err.message || "Something went wrong reaching the buyer agent.");
    } finally {
      setSending(false);
    }
  }

  return (
    <>
      <ChatSidebar
        chats={chats}
        activeChatId={chatId}
        onNewChat={() => navigate("/chat")}
        onRename={async (id, currentTitle) => {
          const title = window.prompt("Rename chat", currentTitle || "Untitled")?.trim();
          if (!title || title === currentTitle) return;
          await api.renameChat(id, title);
          setChats(await api.listChats());
        }}
        onDelete={async (id) => {
          if (!window.confirm("Delete this chat? This cannot be undone.")) return;
          await api.deleteChat(id);
          setChats(await api.listChats());
          if (id === chatId) navigate("/chat", { replace: true });
        }}
      />
      <div className="chat-main">
        <div className="chat-scroll" ref={scrollRef}>
          <div className="chat-scroll__inner">
            {messages.length === 0 && (
              <div className="chat-empty">Ask your buyer agent to find and buy something.</div>
            )}
            {messages.map((m, i) => (
              <div key={i} className={`bubble ${m.role === "user" ? "user" : "agent"}`}>
                <MessageContent text={m.text} />
              </div>
            ))}
            {threads.length > 0 && (
              <div className="tickets">
                {threads.map((t) => (
                  <MerchantThread key={t.merchantId} thread={t} />
                ))}
              </div>
            )}
            {sending && <div className="thinking">buyer-agent is working…</div>}
            {error && <div className="bubble agent error">{error}</div>}
          </div>
        </div>
        <form className="composer" onSubmit={handleSend}>
          <div className="composer__inner">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="buy me an iphone…"
              disabled={sending}
            />
            <button type="submit" disabled={sending || !input.trim()}>
              Send
            </button>
          </div>
        </form>
      </div>
    </>
  );
}
