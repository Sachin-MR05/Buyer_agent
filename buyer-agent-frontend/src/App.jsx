import React from "react";
import { NavLink, Route, Routes, Navigate } from "react-router-dom";
import ChatPage from "./pages/ChatPage.jsx";
import RegistryPage from "./pages/RegistryPage.jsx";

export default function App() {
  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar__mark">
          buyer<span>-agent</span>
        </div>
        <nav className="topbar__nav">
          <NavLink to="/chat" className={({ isActive }) => (isActive ? "active" : "")}>
            Chat
          </NavLink>
          <NavLink to="/registry" className={({ isActive }) => (isActive ? "active" : "")}>
            Merchant Registry
          </NavLink>
        </nav>
      </header>
      <div className="main-area">
        <Routes>
          <Route path="/" element={<Navigate to="/chat" replace />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/chat/:chatId" element={<ChatPage />} />
          <Route path="/registry" element={<RegistryPage />} />
        </Routes>
      </div>
    </div>
  );
}
