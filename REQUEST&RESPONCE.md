**USER :** 
Invoke-RestMethod -Method Post -Uri "http://localhost:8030/buyer/chat" -ContentType "application/   json" -Body '{"message": "I want to buy an iphone12 from TechHaven India"}' | ConvertTo-Json -Depth 6

**BUYER AGENT ->**:  
{
    "chatId":  "chat-f0c408c03e",
    "status":  "WAITING_FOR_USER",
    "message":  "Could you please provide the exact name of the merchant you are looking for or a category to search for an iPhone 12?",
    "messages":  [
                     {
                         "role":  "user",
                         "text":  "I want to buy an iphone12 from TechHaven India"
                     },
                     {
                         "role":  "assistant",
                         "text":  "Could you please provide the exact name of the merchant you are looking for or a category to search for an iPhone 12?"
                     }
                 ],
    "merchantThreads":  [

                        ]
}

**USER :**

d:\Buyer_agent > Invoke-RestMethod -Method Post -Uri "http://localhost:8030/buyer/chat" -ContentType "application/json" -Body '{"chatId": "chat-f0c408c03e", "message": "The shop is TechHaven India. Search for iphone12."}' | ConvertTo-Json -Depth 6

**BUYER AGENT ->:**

{
    "chatId":  "chat-f0c408c03e",
    "status":  "COMPLETED",
    "message":  "Please complete the payment at http://localhost:3000/checkout?key=rzp_test_TT9dgvW6FBwmgm\u0026order_id=order_TWq8O2DAzdtcoM\u0026amount=4500000\u0026currency=INR",
    "messages":  [
                     {
                         "role":  "user",
                         "text":  "I want to buy an iphone12 from TechHaven India"
                     },
                     {
                         "role":  "assistant",
                         "text":  "Could you please provide the exact name of the merchant you are looking for or a category to search for an iPhone 12?"
                     },
                     {
                         "role":  "user",
                         "text":  "The shop is TechHaven India. Search for iphone12."
                     },
                     {
                         "role":  "assistant",
                         "text":  "TechHaven India has an iPhone 12 for 45000 INR. Do you want to buy from them?"
                     },
                     {
                         "role":  "user",
                         "text":  "yes checkout now"
                     },
                     {
                         "role":  "assistant",
                         "text":  "Please complete the payment at http://localhost:3000/checkout?key=rzp_test_TT9dgvW6FBwmgm\u0026order_id=order_TWq8O2DAzdtcoM\u0026amount=4500000\u0026currency=INR"
                     }
                 ],
    "merchantThreads":  [
                            {
                                "merchantId":  "m-6b14d057ac",
                                "shopName":  "TechHaven India",
                                "transcript":  [
                                                   {
                                                       "direction":  "sent",
                                                       "text":  "Do you have an iPhone 12 in stock and at what price?",
                                                       "status":  null,
                                                       "ts":  "2026-09-01T22:02:45.670381+05:30"
                                                   },
                                                   {
                                                       "direction":  "received",
                                                       "text":  "The iPhone 12 is available for 45000 INR. Would you like to proceed with the purchase?",
                                                       "status":  "SUCCESS",
                                                       "ts":  "2026-09-01T22:02:45.670381+05:30"
                                                   },
                                                   {
                                                       "direction":  "sent",
                                                       "text":  "checkout iPhone 12, quantity 1",
                                                       "status":  null,
                                                       "ts":  "2026-09-01T16:33:10.641730+00:00"
                                                   },
                                                   {
                                                       "direction":  "received",
                                                       "text":  "Your order for iPhone 12 has been successfully placed. Please complete the payment at the following link: http://localhost:3000/checkout?key=rzp_test_TT9dgvW6FBwmgm\u0026order_id=order_TWq8O2DAzdtcoM\u0026amount=4500000\u0026currency=INR",
                                                       "status":  "SUCCESS",
                                                       "ts":  "2026-09-01T16:33:15.816955+00:00"
                                                   }
                                               ]
                            }
                        ]
}

Set-Content -Path "d:\Buyer_agent\REQUEST&RESPONCE.md" -Encoding UTF8 -Value @'
# System Architecture & Conversation Reference

---

## 🏪 BOX 1 — E-Commerce App + Merchant Agent

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          E-COMMERCE APP  (port 3000)                            │
│                       React Frontend — TechHaven India Store                    │
│   Products / Cart / Orders / Checkout Page (Razorpay Widget)                    │
└──────────────────────────────┬──────────────────────────────────────────────────┘
                               │  HTTP REST (JWT Bearer Token)
                               ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                     JAVA SPRING BOOT BACKEND  (port 8080)                       │
