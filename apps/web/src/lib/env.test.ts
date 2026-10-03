import { afterEach, describe, expect, it } from "vitest";

import { getApiInternalUrl } from "./env";

const originalApiInternalUrl = process.env.API_INTERNAL_URL;

describe("getApiInternalUrl", () => {
  afterEach(() => {
    if (originalApiInternalUrl === undefined) {
      delete process.env.API_INTERNAL_URL;
    } else {
      process.env.API_INTERNAL_URL = originalApiInternalUrl;
    }
  });

  it.each(["ftp://api.example.com", "file:///tmp/api.sock"]) (
    "rejects unsupported URL %s",
    (url) => {
      process.env.API_INTERNAL_URL = url;

      expect(() => getApiInternalUrl()).toThrow();
    },
  );
});
