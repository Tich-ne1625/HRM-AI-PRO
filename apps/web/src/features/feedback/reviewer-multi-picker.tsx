"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useId, useState } from "react";
import { ReferencePicker } from "../organization/employee-form";
import { Pagination } from "../organization/shared";
import { feedbackApi, type Relationship, type ReviewerOption } from "./api";
import { FeedbackError } from "./shared";

export function ReviewerMultiPicker({ participant, relationship, value, onChange, onBusy, limit = 100 }: { participant: string; relationship: Relationship; value: ReviewerOption[]; onChange: (rows: ReviewerOption[]) => void; onBusy?: (busy: boolean) => void; limit?: number }) {
  const id = useId();
  const [department, setDepartment] = useState(""), [page, setPage] = useState(1), [search, setSearch] = useState(""), [q, setQ] = useState("");
  const [selectionError, setSelectionError] = useState("");
  useEffect(() => { if (search === q) return; const timer = setTimeout(() => { setQ(search); setPage(1); }, 300); return () => clearTimeout(timer); }, [search, q]);
  const filters = { department_id: department, q, available_only: true };
  const query = useQuery({ queryKey: ["feedback", "administration", "batch-options", participant, relationship, department, q, page], queryFn: () => feedbackApi.options(participant, relationship, { ...filters, page }) });
  const selectAll = useMutation({ mutationFn: () => feedbackApi.options(participant, relationship, { ...filters, page: 1, page_size: 100 }), onSuccess: (result) => {
    const rows = new Map(value.map((row) => [row.reviewer_id, row]));
    for (const row of result.items) if (row.is_active && !row.existing_assignment_id) rows.set(row.reviewer_id, row);
    if (result.total > limit || rows.size > limit) { setSelectionError(`Hồ sơ còn chỗ cho ${limit} phiếu mới. Thu hẹp bộ lọc hoặc bỏ bớt người đã chọn.`); return; }
    setSelectionError(""); onChange([...rows.values()]);
  } });
  useEffect(() => { onBusy?.(selectAll.isPending); return () => onBusy?.(false); }, [selectAll.isPending, onBusy]);
  const choose = (row: ReviewerOption) => onChange(value.some((item) => item.reviewer_id === row.reviewer_id) ? value.filter((item) => item.reviewer_id !== row.reviewer_id) : [...value, row]);
  const selectedIds = new Set(value.map((row) => row.reviewer_id));
  return <div className="reviewer-multi-picker">
    <p className="help-text">Chọn nhiều người đánh giá cho cùng nhân viên. Lọc theo phòng ban hiện tại; hệ thống vẫn kiểm tra đúng quan hệ trong kỳ. Người đã được giao hoặc bị khóa không được chọn lại.</p>
    <div className="form-grid"><ReferencePicker kind="departments" emptyLabel="Tất cả phòng ban" activeOnly={false} labelOverride="Phòng ban người đánh giá" value={department} onChange={(next) => { setDepartment(next); setPage(1); }} /><div><label htmlFor={`${id}-search`}>Tìm người đánh giá theo mã hoặc tên</label><input id={`${id}-search`} maxLength={100} value={search} onChange={(event) => setSearch(event.target.value)} /></div></div>
    <div className="row-actions"><button type="button" className="secondary" disabled={!query.data?.total || query.data.total > limit || query.isFetching || search !== q || selectAll.isPending} onClick={() => selectAll.mutate()}>Chọn toàn bộ kết quả lọc ({query.data?.total ?? 0})</button><button type="button" className="secondary" disabled={!value.length || selectAll.isPending} onClick={() => onChange([])}>Bỏ chọn tất cả</button><strong>Đã chọn {value.length}/{limit} người có thể giao thêm</strong></div>
    {!!query.data && query.data.total > limit && <p>Hồ sơ còn chỗ cho {limit} phiếu mới trong giới hạn 100 phiếu. Hãy lọc phòng ban hoặc tìm tên để thu hẹp trước khi chọn tất cả.</p>}
    {selectionError && <p role="alert">{selectionError}</p>}{query.isPending && <p role="status">Đang tìm người đánh giá…</p>}{query.isError && <FeedbackError error={query.error} />}{selectAll.isError && <FeedbackError error={selectAll.error} />}
    {query.data && !query.isError && <><div className="reviewer-checkboxes" role="group" aria-label="Chọn nhiều người đánh giá">{query.data.items.map((row) => <label className="reviewer-checkbox" key={row.reviewer_id}><input type="checkbox" checked={selectedIds.has(row.reviewer_id)} disabled={!row.is_active || !!row.existing_assignment_id || selectAll.isPending || (value.length >= limit && !selectedIds.has(row.reviewer_id))} onChange={() => choose(row)} /><span>{row.employee_code} · {row.display_name}</span></label>)}</div>{!query.data.items.length && <p>Không còn người chưa được giao phù hợp bộ lọc và quan hệ này. Phiếu đã hủy cần được khôi phục ở danh sách phân công.</p>}<Pagination page={page} total={query.data.total} pending={query.isFetching || selectAll.isPending} onPage={setPage} /></>}
    {!!value.length && <details className="selected-reviewers"><summary>Danh sách đã chọn ({value.length}) — giữ khi đổi trang hoặc bộ lọc</summary><ul>{value.map((row) => <li key={row.reviewer_id}><span>{row.employee_code} · {row.display_name}</span><button type="button" className="secondary" disabled={selectAll.isPending} onClick={() => choose(row)}>Bỏ {row.employee_code}</button></li>)}</ul></details>}
  </div>;
}
