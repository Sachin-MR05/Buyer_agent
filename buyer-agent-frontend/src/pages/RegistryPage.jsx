import React, { useEffect, useState } from "react";
import { api } from "../api.js";

const emptyForm = { shopName: "", description: "", agentUrl: "", authToken: "", contactPhone: "" };

export default function RegistryPage() {
  const [merchants, setMerchants] = useState([]);
  const [paste, setPaste] = useState("");
  const [form, setForm] = useState(emptyForm);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);

  function refresh() {
    api.listMerchants().then(setMerchants).catch(() => {});
  }

  useEffect(refresh, []);

  function handlePaste(value) {
    setPaste(value);
    setError(null);
    try {
      const parsed = JSON.parse(value);
      setForm({
        shopName: parsed.name || "",
        description: parsed.description || "",
        agentUrl: parsed.agentUrl || "",
        authToken: parsed.authToken || "",
        contactPhone: parsed.contactPhone || "",
      });
    } catch {
      // Not valid JSON yet (still typing/pasting) - leave the form as-is.
    }
  }

  function updateField(key, value) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function handleSave(e) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await api.addMerchant({
        name: form.shopName,
        description: form.description,
        agentUrl: form.agentUrl,
        authToken: form.authToken,
        contactPhone: form.contactPhone || undefined,
      });
      setForm(emptyForm);
      setPaste("");
      refresh();
    } catch (err) {
      setError(err.message || "Could not save this merchant.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id) {
    await api.deleteMerchant(id);
    refresh();
  }

  return (
    <div className="registry-page">
      <div className="registry-page__inner">
        <div>
          <h1>Merchant Registry</h1>
          <p className="registry-page__sub">
            Shops your buyer agent can contact. Paste a shop's agent manifest, or fill the fields by hand.
          </p>
        </div>

        <form className="panel" onSubmit={handleSave}>
          <h2>Add merchant</h2>
          <textarea
            className="paste-box"
            placeholder={`{ "name": "TechHaven India", "description": "...", "agentUrl": "https://.../agent/message", "authToken": "Bearer ...", "contactPhone": "+91 ..." }`}
            value={paste}
            onChange={(e) => handlePaste(e.target.value)}
          />
          <div className="paste-hint">Paste the manifest from the shop's agent info page - the fields below fill in automatically.</div>

          <div className="form-grid">
            <div className="field">
              <label>Shop name</label>
              <input value={form.shopName} onChange={(e) => updateField("shopName", e.target.value)} required />
            </div>
            <div className="field">
              <label>Contact phone (optional)</label>
              <input value={form.contactPhone} onChange={(e) => updateField("contactPhone", e.target.value)} />
            </div>
            <div className="field full">
              <label>Description</label>
              <input value={form.description} onChange={(e) => updateField("description", e.target.value)} />
            </div>
            <div className="field full">
              <label>Agent URL</label>
              <input value={form.agentUrl} onChange={(e) => updateField("agentUrl", e.target.value)} required />
            </div>
            <div className="field token full">
              <label>Auth token</label>
              <input
                type="password"
                value={form.authToken}
                onChange={(e) => updateField("authToken", e.target.value)}
                required
              />
            </div>
          </div>

          {error && <div className="field-error">{error}</div>}
          <button className="save-btn" type="submit" disabled={saving}>
            {saving ? "Saving…" : "Save merchant"}
          </button>
        </form>

        <div className="panel">
          <h2>Registered shops</h2>
          <div className="merchant-table">
            {merchants.length === 0 && <div className="registry-empty">No merchants registered yet.</div>}
            {merchants.map((m) => (
              <div className="merchant-row" key={m.id}>
                <div className="merchant-row__main">
                  <div className="merchant-row__name">{m.shopName}</div>
                  <div className="merchant-row__desc">{m.description}</div>
                </div>
                <div className="merchant-row__meta">
                  <span className="token-note">token stored encrypted</span>
                  {m.contactPhone && <div className="merchant-row__phone">{m.contactPhone}</div>}
                </div>
                <button className="delete-btn" onClick={() => handleDelete(m.id)}>
                  Remove
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
