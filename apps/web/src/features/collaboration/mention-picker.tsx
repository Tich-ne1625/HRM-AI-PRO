"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useAuth } from "../auth/auth-provider";
import { collaborationApi, type Person } from "./api";

export function MentionPicker({ selected, change, post, ownDepartment, departmentId, disabled }: { selected: Person[]; change: (people: Person[]) => void; post?: string; ownDepartment?: boolean; departmentId?: string; disabled?: boolean }) {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const people = useQuery({ queryKey: ["collaboration", user?.id, "mention-people", post, ownDepartment, departmentId, search, page], queryFn: () => collaborationApi.people(search, page, post, ownDepartment, departmentId), enabled: open && !!user });
  return <div className="mention-picker">
    <button type="button" className="secondary" disabled={disabled} onClick={() => setOpen(!open)} aria-expanded={open}>@ Nhắc người liên quan{selected.length ? ` (${selected.length})` : ""}</button>
    {selected.length > 0 && <div className="mention-chips">{selected.map((person) => <button type="button" key={person.id} disabled={disabled} onClick={() => change(selected.filter((item) => item.id !== person.id))} aria-label={`Bỏ nhắc ${person.name}`}>@{person.name} ×</button>)}</div>}
    {open && <div className="mention-options"><label>Tìm người để @nhắc<input value={search} maxLength={100} onChange={(e) => { setSearch(e.target.value); setPage(1); }} /></label>
      <p className="help-text">Chỉ người thuộc phạm vi bài viết. Tối đa 10 người.</p>
      {people.isPending && <p>Đang tìm…</p>}{people.isError && <p role="alert">Không tải được danh sách. <button type="button" onClick={() => void people.refetch()}>Thử lại</button></p>}
      {people.data?.items.map((person) => <label key={person.id} className="mention-option"><input type="checkbox" disabled={disabled || (selected.length >= 10 && !selected.some((item) => item.id === person.id))} checked={selected.some((item) => item.id === person.id)} onChange={(e) => change(e.target.checked ? [...selected, person] : selected.filter((item) => item.id !== person.id))} /><span>{person.name}<small>{person.department ?? "Toàn công ty"}</small></span></label>)}
      {people.data && !people.data.items.length && <p>Không tìm thấy người phù hợp.</p>}
      <div className="collab-pagination"><button type="button" disabled={page === 1} onClick={() => setPage(page - 1)}>Trước</button><span>Trang {page}</span><button type="button" disabled={!people.data?.has_more} onClick={() => setPage(page + 1)}>Sau</button></div>
    </div>}
  </div>;
}
