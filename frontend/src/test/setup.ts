import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

vi.stubEnv("VITE_API_URL", "http://api.test");
vi.stubEnv("VITE_SUPABASE_URL", "http://supabase.test");
vi.stubEnv("VITE_SUPABASE_PUBLISHABLE_KEY", "publica");
