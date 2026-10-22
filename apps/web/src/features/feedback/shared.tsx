"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { ApiClientError } from "../../lib/api-client";
import type { Relationship, Status, Versions, Assignment } from "./api";

export const relationships: Record<Relationship, string> = { SELF: "Tự đánh giá", MANAGER: "Quản lý", PEER: "Đồng nghiệp", SUBORDINATE: "Cấp dưới" };
export const statuses: Record<Status, string> = { OPEN: "Chờ phản hồi", SUBMITTED: "Đã gửi", CANCELLED: "Đã hủy" };
export const versions = (row: Assignment): Versions => ({ expected_assignment_version: row.version, expected_evidence_version: row.evidence_version });
export const deadline = (value: string | null) => value ? new Intl.DateTimeFormat("vi-VN", { dateStyle: "medium", timeStyle: "short", timeZoneName: undefined }).format(new Date(value)) : "Không giới hạn thời gian trong chu kỳ";
export function useDisplayClock() {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 60_000); return () => clearInterval(timer); }, []);
  return now;
}
export function FeedbackError({ error, reload }: { error: Error; reload?: () => void }) {
  const messages: Record<string, string> = {
    stale_assignment_version: "Phân công đã thay đổi. Tải lại và kiểm tra trước khi gửi tiếp.",
    stale_evidence_version: "Dữ liệu đánh giá đã thay đổi. Nội dung bạn nhập được giữ lại; hãy tải phiên bản mới và xác nhận lại.",
    feedback_already_submitted: "Phản hồi đã được ghi nhận trước đó. Tải lại để xem kết quả.",
    deadline_passed: "Đã quá hạn. HR cần gia hạn phân công trước khi bạn gửi.",
    assignment_not_open: "Phân công đã gửi hoặc đã hủy; hãy tải lại để kiểm tra.",
    assignment_already_exists: "Người này đã được phân công. Hãy mở phân công cũ và khôi phục nếu đã hủy.",
    reviewer_inactive: "Tài khoản người đánh giá lịch sử đang bị khóa. ADMIN cần khôi phục đúng tài khoản này.",
    reviewer_ineligible: "Người đánh giá không còn đáp ứng quan hệ được chọn.",
    required_coverage_conflict: "Phân công bắt buộc cần được giữ. SELF và MANAGER không được thay người hoặc hủy.",
    required_relationship_exists: "Quan hệ bắt buộc đã được phân công.",
    cycle_not_active: "Chu kỳ chưa hoạt động hoặc đã đóng.", participant_finalized: "Hồ sơ đánh giá đã chốt.",
    assignment_limit_reached: "Mỗi người tham gia chỉ có tối đa 100 phân công đang dùng.",
    assignment_not_found: "Không tìm thấy phân công trong phạm vi của bạn.",
    forbidden: "Bạn không có quyền thực hiện thao tác này.",
    validation_error: "Kiểm tra lại mức đánh giá, nhận xét và thời hạn.",
  };
  return <div className="feedback-error" role="alert"><p>{error instanceof ApiClientError ? messages[error.code] ?? "Không thể thực hiện. Hãy kiểm tra rồi thử lại." : "Không thể kết nối. Nội dung chưa gửi vẫn được giữ."}</p>
    {reload && <button type="button" className="secondary" onClick={reload}>Tải phiên bản mới, giữ nội dung</button>}</div>;
}
export function useFeedbackRefresh() {
  const cache = useQueryClient();
  return async () => { await Promise.all(["feedback", "reviews", "performance", "ai"].map((key) => cache.invalidateQueries({ queryKey: [key] }))); };
}
export function SubmissionContent({ rating, comment }: { rating: number; comment: string }) {
  return <><p><strong>Mức đánh giá: {rating}/5</strong></p><p className="plain-comment">{comment || "Không có nhận xét."}</p></>;
}
