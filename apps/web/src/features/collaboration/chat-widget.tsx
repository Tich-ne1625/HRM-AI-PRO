"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { useAuth } from "../auth/auth-provider";
import { collaborationApi, dateTime, type Person } from "./api";

export function ChatWidget() { return <Suspense><ChatWindow /></Suspense>; }

function ChatWindow() {
  const { user } = useAuth();
  const cache = useQueryClient();
  const params = useSearchParams();
  const messageLink = params.get("message");
  const [dismissed, setDismissed] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [peer, setPeer] = useState<Person | null>(null);
  const [tab, setTab] = useState<"recent" | "people">("recent");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const linked = useQuery({ queryKey: ["collaboration", user?.id, "message-link", messageLink], queryFn: () => collaborationApi.message(messageLink!), enabled: !!user && !!messageLink && messageLink !== dismissed });
  const linkPeer = linked.data && messageLink !== dismissed ? linked.data.sender_id === user?.id ? linked.data.recipient_id : linked.data.sender_id : null;
  const isOpen = open || (!!messageLink && messageLink !== dismissed);
  const conversations = useQuery({ queryKey: ["collaboration", user?.id, user?.role, "conversations", page], queryFn: () => collaborationApi.conversations(page), enabled: !!user, refetchInterval: 15000 });
  const activePeer = linkPeer ? conversations.data?.items.find((item) => item.peer.id === linkPeer)?.peer ?? { id: linkPeer, name: "Cuộc trò chuyện", role: "EMPLOYEE" as const, department: null, department_id: null } : peer;
  const people = useQuery({ queryKey: ["collaboration", user?.id, "chat-people", search, page], queryFn: () => collaborationApi.people(search, page), enabled: !!user && isOpen && tab === "people" && !activePeer });
  const count = conversations.data?.unread_count ?? 0;
  const panel = useRef<HTMLElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  useEffect(() => { if (isOpen) panel.current?.querySelector<HTMLButtonElement>("button")?.focus(); }, [isOpen]);
  function close() { setOpen(false); setDismissed(messageLink); trigger.current?.focus(); }
  function select(person: Person) { setPeer(person); setDismissed(messageLink); }
  return <div className="chat-widget">
    {!isOpen && <button ref={trigger} className="chat-launcher" onClick={() => setOpen(true)} aria-label={`Mở chat nội bộ${count ? `, ${count} tin chưa đọc` : ""}`}>💬 <span>Chat nội bộ</span>{count > 0 && <strong>{count > 99 ? "99+" : count}</strong>}</button>}
    {isOpen && <section ref={panel} className="chat-window" aria-label="Chat nội bộ" onKeyDown={(e) => { if (e.key === "Escape") { e.stopPropagation(); close(); } }}>
      <header className="chat-heading"><div>{activePeer && <button type="button" className="chat-back" aria-label="Danh sách trò chuyện" onClick={() => { setPeer(null); setDismissed(messageLink); setPage(1); }}>‹</button>}<strong>{activePeer?.name ?? "Chat nội bộ"}</strong></div><button type="button" aria-label="Thu gọn chat" onClick={close}>×</button></header>
      {linked.isError && messageLink !== dismissed && <p role="alert">Không mở được tin nhắn hoặc bạn không có quyền xem. <button onClick={() => setDismissed(messageLink)}>Về danh sách</button></p>}
      {activePeer ? <Conversation key={activePeer.id} peer={activePeer} /> : <div className="chat-directory">
        <div className="notification-tabs"><button aria-pressed={tab === "recent"} onClick={() => { setTab("recent"); setPage(1); }}>Gần đây</button><button aria-pressed={tab === "people"} onClick={() => { setTab("people"); setPage(1); }}>Tìm đồng nghiệp</button></div>
        {tab === "people" && <label>Tên hoặc email<input value={search} maxLength={100} onChange={(e) => { setSearch(e.target.value); setPage(1); }} /></label>}
        <div className="chat-contact-list">{tab === "recent" ? <>
          {conversations.isPending && <p>Đang tải cuộc trò chuyện…</p>}{conversations.isError && <p role="alert">Chưa tải được chat. <button onClick={() => void conversations.refetch()}>Thử lại</button></p>}
          {conversations.data?.items.map(({ peer: contact, latest }) => <button className="chat-contact" key={contact.id} onClick={() => select(contact)}><strong>{contact.name}{latest.recipient_id === user?.id && !latest.read_at && <span className="unread-dot" aria-label="Có tin chưa đọc" />}</strong><span>{latest.sender_id === user?.id ? "Bạn: " : ""}{latest.body}</span><small>{dateTime(latest.created_at)}</small></button>)}
          {conversations.data && !conversations.data.items.length && <div className="notification-empty"><p>Chưa có cuộc trò chuyện.</p><button onClick={() => { setTab("people"); setPage(1); }}>Tìm đồng nghiệp để bắt đầu</button></div>}
        </> : <>
          {people.isPending && <p>Đang tìm đồng nghiệp…</p>}{people.isError && <p role="alert">Không tải được danh bạ. <button onClick={() => void people.refetch()}>Thử lại</button></p>}
          {people.data?.items.map((contact) => <button className="chat-contact" key={contact.id} onClick={() => select(contact)}><strong>{contact.name}</strong><small>{contact.department ?? "Tài khoản công ty"}</small></button>)}{people.data && !people.data.items.length && <p>Không tìm thấy đồng nghiệp.</p>}
        </>}</div>
        <div className="collab-pagination"><button disabled={page === 1} onClick={() => setPage(page - 1)}>Trước</button><span>Trang {page}</span><button disabled={!(tab === "recent" ? conversations.data : people.data)?.has_more} onClick={() => setPage(page + 1)}>Sau</button></div>
        <small className="chat-footnote">Chỉ hai người trong cuộc trò chuyện xem được tin nhắn.</small>
      </div>}
      <button type="button" className="chat-refresh" onClick={() => void cache.invalidateQueries({ queryKey: ["collaboration"] })}>Làm mới trao đổi</button>
    </section>}
  </div>;
}

