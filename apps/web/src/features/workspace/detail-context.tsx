"use client";

import { createContext } from "react";

export type DetailLocation = { kind: "cycle" | "employee" | "kpis" | "feedback-summary" | "performance" | "assignment" | "administration"; id: string; cycle: string; href: string };

export function detailLocation(href: string): DetailLocation | null {
  const url = new URL(href, "http://workspace.local");
  if (url.origin !== "http://workspace.local") return null;
  const path = url.pathname;
  const cycle = url.searchParams.get("cycle_id") ?? "";
  const employee = /^\/employees\/([^/]+)(?:\/(kpis|feedback|performance))?$/.exec(path);
  if (employee) {
    if (employee[2] && !cycle) return null;
    const kind = employee[2] === "feedback" ? "feedback-summary" : employee[2] === "kpis" ? "kpis" : employee[2] === "performance" ? "performance" : "employee";
    return { kind, id: employee[1]!, cycle, href };
  }
  const review = /^\/review-cycles\/([^/]+)$/.exec(path);
  if (review) return { kind: "cycle", id: review[1]!, cycle: review[1]!, href };
  const feedback = /^\/feedback\/([^/]+)$/.exec(path);
  if (feedback) return { kind: "assignment", id: feedback[1]!, cycle, href };
  if (path === "/feedback-administration" && url.searchParams.has("participant_id")) return { kind: "administration", id: url.searchParams.get("participant_id")!, cycle, href };
  return null;
}

export const DetailContext = createContext<{ open: (location: DetailLocation) => void; close: () => void; active: boolean } | null>(null);
