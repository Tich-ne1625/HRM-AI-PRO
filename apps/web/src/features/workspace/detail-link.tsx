"use client";

import Link from "next/link";
import { useContext, type ComponentProps } from "react";
import { DetailContext, detailLocation } from "./detail-context";

export default function DetailLink({ onClick, ...props }: ComponentProps<typeof Link>) {
  const context = useContext(DetailContext);
  return <Link {...props} onClick={(event) => {
    onClick?.(event);
    if (!context || event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || props.target === "_blank" || typeof props.href !== "string") return;
    const location = detailLocation(props.href);
    if (location) { event.preventDefault(); context.open(location); }
    else if (context.active && ["/employees", "/review-cycles", "/feedback"].includes(props.href)) { event.preventDefault(); context.close(); }
  }} />;
}
