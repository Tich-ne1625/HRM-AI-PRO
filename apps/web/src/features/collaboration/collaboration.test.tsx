// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import { collaborationApi, type Message, type Person, type Post } from "./api";
import { InternalFeed } from "./feed";
import { ChatWidget } from "./chat-widget";

const state = vi.hoisted(() => ({ role: "EMPLOYEE", params: new URLSearchParams() }));
vi.mock("../auth/auth-provider", () => ({ useAuth: () => ({ user: { id: "me", role: state.role } }) }));
vi.mock("next/navigation", () => ({ useSearchParams: () => state.params }));
vi.mock("../workspace/dialog", () => ({ WorkspaceDialog: ({ title, children, close }: { title: string; children: ReactNode; close: () => void }) => <div role="dialog" aria-label={title}><button onClick={close}>Đóng</button>{children}</div> }));
vi.mock("./api", async (importOriginal) => ({ ...await importOriginal<typeof import("./api")>(), collaborationApi: { feed: vi.fn(), post: vi.fn(), publish: vi.fn(), comment: vi.fn(), people: vi.fn(), conversations: vi.fn(), messages: vi.fn(), message: vi.fn(), send: vi.fn(), read: vi.fn() } }));

const person: Person = { id: "peer", name: "Nguyễn An", department: "Kỹ thuật", department_id: "dept", role: "EMPLOYEE" };
const post: Post = { id: "post1", title: "Lịch sinh hoạt phòng", body: "Cập nhật tuần này", author: person, mentions: [person], department_id: "dept", department: "Kỹ thuật", created_at: "2026-11-14T10:00:00Z" };
const message: Message = { id: "message1", sender_id: "peer", recipient_id: "me", body: "Nhờ bạn xem cập nhật", created_at: "2026-11-14T10:00:00Z", read_at: null };
function mount(children: ReactNode) { const cache = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } }); render(<QueryClientProvider client={cache}>{children}</QueryClientProvider>); return cache; }
beforeEach(() => {
  vi.resetAllMocks(); state.role = "EMPLOYEE"; state.params = new URLSearchParams();
  vi.mocked(collaborationApi.feed).mockResolvedValue({ items: [post], department_id: "dept", departments: [{ id: "dept", name: "Kỹ thuật" }], can_publish_company: false, has_more: false });
  vi.mocked(collaborationApi.post).mockResolvedValue({ post, comments: [], has_more: false });
  vi.mocked(collaborationApi.people).mockResolvedValue({ items: [person], has_more: false });
  vi.mocked(collaborationApi.conversations).mockResolvedValue({ items: [{ peer: person, latest: message }], unread_count: 1, has_more: false });
  vi.mocked(collaborationApi.messages).mockResolvedValue({ items: [message], has_more: false });
  vi.mocked(collaborationApi.read).mockResolvedValue(undefined);
});

it("opens a post in a closable overlay while retaining feed filters", async () => {
  const user = userEvent.setup(); mount(<InternalFeed />);
  await screen.findByText(post.title);
  await user.click(screen.getByRole("button", { name: "Phòng ban của tôi" }));
  await user.click(screen.getByRole("button", { name: "Xem bài viết và trao đổi" }));
  expect(await screen.findByRole("dialog", { name: "Bài viết và trao đổi" })).toBeTruthy();
  await user.click(screen.getByRole("button", { name: "Đóng" }));
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(screen.getByRole("button", { name: "Phòng ban của tôi" }).getAttribute("aria-pressed")).toBe("true");
});

it("employees publish only to their department and explicit mentions are included", async () => {
  const user = userEvent.setup(); vi.mocked(collaborationApi.publish).mockResolvedValue(post); mount(<InternalFeed />);
  await screen.findByText(post.title); await user.click(screen.getByRole("button", { name: "+ Viết bài" }));
  expect(screen.getAllByRole("option").map((option) => option.textContent)).toEqual(["Phòng ban · Kỹ thuật"]);
  await user.type(screen.getByLabelText("Tiêu đề"), "Cuộc họp"); await user.type(screen.getByLabelText("Nội dung"), "Thứ hai");
  await user.click(screen.getByRole("button", { name: "@ Nhắc người liên quan" }));
  await user.click(await screen.findByRole("checkbox"));
  await user.click(screen.getByRole("button", { name: "Đăng bài" }));
  await waitFor(() => expect(collaborationApi.publish).toHaveBeenCalledWith(expect.objectContaining({ department_id: "dept", mentions: ["peer"], title: "Cuộc họp" })));
});

