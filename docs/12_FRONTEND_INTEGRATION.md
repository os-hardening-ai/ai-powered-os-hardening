# 12 - Frontend Integration Guide

**AI-Powered OS Hardening API**
**Date**: 2025-12-24
**Version**: v1.0.2

---

## Table of Contents

1. [Overview](#overview)
2. [API Endpoints](#api-endpoints)
3. [Integration Examples](#integration-examples)
4. [React Integration](#react-integration)
5. [Vue.js Integration](#vuejs-integration)
6. [Vanilla JavaScript](#vanilla-javascript)
7. [SSE Streaming Client](#sse-streaming-client)
8. [Error Handling](#error-handling)
9. [Best Practices](#best-practices)

---

## Overview

This guide demonstrates how to integrate the AI-Powered OS Hardening API with various frontend frameworks. The API provides both traditional REST endpoints and Server-Sent Events (SSE) for streaming responses.

### API Base URL

```
Development: http://localhost:8000
Production: https://your-domain.com
```

### Authentication (JWT)

The API requires **JWT Bearer authentication** on all protected endpoints (`/health`,
`/docs`, `/auth/login` are public). Flow: login → receive token → send it as a Bearer header.

```javascript
// 1) Login → get token
const res = await fetch(`${API_BASE}/auth/login`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ username, password }),  // dev demo: admin / changeme123
});
const { access_token, role } = await res.json();

// 2) Use the token on every request
const headers = {
  'Authorization': `Bearer ${access_token}`,
  'Content-Type': 'application/json',
};
```

**RBAC**: the token carries a `role` (sysadmin / security / developer / end_user). Some
endpoints require specific roles (e.g. `/api/agent/harden` → security+); insufficient role → `403`.

**SSE note**: `EventSource` cannot set headers — for `/api/chat/stream` pass the token as a
query param: `/api/chat/stream?access_token=<token>` (or use `fetch` streaming with the header).

**Logout**: `POST /auth/logout` (with the Bearer header) revokes the token until it expires.

---

## API Endpoints

### 1. POST `/api/chat` - Standard Chat

**Request**:
```json
{
  "question": "Ubuntu SSH portunu nasıl değiştiririm?",
  "os": "ubuntu_24_04",
  "use_rag": true,
  "rag_top_k": 5,
  "timeout": 60
}
```

**Response**:
```json
{
  "answer": "SSH portunu değiştirmek için...",
  "intent": "action_request",
  "safety_category": "safe_defensive",
  "layer_path": "1->2->3C->4",
  "rag_sources": [...],
  "stats": {"total_time_s": 5.2},
  "request_id": "req_abc123",
  "estimated_cost": 0.0005
}
```

### 2. POST `/api/chat/stream` - Streaming Chat (SSE)

**Event Types**:
- `metadata`: Initial metadata about the request
- `message`: Token-by-token response
- `done`: Completion event with statistics

**Response Format**:
```
event: metadata
data: {"intent": "info_request", "rag_used": true}

event: message
data: {"token": "SSH "}

event: message
data: {"token": "güvenliği "}

event: done
data: {"total_tokens": 150, "total_time_s": 3.2}
```

### 3. POST `/rag/search` - RAG Only

Search CIS Benchmarks without LLM generation.

**Request**:
```json
{
  "query": "SSH hardening best practices",
  "top_k": 3
}
```

---

## Integration Examples

### React Integration

#### 1. Standard Chat (Axios)

```typescript
import axios from 'axios';
import { useState } from 'react';

interface ChatRequest {
  question: string;
  os?: string;
  use_rag?: boolean;
  timeout?: number;
}

interface ChatResponse {
  answer: string;
  intent: string;
  safety_category: string;
  layer_path: string;
  rag_sources?: Array<any>;
  stats: {
    total_time_s: number;
  };
  request_id: string;
  estimated_cost: number;
}

function ChatComponent() {
  const [question, setQuestion] = useState('');
  const [response, setResponse] = useState<ChatResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const API_BASE_URL = 'http://localhost:8000';

  const sendMessage = async () => {
    setLoading(true);
    setError(null);

    try {
      const { data } = await axios.post<ChatResponse>(
        `${API_BASE_URL}/api/chat`,
        {
          question,
          os: 'ubuntu_24_04',
          use_rag: true,
          timeout: 60
        },
        {
          headers: {
            'Content-Type': 'application/json'
          }
        }
      );

      setResponse(data);
    } catch (err: any) {
      setError(err.response?.data?.error?.message || 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="chat-container">
      <div className="input-section">
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask a security question..."
          rows={4}
        />
        <button onClick={sendMessage} disabled={loading}>
          {loading ? 'Thinking...' : 'Send'}
        </button>
      </div>

      {error && <div className="error">{error}</div>}

      {response && (
        <div className="response-section">
          <div className="answer">{response.answer}</div>
          <div className="metadata">
            <span>Intent: {response.intent}</span>
            <span>Time: {response.stats.total_time_s}s</span>
            <span>Cost: ${response.estimated_cost.toFixed(4)}</span>
          </div>
          {response.rag_sources && (
            <div className="sources">
              <h4>Sources:</h4>
              <ul>
                {response.rag_sources.map((source, i) => (
                  <li key={i}>
                    {source.source} - Score: {source.score.toFixed(2)}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default ChatComponent;
```

#### 2. Streaming Chat (SSE)

> **Not:** `/api/chat/stream` bir **POST** endpoint'idir. `EventSource` yalnızca GET destekler
> ve kullanılamaz. Bunun yerine `fetch` + `ReadableStream` + manuel SSE frame parser kullanın.

SSE event sırası:
```
event: metadata  → intent, safety, rag_used, layer_path, session_id, history_turns
event: sources   → rag_sources listesi (RAG kullanıldıysa token'lardan ÖNCE gelir)
event: message   → token-by-token yanıt
event: done      → total_tokens, total_time_s, estimated_cost, verification_confidence
```

```typescript
import { useState, useRef } from 'react';

function StreamingChat() {
  const [question, setQuestion] = useState('');
  const [streamingResponse, setStreamingResponse] = useState('');
  const [ragSources, setRagSources] = useState<any[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [metadata, setMetadata] = useState<any>(null);
  const [stats, setStats] = useState<any>(null);
  const abortRef = useRef<AbortController | null>(null);

  const API_BASE_URL = 'http://localhost:8000';

  const sendStreamingMessage = async () => {
    setIsStreaming(true);
    setStreamingResponse('');
    setRagSources([]);
    setMetadata(null);
    setStats(null);

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const res = await fetch(`${API_BASE_URL}/api/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'text/event-stream' },
        body: JSON.stringify({ question, os: 'ubuntu_24_04', use_rag: true, rag_top_k: 3 }),
        signal: controller.signal,
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      if (!res.body) throw new Error('No response body');

      // Manuel SSE frame parser — '\n\n' ile ayrılmış event blokları
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const frames = buffer.split('\n\n');
        buffer = frames.pop() ?? '';

        for (const frame of frames) {
          const eventMatch = frame.match(/^event: (\w+)/m);
          const dataMatch  = frame.match(/^data: (.+)/ms);
          if (!dataMatch) continue;

          const eventType = eventMatch?.[1] ?? 'message';
          const data = JSON.parse(dataMatch[1]);

          if (eventType === 'metadata') setMetadata(data);
          else if (eventType === 'sources') setRagSources(data.rag_sources ?? []);
          else if (eventType === 'message' && data.token) setStreamingResponse(p => p + data.token);
          else if (eventType === 'done') setStats(data);
        }
      }
    } catch (err: any) {
      if (err.name !== 'AbortError') console.error('Stream error:', err);
    } finally {
      setIsStreaming(false);
    }
  };

  const stopStreaming = () => {
    abortRef.current?.abort();
    setIsStreaming(false);
  };

  return (
    <div className="streaming-chat">
      <div className="input-section">
        <textarea value={question} onChange={(e) => setQuestion(e.target.value)} rows={4}
          placeholder="Ask a security question..." />
        <button onClick={sendStreamingMessage} disabled={isStreaming}>
          {isStreaming ? 'Streaming...' : 'Send'}
        </button>
        {isStreaming && <button onClick={stopStreaming}>Stop</button>}
      </div>

      {metadata && (
        <div className="metadata">
          Intent: {metadata.intent} | RAG: {metadata.rag_used ? 'Yes' : 'No'}
          {stats && ` | Time: ${stats.total_time_s?.toFixed(2)}s`}
        </div>
      )}

      {streamingResponse && (
        <div className="response">
          {streamingResponse}
          {isStreaming && <span className="cursor">▋</span>}
        </div>
      )}

      {ragSources.length > 0 && (
        <div className="evidence-panel">
          <h4>Sources</h4>
          <ul>
            {ragSources.map((src, i) => (
              <li key={i}>{src.section} — {src.source} (score: {src.score.toFixed(2)})</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export default StreamingChat;
```

---

## Vue.js Integration

### Standard Chat (Composition API)

```vue
<template>
  <div class="chat-container">
    <div class="input-section">
      <textarea
        v-model="question"
        placeholder="Ask a security question..."
        rows="4"
      ></textarea>
      <button @click="sendMessage" :disabled="loading">
        {{ loading ? 'Thinking...' : 'Send' }}
      </button>
    </div>

    <div v-if="error" class="error">{{ error }}</div>

    <div v-if="response" class="response-section">
      <div class="answer">{{ response.answer }}</div>
      <div class="metadata">
        <span>Intent: {{ response.intent }}</span>
        <span>Time: {{ response.stats.total_time_s }}s</span>
        <span>Cost: ${{ response.estimated_cost.toFixed(4) }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000';

const question = ref('');
const response = ref<any>(null);
const loading = ref(false);
const error = ref<string | null>(null);

const sendMessage = async () => {
  loading.value = true;
  error.value = null;

  try {
    const { data } = await axios.post(
      `${API_BASE_URL}/api/chat`,
      {
        question: question.value,
        os: 'ubuntu_24_04',
        use_rag: true,
        timeout: 60
      }
    );

    response.value = data;
  } catch (err: any) {
    error.value = err.response?.data?.error?.message || 'An error occurred';
  } finally {
    loading.value = false;
  }
};
</script>
```

---

## Vanilla JavaScript

### Fetch API Example

```javascript
const API_BASE_URL = 'http://localhost:8000';

async function sendChatMessage(question) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        question: question,
        os: 'ubuntu_24_04',
        use_rag: true,
        timeout: 60
      })
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.error.message);
    }

    const data = await response.json();

    // Display response
    displayResponse(data);

    return data;
  } catch (error) {
    console.error('Chat error:', error);
    displayError(error.message);
  }
}

function displayResponse(data) {
  const responseDiv = document.getElementById('response');
  responseDiv.innerHTML = `
    <div class="answer">${data.answer}</div>
    <div class="metadata">
      <span>Intent: ${data.intent}</span>
      <span>Time: ${data.stats.total_time_s}s</span>
      <span>Cost: $${data.estimated_cost.toFixed(4)}</span>
    </div>
  `;
}

function displayError(message) {
  const errorDiv = document.getElementById('error');
  errorDiv.textContent = message;
  errorDiv.style.display = 'block';
}

// Event listener
document.getElementById('sendBtn').addEventListener('click', () => {
  const question = document.getElementById('questionInput').value;
  sendChatMessage(question);
});
```

---

## SSE Streaming Client

### Generic SSE Handler (fetch tabanlı — POST)

> `EventSource` yalnızca GET destekler; `/api/chat/stream` POST endpoint'idir.
> Aşağıdaki istemci `fetch` + `ReadableStream` + manuel SSE parser kullanır.

```javascript
class StreamingChatClient {
  constructor(baseUrl) {
    this.baseUrl = baseUrl;
    this._abort = null;
  }

  async streamChat(question, options = {}, callbacks = {}) {
    this.stop();
    const controller = new AbortController();
    this._abort = controller;

    try {
      const res = await fetch(`${this.baseUrl}/api/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'text/event-stream' },
        body: JSON.stringify({
          question,
          os:         options.os        ?? 'ubuntu_24_04',
          use_rag:    options.use_rag   !== false,
          rag_top_k:  options.rag_top_k ?? 3,
          session_id: options.session_id,
          timeout:    options.timeout   ?? 60,
        }),
        signal: controller.signal,
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      if (!res.body) throw new Error('No response body');

      const reader  = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const frames = buffer.split('\n\n');
        buffer = frames.pop() ?? '';

        for (const frame of frames) {
          const eventMatch = frame.match(/^event: (\w+)/m);
          const dataMatch  = frame.match(/^data: (.+)/ms);
          if (!dataMatch) continue;

          const eventType = eventMatch?.[1] ?? 'message';
          const data = JSON.parse(dataMatch[1]);

          switch (eventType) {
            case 'metadata': callbacks.onMetadata?.(data);                   break;
            case 'sources':  callbacks.onSources?.(data.rag_sources ?? []);  break;
            case 'message':  if (data.token) callbacks.onToken?.(data.token); break;
            case 'done':     callbacks.onComplete?.(data);                   break;
            case 'error':    callbacks.onError?.(new Error(data.message));   break;
          }
        }
      }
    } catch (err) {
      if (err.name !== 'AbortError') callbacks.onError?.(err);
    }
  }

  stop() {
    this._abort?.abort();
    this._abort = null;
  }
}

// Kullanım
const client = new StreamingChatClient('http://localhost:8000');

client.streamChat(
  'Ubuntu SSH nasıl sıkılaştırılır?',
  { os: 'ubuntu_24_04', use_rag: true, session_id: 'user-abc-123' },
  {
    onMetadata: (meta) => {
      console.log('Intent:', meta.intent, '| History turns:', meta.history_turns);
    },
    onSources: (sources) => {
      // Evidence paneli — token'lardan önce gelir
      sources.forEach(s => console.log(`[${s.score.toFixed(2)}] ${s.section}`));
    },
    onToken: (token) => {
      document.getElementById('response').textContent += token;
    },
    onComplete: (stats) => {
      console.log(`Tamamlandı: ${stats.total_time_s?.toFixed(2)}s, maliyet: $${stats.estimated_cost}`);
    },
    onError: (err) => console.error('Hata:', err),
  }
);
```

---

## Error Handling

### Standard Error Response Format

```json
{
  "error": {
    "code": "PIPELINE_ERROR",
    "message": "Pipeline execution failed",
    "type": "internal_error",
    "request_id": "req_abc123",
    "details": {
      "stage": "pipeline_execution"
    }
  }
}
```

### Error Handling Example

```typescript
interface APIError {
  error: {
    code: string;
    message: string;
    type: string;
    request_id: string;
    details?: any;
  };
}

async function handleAPICall() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: 'test' })
    });

    if (!response.ok) {
      const errorData: APIError = await response.json();

      // Handle specific error types
      switch (errorData.error.type) {
        case 'rate_limit_exceeded':
          showNotification('Too many requests. Please wait.');
          break;
        case 'validation_error':
          showNotification(`Invalid input: ${errorData.error.message}`);
          break;
        case 'timeout_error':
          showNotification('Request timeout. Please try again.');
          break;
        default:
          showNotification(`Error: ${errorData.error.message}`);
      }

      return null;
    }

    return await response.json();
  } catch (error) {
    console.error('Network error:', error);
    showNotification('Network error. Please check your connection.');
    return null;
  }
}
```

---

## Best Practices

### 1. Request Optimization

```javascript
// Use AbortController for cancellation
const controller = new AbortController();

fetch(`${API_BASE_URL}/api/chat`, {
  method: 'POST',
  signal: controller.signal,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ question: 'test', timeout: 30 })
});

// Cancel if needed
controller.abort();
```

### 2. Response Caching

```javascript
class APIClient {
  constructor() {
    this.cache = new Map();
  }

  async chat(question, options = {}) {
    const cacheKey = JSON.stringify({ question, ...options });

    // Check cache
    if (this.cache.has(cacheKey)) {
      console.log('Cache hit!');
      return this.cache.get(cacheKey);
    }

    // Make API call
    const response = await fetch(`${API_BASE_URL}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, ...options })
    });

    const data = await response.json();

    // Cache response (5 minutes TTL)
    this.cache.set(cacheKey, data);
    setTimeout(() => this.cache.delete(cacheKey), 5 * 60 * 1000);

    return data;
  }
}
```

### 3. Loading States

```typescript
enum LoadingState {
  IDLE = 'idle',
  LOADING = 'loading',
  STREAMING = 'streaming',
  SUCCESS = 'success',
  ERROR = 'error'
}

function ChatComponent() {
  const [loadingState, setLoadingState] = useState<LoadingState>(LoadingState.IDLE);

  const sendMessage = async () => {
    setLoadingState(LoadingState.LOADING);

    try {
      const response = await fetch(...);
      const data = await response.json();
      setLoadingState(LoadingState.SUCCESS);
    } catch (error) {
      setLoadingState(LoadingState.ERROR);
    }
  };

  return (
    <div>
      {loadingState === LoadingState.LOADING && <Spinner />}
      {loadingState === LoadingState.ERROR && <ErrorMessage />}
      {/* ... */}
    </div>
  );
}
```

### 4. Rate Limit Handling

```javascript
// Respect rate limits from response headers
async function makeRequest() {
  const response = await fetch(`${API_BASE_URL}/api/chat`, {
    method: 'POST',
    body: JSON.stringify({ question: 'test' })
  });

  // Check rate limit headers
  const limit = response.headers.get('X-RateLimit-Limit');
  const remaining = response.headers.get('X-RateLimit-Remaining');
  const reset = response.headers.get('X-RateLimit-Reset');

  if (remaining === '0') {
    const resetDate = new Date(parseInt(reset) * 1000);
    console.warn(`Rate limit exceeded. Resets at ${resetDate}`);
  }

  return response.json();
}
```

### 5. TypeScript Types

```typescript
// API Types
export interface ChatRequest {
  question: string;
  os?: string;
  role?: string;
  security_level?: 'low' | 'medium' | 'high';
  use_rag?: boolean;
  rag_top_k?: number;
  timeout?: number;
}

export interface RAGSource {
  id: string;
  score: number;
  source: string;
  section: string;
}

export interface ChatResponse {
  answer: string;
  intent: string;
  safety_category: string;
  layer_path: string;
  rag_sources?: RAGSource[];
  stats: {
    total_time_s: number;
    rag_time_s?: number;
    llm_time_s?: number;
  };
  request_id: string;
  estimated_cost: number;
}

export interface APIError {
  error: {
    code: string;
    message: string;
    type: string;
    request_id: string;
    details?: Record<string, any>;
  };
}
```

---

## Complete Example Application

See the `examples/frontend-demo/` directory for complete working examples:

- `react-chat/` - React + TypeScript chat interface
- `vue-chat/` - Vue 3 + Composition API
- `vanilla-js/` - Plain JavaScript implementation

---

## Support

For API issues or questions:
- **GitHub**: [Issues](https://github.com/your-org/ai-powered-os-hardening/issues)
- **Documentation**: [docs/](../docs/)

---

**Last Updated**: 2025-12-24
**Version**: v1.0.2
