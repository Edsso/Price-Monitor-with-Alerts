import { createClient } from "@supabase/supabase-js";
import { env } from "./env";

/** Usado apenas para login; os dados passam pela API. */
export const supabase = createClient(env.supabaseUrl, env.supabaseKey);
