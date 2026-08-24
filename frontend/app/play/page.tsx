"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabaseClient";
import ChessGame from "@/components/ChessGame";

export default function PlayPage() {
  const router = useRouter();
  const [checkingAuth, setCheckingAuth] = useState(true);
  const [loggedIn, setLoggedIn] = useState(false);

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!session) {
        router.replace("/login");
      } else {
        setLoggedIn(true);
      }
      setCheckingAuth(false);
    });
  }, [router]);

  if (checkingAuth) return null;
  if (!loggedIn) return null; // redirecting

  return <ChessGame />;
}
