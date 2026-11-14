"use client";

import { useQuery } from "@tanstack/react-query";
import { useId, useState } from "react";
import { reviewApi, type Participant } from "../cycles/api";
import { ReferencePicker } from "../organization/employee-form";
import { Pagination } from "../organization/shared";
import { FeedbackError } from "./shared";

export function AssignmentWorkspace({ initialCycle, selected, onSelect }: { initialCycle?: string; selected?: string; onSelect: (participant: Participant | null, cycle: string) => void }) {
  const id = useId();
  const [cycle, setCycle] = useState(initialCycle ?? ""), [cyclePage, setCyclePage] = useState(1);
  const [status, setStatus] = useState("ACTIVE"), [page, setPage] = useState(1), [department, setDepartment] = useState(""), [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const cycles = useQuery({ queryKey: ["reviews", "assignment-cycles", status, cyclePage], queryFn: () => reviewApi.cycles({ status, page: cyclePage }) });
  const participants = useQuery({ queryKey: ["reviews", "assignment-participants", cycle, department, q, page], queryFn: () => reviewApi.participants(cycle, { page, q, department_id: department }), enabled: !!cycle });
  return <section className="auth-card wide" aria-label="Chọn hồ sơ để phân công">
    <p className="eyebrow">BƯỚC 1 · CHỌN HỒ SƠ</p><h2>Phân công cho người được đánh giá</h2>
    <p>Chọn kỳ rồi chọn nhân viên cần thu thập phản hồi. Nhân viên chưa có phiếu vẫn xuất hiện ở đây.</p>
    <div className="form-grid"><div>
      <label htmlFor={`${id}-status`}>Trạng thái kỳ</label><select id={`${id}-status`} value={status} onChange={(event) => { setStatus(event.target.value); setCyclePage(1); setCycle(""); onSelect(null, ""); }}><option value="ACTIVE">Đang hoạt động — có thể phân công</option><option value="CLOSED">Đã đóng — chỉ tra cứu</option></select>
      <label htmlFor={`${id}-cycle`}>Chu kỳ cần phân công</label><select id={`${id}-cycle`} value={cycle} onChange={(event) => { setCycle(event.target.value); setPage(1); onSelect(null, event.target.value); }}><option value="">Chọn chu kỳ</option>{cycle && !cycles.data?.items.some((row) => row.id === cycle) && <option value={cycle}>Chu kỳ đang chọn</option>}{cycles.data?.items.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</select>
      {cycles.isPending && <p role="status">Đang tải chu kỳ…</p>}{cycles.isError && <FeedbackError error={cycles.error} />}
      {cycles.data && !cycles.data.items.length && <p>Không có kỳ ở trạng thái này. Chuẩn bị và kích hoạt kỳ tại Chu kỳ đánh giá trước khi giao phiếu.</p>}
      {cycles.data && cycles.data.total > 20 && <Pagination page={cyclePage} total={cycles.data.total} pending={cycles.isFetching} onPage={setCyclePage} />}
    </div>{cycle && <ReferencePicker kind="departments" emptyLabel="Tất cả phòng ban" activeOnly={false} value={department} labelOverride="Lọc người được đánh giá theo phòng ban" onChange={(value) => { setDepartment(value); setPage(1); }} />}</div>
    {cycle && <><form className="filters" onSubmit={(event) => { event.preventDefault(); setQ(String(new FormData(event.currentTarget).get("q") ?? "")); setPage(1); }}><label htmlFor={`${id}-search`}>Tìm người được đánh giá</label><input id={`${id}-search`} name="q" maxLength={100} value={search} onChange={(event) => setSearch(event.target.value)} /><button>Tìm nhân viên</button><button type="button" className="secondary" onClick={() => { setDepartment(""); setSearch(""); setQ(""); setPage(1); }}>Bỏ lọc</button></form>
      {participants.isPending && <p role="status">Đang tải người tham gia…</p>}{participants.isError && <FeedbackError error={participants.error} />}
      {participants.data && !participants.isError && <><div className="assignment-subjects" role="group" aria-label="Người được đánh giá">{participants.data.items.map((row) => <button type="button" key={row.id} className={`secondary assignment-subject${selected === row.id ? " is-selected" : ""}`} aria-pressed={selected === row.id} onClick={() => onSelect(row, cycle)}><strong>{row.employee_code} · {row.display_name}</strong><span>{row.department_name}</span><small>{selected === row.id ? "Đang phân công cho người này" : "Chọn để phân công phản hồi"}</small></button>)}</div>{!participants.data.items.length && <p>Không có người tham gia phù hợp. Thử bỏ bộ lọc hoặc kiểm tra danh sách trong kỳ.</p>}<Pagination page={page} total={participants.data.total} pending={participants.isFetching} onPage={setPage} /></>}
    </>}
  </section>;
}