│  ┌────────────┐  ┌────────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │ /auth/**   │  │ /products  │  │  /cart/**    │  │  /orders/checkout     │  │
│  │ Register   │  │ Catalog    │  │  CartItem    │  │  verify-payment       │  │
│  │ Login/JWT  │  │ CRUD       │  │  add/remove  │  │  Razorpay integration │  │
│  └────────────┘  └────────────┘  └──────────────┘  └───────────────────────┘  │
│                                                                                  │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                    /tools/**  — Agent Tool Layer                         │   │
│  │  search_products │ get_price │ check_inventory │ add_to_cart            │   │
│  │  remove_from_cart │ update_cart │ create_order │ verify_payment         │   │
│  │  get_orders │ get_product                                                │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
│  ┌───────────────┐  ┌─────────────────┐  ┌──────────────────────────────────┐  │
│  │ PostgreSQL DB │  │ RazorpayService  │  │ SecurityConfig (Spring Security) │  │
│  │ products      │  │ createOrder()    │  │ JWT Filter + Role Auth           │  │
│  │ cart_items    │  │ verifySignature()│  │ /tools/** → permitAll            │  │
│  │ orders        │  │ createPaymentLink│  │ /orders/verify-payment → permitAll│  │
│  └───────────────┘  └─────────────────┘  └──────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────────┘
                               ▲
                               │  POST /tools/{tool}/execute
                               │  { "arguments": {...}, "context": { "userId": 1 } }
                               │
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      MERCHANT AGENT CORE  (port 8001)                           │
│                                                                                  │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │  GATEWAY  —  POST /agent/message                                         │   │
│  │  Validates: Authorization: Bearer dev-token-techhaven                    │   │
│  │  Extracts:  requestId, sessionId, userId, message, channel               │   │
│  │  Coerces:   userId "demo-user" → integer 1                               │   │
│  └────────────────────────┬─────────────────────────────────────────────────┘   │
│                           │                                                      │
│                           ▼                                                      │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │  AGENT LOOP  (LLM — NVIDIA NIM / Llama)                                  │   │
│  │  Iter 1 → search_products                                                │   │
│  │  Iter 2 → get_price + check_inventory                                    │   │
│  │  Iter 3 → add_to_cart  ← auto-clears cart first                         │   │
│  │  Iter 4 → create_order → Razorpay order + payment link                  │   │
│  │  Iter 5 → COMPLETED                                                      │   │
│  └────────────────────────┬─────────────────────────────────────────────────┘   │
│                           │                                                      │
│                           ▼                                                      │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │  EXECUTOR                                                                 │   │
│  │  • _clear_cart_for_user(userId) before every add_to_cart                 │   │
│  │  • ToolClient.execute_tool(tool, args, user_id=1)                        │   │
│  │  • Idempotency cache + audit logging                                      │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🤖 BOX 2 — Buyer Agent

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           BUYER AGENT SYSTEM                                    │
│                                                                                  │
│  ┌─────────────────────────────────────┐                                        │
│  │         USER / FRONTEND             │                                        │
│  │  React Frontend (port 5173)         │                                        │
│  │  ChatbotWidget in E-Commerce (3000) │                                        │
│  │  PowerShell / curl                  │                                        │
│  └─────────────────┬───────────────────┘                                        │
│                    │  POST /buyer/chat                                           │
│                    │  { message, chatId }                                        │
│                    ▼                                                             │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │  BUYER AGENT GATEWAY  (FastAPI — port 8030)                              │   │
│  │  routes.py:  user_id = "1"  (always — never "demo-user")                │   │
│  │  CORS:       allow_origins=["*"]                                         │   │
│  └────────────────────────┬─────────────────────────────────────────────────┘   │
│                           │                                                      │
│                           ▼                                                      │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │  BUYER AGENT CORE                                                         │   │
│  │                                                                           │   │
│  │  ┌──────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │   │
│  │  │ Planner  │→ │ BuyerAgent   │→ │  ChatStore   │  │MerchantRegistry  │  │   │
│  │  │  (LLM)   │  │  .run()      │  │ PostgreSQL   │  │ resolve URL +    │  │   │
│  │  │ Decides  │  │  Orchestrate │  │ buyer-agent  │  │ auth token       │  │   │
│  │  │ action   │  │  per turn    │  │ DB           │  └──────────────────┘  │   │
│  │  └──────────┘  └──────────────┘  └──────────────┘                        │   │
│  │                                                                           │   │
│  │  ┌──────────────────────────────────────────────────────────────────┐    │   │
│  │  │  EXECUTOR — MerchantClient.send()                                 │    │   │
│  │  │  • sanitizes userId: "demo-user" → "1"                           │    │   │
│  │  │  • adds Authorization header                                      │    │   │
│  │  └──────────────────────────────────────────────────────────────────┘    │   │
│  └────────────────────────┬─────────────────────────────────────────────────┘   │
│                           │                                                      │
│                           │  POST http://localhost:8001/agent/message           │
│                           │  Authorization: Bearer dev-token-techhaven          │
│                           │  { requestId, sessionId, userId:"1", message }      │
│                           ▼                                                      │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │           MERCHANT AGENT  (port 8001)  — see BOX 1                      │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 💬 Raw Conversation — User → Buyer Agent → Merchant Agent

### Turn 1 — User first message

**REQUEST (User → Buyer Agent)**
```powershell
Invoke-RestMethod -Method Post -Uri "http://localhost:8030/buyer/chat" `
  -ContentType "application/json" `
  -Body '{"message": "I want to buy an iphone12 from TechHaven India"}' | ConvertTo-Json -Depth 6
```

**RESPONSE (Buyer Agent → User)**
```json
{
  "chatId":  "chat-f0c408c03e",
  "status":  "WAITING_FOR_USER",
  "message": "Could you please provide the exact name of the merchant or a category?",
  "messages": [
    { "role": "user",      "text": "I want to buy an iphone12 from TechHaven India" },
    { "role": "assistant", "text": "Could you please provide the exact name of the merchant or a category?" }
  ],
  "merchantThreads": []
}
```

---

### Turn 2 — User clarifies → Buyer Agent → Merchant Agent

**REQUEST (User → Buyer Agent)**
```powershell
Invoke-RestMethod -Method Post -Uri "http://localhost:8030/buyer/chat" `
  -ContentType "application/json" `
  -Body '{"chatId": "chat-f0c408c03e", "message": "The shop is TechHaven India. Search for iphone12."}' | ConvertTo-Json -Depth 6
```

#### Buyer Agent internally sends to Merchant Agent:

**→ INQUIRY (Buyer Agent → Merchant Agent)**
```http
POST http://localhost:8001/agent/message
Authorization: Bearer dev-token-techhaven
Content-Type: application/json

{
  "requestId":  "buyer-7b488c8430",
  "sessionId":  "buyer-sess-b0643b85cb",
  "userId":     "1",
  "message":    "Do you have an iPhone 12 in stock and at what price?",
  "channel":    "api"
}
```

**← REPLY (Merchant Agent → Buyer Agent)**
```json
{
  "requestId": "buyer-7b488c8430",
  "status":    "SUCCESS",
  "message":   "The iPhone 12 is available for 45000 INR. Would you like to proceed?"
}
```

**→ CHECKOUT (Buyer Agent → Merchant Agent)**
```http
POST http://localhost:8001/agent/message
Authorization: Bearer dev-token-techhaven
Content-Type: application/json

{
  "requestId":  "buyer-3666d7023c",
  "sessionId":  "buyer-sess-b0643b85cb",
  "userId":     "1",
  "message":    "checkout iPhone 12, quantity 1",
  "channel":    "api"
}
```

**← ORDER CREATED (Merchant Agent → Buyer Agent)**
```json
{
  "requestId": "buyer-3666d7023c",
  "status":    "SUCCESS",
  "message":   "Order placed. Pay here: http://localhost:3000/checkout?key=rzp_test_TT9dgvW6FBwmgm&order_id=order_TWq8O2DAzdtcoM&amount=4500000&currency=INR"
}
```

**FINAL RESPONSE (Buyer Agent → User)**
```json
{
  "chatId":  "chat-f0c408c03e",
  "status":  "COMPLETED",
  "message": "Please complete the payment at http://localhost:3000/checkout?key=rzp_test_TT9dgvW6FBwmgm&order_id=order_TWq8O2DAzdtcoM&amount=4500000&currency=INR",
  "messages": [
    { "role": "user",      "text": "I want to buy an iphone12 from TechHaven India" },
    { "role": "assistant", "text": "Could you please provide the exact name of the merchant or a category?" },
    { "role": "user",      "text": "The shop is TechHaven India. Search for iphone12." },
    { "role": "assistant", "text": "TechHaven India has an iPhone 12 for 45000 INR. Do you want to buy?" },
    { "role": "user",      "text": "yes checkout now" },
    { "role": "assistant", "text": "Please complete the payment at http://localhost:3000/checkout?..." }
  ],
  "merchantThreads": [
    {
      "merchantId": "m-6b14d057ac",
      "shopName":   "TechHaven India",
      "transcript": [
        { "direction": "sent",     "text": "Do you have an iPhone 12 in stock and at what price?", "status": null },
        { "direction": "received", "text": "The iPhone 12 is available for 45000 INR. Would you like to proceed?", "status": "SUCCESS" },
        { "direction": "sent",     "text": "checkout iPhone 12, quantity 1", "status": null },
        { "direction": "received", "text": "Order placed. Pay here: http://localhost:3000/checkout?...", "status": "SUCCESS" }
      ]
    }
  ]
}
```

---

## 🔑 Auth Token

| What | Value | Why |
|------|-------|-----|
| Header name | `Authorization` | Standard HTTP auth header |
| Header value | `Bearer dev-token-techhaven` | Proves caller is trusted Buyer Agent |
| No token | `401 Unauthorized` | Request rejected at Merchant gateway |
| userId in body | `"1"` | Java Tool Layer uses this for cart/order operations |

```
Wrong / missing token  →  401 blocked
Correct token          →  Agent processes → tools run with userId=1
```
'@