it("retains an unsent post and displays failure without pretending it was published", async () => {
  const user = userEvent.setup(); vi.mocked(collaborationApi.publish).mockRejectedValue(new Error("offline")); mount(<InternalFeed />);
  await screen.findByText(post.title); await user.click(screen.getByRole("button", { name: "+ Viết bài" }));
  await user.type(screen.getByLabelText("Tiêu đề"), "Bản nháp"); await user.type(screen.getByLabelText("Nội dung"), "Giữ nội dung");
  await user.click(screen.getByRole("button", { name: "Đăng bài" }));
  expect(await screen.findByRole("alert")).toBeTruthy();
  expect((screen.getByLabelText("Nội dung") as HTMLTextAreaElement).value).toBe("Giữ nội dung");
  expect(screen.getByRole("dialog")).toBeTruthy();
});

it("opens tagged post deep links as an overlay and allows X close", async () => {
  const user = userEvent.setup(); state.params = new URLSearchParams("post=post1"); mount(<InternalFeed />);
  const dialog = await screen.findByRole("dialog");
  expect(await within(dialog).findByText("@Nguyễn An")).toBeTruthy();
  await user.click(within(dialog).getByRole("button", { name: "Đóng" }));
  expect(screen.queryByRole("dialog")).toBeNull();
});

it("shows unread count while minimized without marking private messages read", async () => {
  mount(<ChatWidget />);
  await screen.findByRole("button", { name: "Mở chat nội bộ, 1 tin chưa đọc" });
  expect(collaborationApi.messages).not.toHaveBeenCalled(); expect(collaborationApi.read).not.toHaveBeenCalled();
});

it("opens the peer conversation and marks only the visible incoming message read", async () => {
  const user = userEvent.setup(); mount(<ChatWidget />);
  await user.click(await screen.findByRole("button", { name: "Mở chat nội bộ, 1 tin chưa đọc" }));
  await user.click(screen.getByRole("button", { name: /Nguyễn An/ }));
  await screen.findByText(message.body);
  await waitFor(() => expect(collaborationApi.read).toHaveBeenCalledWith("peer", "message1"));
  await user.click(screen.getByRole("button", { name: "Thu gọn chat" }));
  expect(screen.queryByLabelText("Tin nhắn")).toBeNull();
});

it("sends a tagged message with a stable retry identifier and keeps failed draft", async () => {
  const user = userEvent.setup(); vi.mocked(collaborationApi.send).mockRejectedValue(new Error("offline")); mount(<ChatWidget />);
  await user.click(await screen.findByRole("button", { name: "Mở chat nội bộ, 1 tin chưa đọc" }));
  await user.click(screen.getByRole("button", { name: /Nguyễn An/ }));
  await user.type(screen.getByLabelText("Tin nhắn"), "Xem giúp mình"); await user.click(screen.getByRole("button", { name: "@ Nhắc" }));
  await user.click(screen.getByRole("button", { name: "Gửi" }));
  await screen.findByRole("alert");
  const first = vi.mocked(collaborationApi.send).mock.calls[0]![1];
  expect(first.mentions).toEqual(["peer"]); expect(first.body).toContain("@Nguyễn An");
  await user.click(screen.getByRole("button", { name: "Gửi" }));
  await waitFor(() => expect(collaborationApi.send).toHaveBeenCalledTimes(2));
  expect(vi.mocked(collaborationApi.send).mock.calls[1]![1].id).toBe(first.id);
});

it("a message deep link opens only after scoped API lookup", async () => {
  state.params = new URLSearchParams("message=message1"); vi.mocked(collaborationApi.message).mockResolvedValue(message); mount(<ChatWidget />);
  await screen.findByText(message.body);
  expect(collaborationApi.message).toHaveBeenCalledWith("message1");
  expect(collaborationApi.messages).toHaveBeenCalledWith("peer", undefined);
  fireEvent.keyDown(screen.getByRole("region", { name: "Chat nội bộ" }), { key: "Escape" });
  expect(screen.queryByLabelText("Tin nhắn")).toBeNull();
});
