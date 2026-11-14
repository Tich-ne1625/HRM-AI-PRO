"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { useAuth } from "../auth/auth-provider";
import { WorkspaceDialog } from "../workspace/dialog";
import { collaborationApi, dateTime, type Person, type Post } from "./api";
import { MentionPicker } from "./mention-picker";

export function InternalFeed() {
  const { user } = useAuth();
  const params = useSearchParams();
  const cache = useQueryClient();
  const [page, setPage] = useState(1);
  const [audience, setAudience] = useState("all");
  const [composer, setComposer] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [dismissed, setDismissed] = useState<string | null>(null);
  const linked = params.get("post");
  const active = selected ?? (linked !== dismissed ? linked : null);
  const query = useQuery({ queryKey: ["collaboration", user?.id, user?.role, "feed", page, audience], queryFn: () => collaborationApi.feed(page, audience), enabled: !!user, refetchInterval: 15000 });
  const refresh = () => { void cache.invalidateQueries({ queryKey: ["collaboration"] }); };
  return <div className="internal-feed">
    <div className="feed-heading"><div><span className="eyebrow">KẾT NỐI NỘI BỘ</span><h1>Bảng tin công ty</h1><p>Thông tin chung, cập nhật phòng ban và trao đổi cùng đồng nghiệp.</p></div><button disabled={!query.data || (!query.data.can_publish_company && !query.data.department_id)} onClick={() => setComposer(true)}>+ Viết bài</button></div>
    <div className="feed-filters" role="group" aria-label="Phạm vi bảng tin">{([["all", "Tất cả"], ["company", "Toàn công ty"], ["department", "Phòng ban của tôi"]] as const).map(([value, label]) => <button key={value} aria-pressed={audience === value} onClick={() => { setAudience(value); setPage(1); }}>{label}</button>)}</div>
    {query.isPending && <p role="status">Đang tải bảng tin…</p>}
    {query.isError && <p role="alert">Không tải được bảng tin. <button onClick={() => void query.refetch()}>Thử lại</button></p>}
    {query.data && <><div className="feed-layout"><div className="feed-posts">{query.data.items.map((post) => <article key={post.id} className="feed-card"><PostHeader post={post} /><h2>{post.title}</h2><p className="feed-preview">{post.body}</p><Mentions people={post.mentions} /><button className="secondary" onClick={() => setSelected(post.id)}>Xem bài viết và trao đổi</button></article>)}{!query.data.items.length && <div className="feed-card"><h2>Chưa có bài viết trong mục này</h2><p>Bài đăng mới sẽ tự cập nhật tại đây. Chọn Viết bài để chia sẻ thông tin đầu tiên.</p></div>}</div>
      <aside className="feed-guidance"><h2>Không gian chung</h2><p><strong>Toàn công ty:</strong> HR và quản trị viên đăng thông báo chung.</p><p><strong>Phòng ban:</strong> thành viên chia sẻ cập nhật trong phòng của mình. HR và quản trị viên có thể theo dõi.</p><p>Dùng @nhắc khi cần một người chú ý. Trao đổi riêng qua nút Chat ở góc màn hình.</p><small>Nhận xét đánh giá và bằng chứng hiệu suất tiếp tục nằm trong các tab nghiệp vụ.</small></aside></div>
      <div className="collab-pagination"><button disabled={page === 1} onClick={() => setPage(page - 1)}>Trang trước</button><span>Trang {page}</span><button disabled={!query.data.has_more} onClick={() => setPage(page + 1)}>Trang sau</button></div>
      {composer && <WorkspaceDialog variant="content" eyebrow="TRAO ĐỔI NỘI BỘ" title="Viết bài nội bộ" close={() => setComposer(false)}><PostComposer departments={query.data.departments} company={query.data.can_publish_company} done={() => { setComposer(false); setPage(1); refresh(); }} /></WorkspaceDialog>}
    </>}
    {active && <WorkspaceDialog variant="content" eyebrow="TRAO ĐỔI NỘI BỘ" key={active} title="Bài viết và trao đổi" close={() => { setSelected(null); setDismissed(linked); }}><PostDetail id={active} /></WorkspaceDialog>}
  </div>;
}

function PostHeader({ post }: { post: Post }) { return <div className="feed-meta"><span className="collab-avatar" aria-hidden="true">{post.author.name.slice(0, 1).toUpperCase()}</span><div><strong>{post.author.name}</strong><small>{post.department ?? "Toàn công ty"} · {dateTime(post.created_at)}</small></div></div>; }

