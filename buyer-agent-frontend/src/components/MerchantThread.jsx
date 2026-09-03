import React, { useState } from "react";

export default function MerchantThread({ thread }) {
  const [open, setOpen] = useState(false);
  const lastStatus = [...thread.transcript].reverse().find((t) => t.status)?.status;

  return (
    <div className="ticket">
      <button className="ticket__row" onClick={() => setOpen((v) => !v)}>
        <span className={`ticket__caret ${open ? "open" : ""}`}>▸</span>
        <span className="ticket__shop">{thread.shopName}</span>
        <span>conv</span>
        {lastStatus && <span className={`status-pill ${lastStatus}`}>{lastStatus}</span>}
      </button>
      {open && (
        <div className="ticket__body">
          {thread.transcript.map((line, i) => (
            <div key={i} className={`ticket__line ${line.direction}`}>
              <span className="dir">{line.direction === "sent" ? "buyer →" : "shop →"}</span>
              {line.text}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
