import { cleanup, configure } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => { cleanup(); });

// Allow asynchronous DOM updates while local Docker builds compete for CPU.
configure({ asyncUtilTimeout: 5000 });