function Conversation({ peer }: { peer: Person }) {
  const { user } = useAuth();
  const cache = useQueryClient();
  const [body, setBody] = useState("");
  const [mention, setMention] = useState(false);
  const [id, setId] = useState(() => crypto.randomUUID());
  const [before, setBefore] = useState<string | undefined>();
  const [cursors, setCursors] = useState<(string | undefined)[]>([]);
  const [visible, setVisible] = useState(() => typeof document === "undefined" || document.visibilityState === "visible");
  const [atBottom, setAtBottom] = useState(true);
  const scroll = useRef<HTMLDivElement>(null);
  const query = useQuery({ queryKey: ["collaboration", user?.id, user?.role, "chat", peer.id, before], queryFn: () => collaborationApi.messages(peer.id, before), refetchInterval: 15000 });
  const refresh = () => { void cache.invalidateQueries({ queryKey: ["collaboration"] }); void cache.invalidateQueries({ queryKey: ["notifications"] }); };
  const read = useMutation({ mutationFn: (through: string) => collaborationApi.read(peer.id, through), onSuccess: refresh });
  const send = useMutation({ mutationFn: () => collaborationApi.send(peer.id, { id, body, mentions: mention ? [peer.id] : [] }), onSuccess: () => { setBody(""); setMention(false); setId(crypto.randomUUID()); setBefore(undefined); setCursors([]); setAtBottom(true); refresh(); } });
  const latest = query.data?.items.at(-1)?.id;
  const unread = !before && visible && atBottom ? query.data?.items.filter((item) => item.recipient_id === user?.id && !item.read_at).at(-1)?.id : undefined;
  const lastAttempt = useRef<string | null>(null);
  const markRead = read.mutate;
  useEffect(() => { const change = () => setVisible(document.visibilityState === "visible"); document.addEventListener("visibilitychange", change); return () => document.removeEventListener("visibilitychange", change); }, []);
  useEffect(() => { if (unread && lastAttempt.current !== unread) { lastAttempt.current = unread; markRead(unread); } }, [unread, markRead]);
  useEffect(() => { if (!before && atBottom && scroll.current) scroll.current.scrollTop = scroll.current.scrollHeight; }, [latest, before, atBottom]);
  return <>
    <div className="chat-history" ref={scroll} onScroll={(e) => { const el = e.currentTarget; setAtBottom(el.scrollHeight - el.scrollTop - el.clientHeight < 48); }} aria-label={`Tin nhắn với ${peer.name}`}>
      {query.isPending && <p>Đang tải tin nhắn…</p>}{query.isError && <p role="alert">Không tải được tin nhắn. <button onClick={() => void query.refetch()}>Thử lại</button></p>}
      {query.data?.has_more && <button className="secondary" onClick={() => { setCursors([...cursors, before]); setBefore(query.data?.items[0]?.id); }}>Xem tin cũ hơn</button>}
      {before && <button className="secondary" onClick={() => { setBefore(cursors.at(-1)); setCursors(cursors.slice(0, -1)); }}>Về tin mới hơn</button>}
      {query.data?.items.map((item) => <article key={item.id} className={`chat-bubble ${item.sender_id === user?.id ? "chat-own" : ""}`}><p>{item.body}</p><small>{dateTime(item.created_at)}{item.sender_id === user?.id ? item.read_at ? " · Đã đọc" : " · Đã gửi" : ""}</small></article>)}
      {query.data && !query.data.items.length && <p className="help-text">Bắt đầu trao đổi với {peer.name}.</p>}
    </div>
    <form className="chat-compose" onSubmit={(e) => { e.preventDefault(); send.mutate(); }}>
      <label htmlFor="chat-message-body">Tin nhắn<textarea id="chat-message-body" rows={2} maxLength={2000} required value={body} disabled={send.isPending} onChange={(e) => setBody(e.target.value)} placeholder="Nhập tin nhắn…" /></label>
      <div><button type="button" className="secondary" aria-pressed={mention} disabled={send.isPending} onClick={() => { if (!mention) { setBody((value) => `${value}${value ? " " : ""}@${peer.name} `.slice(0, 2000)); setMention(true); } else setMention(false); }}>@ Nhắc</button><button disabled={send.isPending || !body.trim()}>{send.isPending ? "Đang gửi…" : "Gửi"}</button></div>
      {send.isError && <p role="alert">Chưa gửi được, nội dung vẫn được giữ. Hãy kiểm tra người nhận hoặc thử lại.</p>}
      {read.isError && <p role="alert">Chưa cập nhật được đã đọc. <button type="button" onClick={() => { if (unread) read.mutate(unread); }}>Thử lại</button></p>}
    </form>
  </>;
}
