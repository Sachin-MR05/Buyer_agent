import React from "react";
import { useNavigate } from "react-router-dom";

export default function ChatSidebar({ chats, activeChatId, onNewChat, onRename, onDelete }) {
  const navigate = useNavigate();

  return (
    <aside className="chat-sidebar">
      <div className="chat-sidebar__header">
        <button className="new-chat-btn" onClick={onNewChat}>
          + New chat
        </button>
      </div>
      <div className="chat-list">
        {chats.length === 0 && <div className="chat-empty">No chats yet</div>}
        {chats.map((chat) => (
          <div key={chat.chatId} className={`chat-list__row ${chat.chatId === activeChatId ? "active" : ""}`}>
            <button className="chat-list__item" onClick={() => navigate(`/chat/${chat.chatId}`)}>
              {chat.title || "Untitled"}
            </button>
            <details className="chat-menu">
              <summary aria-label={`Options for ${chat.title || "Untitled"}`}>•••</summary>
              <div className="chat-menu__panel">
                <button onClick={() => onRename(chat.chatId, chat.title || "Untitled")}>Rename</button>
                <button className="danger" onClick={() => onDelete(chat.chatId)}>Delete</button>
              </div>
            </details>
          </div>
        ))}
      </div>
    </aside>
  );
}
