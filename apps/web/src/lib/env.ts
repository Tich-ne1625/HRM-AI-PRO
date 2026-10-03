import { z } from "zod";

const serverEnvironmentSchema = z.object({
  API_INTERNAL_URL: z.url().default("http://localhost:8000"),
});

export function getApiInternalUrl(): string {
  return serverEnvironmentSchema.parse({
    API_INTERNAL_URL: process.env.API_INTERNAL_URL,
  }).API_INTERNAL_URL;
}

