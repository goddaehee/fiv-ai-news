"use client";

import { useEffect, useState, type FormEvent } from "react";
import { getSubscribedEmail, subscribeEmail } from "@/lib/subscribe";

export function SubscribeForm({ compact = false }: { compact?: boolean }) {
  const [email, setEmail] = useState("");
  const [placeholder, setPlaceholder] = useState("you@email.com");
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  useEffect(() => {
    const existing = getSubscribedEmail();
    if (existing) setPlaceholder(existing);
  }, []);

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    const value = email.trim();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
      setMsg({ kind: "err", text: "이메일 형식을 확인해 주세요." });
      return;
    }
    const result = subscribeEmail(value);
    if (result.duplicate) {
      setMsg({ kind: "ok", text: "이미 이 브라우저에서 구독 중입니다." });
    } else {
      setMsg({
        kind: "ok",
        text: "구독이 이 브라우저에 저장됐습니다. 데모라 실제 메일은 발송되지 않습니다.",
      });
    }
    setEmail("");
  };

  return (
    <section className={compact ? undefined : "sub-card"} id={compact ? undefined : "subscribe-card"}>
      {!compact ? (
        <div>
          <p className="sub-label">메일 구독</p>
          <h2 className="sub-title">내일 아침 브리핑, 메일함으로 받기</h2>
          <p className="sub-desc">평일 07:00 전후 발행 · 무료 · 이메일만 · 메일 하단에서 1클릭 해지</p>
        </div>
      ) : null}
      <form className="sub-form" onSubmit={onSubmit} noValidate>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder={placeholder}
          aria-label="구독 이메일 주소"
          autoComplete="email"
          inputMode="email"
          required
        />
        <button className="btn-primary" type="submit">
          무료로 구독하기
        </button>
        {msg ? <div className={`sub-feedback ${msg.kind}`}>{msg.text}</div> : null}
      </form>
    </section>
  );
}
