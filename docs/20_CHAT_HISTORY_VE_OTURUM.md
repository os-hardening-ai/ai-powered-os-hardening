# 20 — Chat Geçmişi ve Oturum (Kullanıcı-Bazlı, Kalıcı)

**Güncelleme:** 2026-06
**İlgili kod:** `llm/core/sqlite_session_store.py`, `llm/core/session_store.py`, `llm/core/redis_session_store.py`, `api/router_chat.py`, `api/db.py`, `config/schemas.py`
**İlgili testler:** `tests/unit/test_sqlite_session_store.py` (9 test)

Bu belge, çok-turlu konuşma için oturum/geçmiş altyapısının **kullanıcı-bazlı, kalıcı** hâle
getirilmesini belgeler.

---

## 1. Problem (giderilen gizlilik açığı)

Önceki durumda chat geçmişi Redis'te **global** `session:{session_id}` anahtarı altında
tutuluyordu. Anahtar yalnız istemciden gelen düz `session_id` string'iydi; **giriş yapan
kullanıcıyla bir bağı yoktu**. Sonuç: frontend sabit/paylaşılan bir `session_id` kullandığında
**tüm kullanıcılar birbirinin geçmişini görebiliyordu** (gizlilik ihlali). Ayrıca Redis TTL'i (1 saat)
nedeniyle geçmiş kalıcı değildi.

## 2. Çözüm — `(owner, session_id)` ile izolasyon + kalıcılık

- **owner = kimlik anahtarı.** `api.auth.peek_username(request)` ile JWT'den kullanıcı adı
  best-effort çıkarılır (auth ZORLAMAZ; token yoksa `"anon"`). Böylece iki farklı kullanıcı
  **aynı** `session_id`'yi kullansa bile geçmişleri **ayrıdır** (owner farklı).
- **Kalıcı SQLite.** Geçmiş `data/auth.db` içindeki `chat_history` tablosunda tutulur (auth/audit
  ile aynı veritabanı, native `sqlite3`). Her tur **anında** yazılır (soru ve cevap üretildiği an).
- **Otomatik temizleme.** `config.auth.chat_history_retention_days` (varsayılan **30 gün**;
  `0` = süresiz). Açılışta eski turlar silinir → DB şişmesi + gizlilik.

### `chat_history` şeması
```sql
CREATE TABLE chat_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  owner TEXT NOT NULL,        -- JWT kullanıcı adı veya "anon"
  session_id TEXT NOT NULL,
  role TEXT NOT NULL,         -- user | assistant
  content TEXT NOT NULL,
  intent TEXT, safety TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX idx_chat_owner_sess ON chat_history(owner, session_id, id);
CREATE INDEX idx_chat_created    ON chat_history(created_at);
```

## 3. Store mimarisi (drop-in, owner-scoped)

`SqliteSessionStore` birincil store'dur; kurulamazsa in-memory `SessionStore`'a düşülür.
Üç store da aynı arayüzü paylaşır ve `owner` **keyword** parametresi alır (geriye dönük uyumlu):

| Metod | Açıklama |
|-------|----------|
| `get_history(session_id, *, owner)` | Bağlam penceresi: son `max_history*2` tur (kronolojik) |
| `add_turn(session_id, role, content, intent=, safety=, *, owner)` | Turu anında kalıcı yazar |
| `reset_session(session_id, *, owner)` | Oturumu siler |
| `list_sessions(owner)` | Kullanıcının oturumları (son mesaj + sayım) — yalnız SQLite |
| `get_turns(owner, session_id)` | Bir oturumun tüm turları — owner filtreli |
| `delete_session(owner, session_id)` | Owner-scoped silme |
| `cleanup(retention_days)` | Eski turları siler |

In-memory ve Redis store'lar da anahtarı owner ile namespace'ler (fallback'te de izolasyon).

## 4. Geçmiş API'si (auth ZORUNLU → doğal olarak kullanıcıya scoped)

| Endpoint | Açıklama |
|----------|----------|
| `GET /chat/sessions` | Giriş yapan kullanıcının sohbetleri |
| `GET /chat/history?session_id=` | O sohbetin mesajları — **yalnız sahibi erişebilir** |
| `DELETE /chat/history?session_id=` | Kullanıcının kendi sohbetini silmesi |

`/chat` ve `/chat/stream` açık kalır (anonim/demo çalışır); token gönderilirse geçmiş o kullanıcıya
izole edilir. Frontend, geçmişi **global yerine giriş yapan kullanıcının JWT'siyle** bu
endpoint'lerden çeker → başkasının geçmişi gelmez.

## 5. "Session" iki ayrı kavram (sık karışan)
1. **Auth session = login (JWT)** → kullanıcının KİM olduğu.
2. **Chat `session_id` = sohbet thread'i** → HANGİ konuşma (bir kullanıcının birden çok sohbeti).

`owner` (1) kullanıcılar arasını, `session_id` (2) aynı kullanıcının farklı sohbetlerini ayırır.

## 6. Test kapsamı
`test_sqlite_session_store.py`: kullanıcı-izolasyonu (A, B'nin geçmişini göremez), kronolojik
pencere, owner-scoped get/delete, kalıcılık (store örnekleri arası), cleanup, boş/eksik durumlar.
