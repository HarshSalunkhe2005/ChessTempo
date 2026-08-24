import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

// The anon key is safe to ship to the browser — Supabase's Row Level
// Security policies (see supabase/schema.sql) are what actually gate
// access, not this key's secrecy.
export const supabase = createClient(supabaseUrl, supabaseAnonKey);