function PostComposer({ departments, company, done }: { departments: { id: string; name: string }[]; company: boolean; done: () => void }) {
  const [target, setTarget] = useState(company ? "company" : departments[0]?.id ?? "");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [mentions, setMentions] = useState<Person[]>([]);
  const [id] = useState(() => crypto.randomUUID());
  const save = useMutation({ mutationFn: () => collaborationApi.publish({ id, title, body, mentions: mentions.map((p) => p.id), department_id: target === "company" ? null : target }), onSuccess: done });
  return <form className="collab-form" onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
    <fieldset disabled={save.isPending}><label>Người được xem<select value={target} onChange={(e) => { setTarget(e.target.value); setMentions([]); }}>{company && <option value="company">Toàn công ty</option>}{departments.map((department) => <option key={department.id} value={department.id}>Phòng ban · {department.name}</option>)}</select></label>
      <label>Tiêu đề<input required maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} /></label><label>Nội dung<textarea required rows={7} maxLength={10000} value={body} onChange={(e) => setBody(e.target.value)} /></label>
      <MentionPicker selected={mentions} change={setMentions} departmentId={target === "company" ? undefined : target} disabled={save.isPending} />
      <p className="help-text">Bài đăng sẽ gửi thông báo đến người thuộc phạm vi được chọn.</p><button disabled={!title.trim() || !body.trim()}>{save.isPending ? "Đang đăng…" : "Đăng bài"}</button>
    </fieldset>{save.isError && <p role="alert">Chưa đăng được bài. Nội dung vẫn được giữ để bạn thử lại.</p>}
  </form>;
}

function PostDetail({ id }: { id: string }) {
  const { user } = useAuth();
  const cache = useQueryClient();
  const [page, setPage] = useState(1);
  const [body, setBody] = useState("");
  const [mentions, setMentions] = useState<Person[]>([]);
  const [commentId, setCommentId] = useState(() => crypto.randomUUID());
  const query = useQuery({ queryKey: ["collaboration", user?.id, user?.role, "post", id, page], queryFn: () => collaborationApi.post(id, page), refetchInterval: 15000 });
  const send = useMutation({ mutationFn: () => collaborationApi.comment(id, { id: commentId, body, mentions: mentions.map((p) => p.id) }), onSuccess: () => { setBody(""); setMentions([]); setCommentId(crypto.randomUUID()); setPage(1); void cache.invalidateQueries({ queryKey: ["collaboration"] }); } });
  return <div className="post-detail">
    {query.isPending && <p>Đang tải bài viết…</p>}{query.isError && <p role="alert">Bài viết không còn trong phạm vi của bạn hoặc chưa tải được. <button onClick={() => void query.refetch()}>Thử lại</button></p>}
    {query.data && <><PostHeader post={query.data.post} /><h2>{query.data.post.title}</h2><p className="collab-body">{query.data.post.body}</p><Mentions people={query.data.post.mentions} /><h3>Trao đổi</h3>
      {query.data.comments.map((comment) => <article key={comment.id} className="feed-comment"><strong>{comment.author.name}</strong><small>{dateTime(comment.created_at)}</small><p className="collab-body">{comment.body}</p><Mentions people={comment.mentions} /></article>)}{!query.data.comments.length && <p>Chưa có trao đổi. Bạn có thể phản hồi hoặc @nhắc người liên quan.</p>}
      <div className="collab-pagination"><button disabled={!query.data.has_more} onClick={() => setPage(page + 1)}>Trao đổi cũ hơn</button><span>Trang {page}</span><button disabled={page === 1} onClick={() => setPage(page - 1)}>Mới hơn</button></div>
      <form className="collab-form" onSubmit={(e) => { e.preventDefault(); send.mutate(); }}><label>Phản hồi bài viết<textarea required rows={3} maxLength={2000} disabled={send.isPending} value={body} onChange={(e) => setBody(e.target.value)} /></label><MentionPicker key={commentId} selected={mentions} change={setMentions} post={id} disabled={send.isPending} /><button disabled={send.isPending || !body.trim()}>{send.isPending ? "Đang gửi…" : "Gửi trao đổi"}</button>{send.isError && <p role="alert">Chưa gửi được. Nội dung vẫn được giữ để thử lại; hãy kiểm tra quyền xem bài.</p>}</form>
    </>}
  </div>;
}

function Mentions({ people }: { people: Person[] }) { return <div className="mention-chips">{people.map((p) => <span key={p.id}>@{p.name}</span>)}</div>; }
