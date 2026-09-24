"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { supabase } from "@/lib/supabaseClient";
import { api, ProfileResponse } from "@/lib/api";
import { DIFFICULTY_LABELS } from "@/lib/chessDisplay";

const DIFFICULTY_OPTIONS = Object.keys(DIFFICULTY_LABELS);

type Notice = { kind: "ok" | "error"; text: string } | null;

function NoticeLine({ notice }: { notice: Notice }) {
  if (!notice) return null;
  return (
    <p className={notice.kind === "error" ? "error-text" : "hint-eval"} style={{ marginBottom: 0 }}>
      {notice.text}
    </p>
  );
}

export default function SettingsPage() {
  const router = useRouter();
  const [checkingAuth, setCheckingAuth] = useState(true);
  const [profile, setProfile] = useState<ProfileResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [nameNotice, setNameNotice] = useState<Notice>(null);
  const [savingName, setSavingName] = useState(false);

  const [difficulty, setDifficulty] = useState("casual");
  const [difficultyNotice, setDifficultyNotice] = useState<Notice>(null);
  const [savingDifficulty, setSavingDifficulty] = useState(false);

  const [newPassword, setNewPassword] = useState("");
  const [passwordNotice, setPasswordNotice] = useState<Notice>(null);
  const [savingPassword, setSavingPassword] = useState(false);

  const [confirmText, setConfirmText] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [deleteNotice, setDeleteNotice] = useState<Notice>(null);

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!session) {
        router.replace("/login");
        return;
      }
      setCheckingAuth(false);
      api
        .getProfile()
        .then((p) => {
          setProfile(p);
          setName(p.full_name ?? "");
          setDifficulty(p.starting_difficulty);
        })
        .catch((e) => setLoadError(e.message));
    });
  }, [router]);

  if (checkingAuth) return null;

  const saveName = async (e: React.FormEvent) => {
    e.preventDefault();
    setNameNotice(null);
    setSavingName(true);
    try {
      const updated = await api.updateProfile({ full_name: name });
      setProfile(updated);
      setNameNotice({ kind: "ok", text: "Name updated." });
    } catch (err) {
      setNameNotice({ kind: "error", text: (err as Error).message });
    } finally {
      setSavingName(false);
    }
  };

  const saveDifficulty = async () => {
    setDifficultyNotice(null);
    setSavingDifficulty(true);
    try {
      const updated = await api.updateProfile({ starting_difficulty: difficulty });
      setProfile(updated);
      setDifficultyNotice({ kind: "ok", text: "Difficulty reset — the bot now plays at that level." });
    } catch (err) {
      setDifficultyNotice({ kind: "error", text: (err as Error).message });
    } finally {
      setSavingDifficulty(false);
    }
  };

  const savePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordNotice(null);
    setSavingPassword(true);
    const { error } = await supabase.auth.updateUser({ password: newPassword });
    setSavingPassword(false);
    if (error) {
      setPasswordNotice({ kind: "error", text: error.message });
    } else {
      setNewPassword("");
      setPasswordNotice({ kind: "ok", text: "Password changed." });
    }
  };

  const deleteAccount = async () => {
    setDeleteNotice(null);
    setDeleting(true);
    try {
      await api.deleteAccount();
      await supabase.auth.signOut();
      router.push("/");
    } catch (err) {
      setDeleting(false);
      setDeleteNotice({ kind: "error", text: (err as Error).message });
    }
  };

  const difficultyChanged = profile !== null && difficulty !== profile.starting_difficulty;

  return (
    <div className="play-shell">
      <nav className="nav">
        <Link href="/" className="nav-brand" style={{ textDecoration: "none", color: "inherit" }}>
          <span className="brand-mark">♞</span>
          <span className="brand-name">ChessTempo</span>
        </Link>
        <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
          <Link href="/play" className="btn-link" style={{ textDecoration: "none" }}>
            Play
          </Link>
          <Link href="/profile" className="btn-link" style={{ textDecoration: "none" }}>
            Profile
          </Link>
        </div>
      </nav>

      <div style={{ maxWidth: 560, margin: "0 auto", padding: "44px 32px" }}>
        <h1 style={{ fontFamily: "var(--font-display)", fontSize: 26, margin: "0 0 24px" }}>Settings</h1>
        {loadError && <p className="error-text">{loadError}</p>}

        <div className="panel-card">
          <div className="status-eyebrow">Display name</div>
          <form onSubmit={saveName}>
            <input
              className="field"
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={80}
              required
              style={{ animation: "none" }}
            />
            <button className="btn" style={{ animation: "none" }} disabled={savingName || !name.trim()}>
              {savingName ? "Saving..." : "Save name"}
            </button>
            <NoticeLine notice={nameNotice} />
          </form>
        </div>

        <div className="panel-card">
          <div className="status-eyebrow">Difficulty</div>
          <p className="hint-eval" style={{ marginTop: 0 }}>
            The bot adjusts itself as you play. Picking a level here resets it to that level&apos;s starting
            strength — useful if it drifted too hard or too easy.
          </p>
          <div className="difficulty-picker">
            {DIFFICULTY_OPTIONS.map((key) => (
              <button
                type="button"
                key={key}
                className={`difficulty-option${difficulty === key ? " selected" : ""}`}
                onClick={() => setDifficulty(key)}
              >
                <span className="difficulty-option-label">{DIFFICULTY_LABELS[key]}</span>
              </button>
            ))}
          </div>
          <button
            className="btn"
            style={{ animation: "none" }}
            onClick={saveDifficulty}
            disabled={savingDifficulty || !difficultyChanged}
          >
            {savingDifficulty ? "Resetting..." : "Reset to this level"}
          </button>
          <NoticeLine notice={difficultyNotice} />
        </div>

        <div className="panel-card">
          <div className="status-eyebrow">Change password</div>
          <form onSubmit={savePassword}>
            <input
              className="field"
              type="password"
              placeholder="New password (min 8 characters)"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              minLength={8}
              required
              style={{ animation: "none" }}
            />
            <button className="btn" style={{ animation: "none" }} disabled={savingPassword || newPassword.length < 8}>
              {savingPassword ? "Saving..." : "Change password"}
            </button>
            <NoticeLine notice={passwordNotice} />
          </form>
        </div>

        <div className="panel-card" style={{ borderColor: "color-mix(in oklab, var(--danger) 50%, var(--border))" }}>
          <div className="status-eyebrow" style={{ color: "var(--danger)" }}>
            Delete account
          </div>
          <p className="hint-eval" style={{ marginTop: 0 }}>
            Permanently deletes your account, your game history, and your personalized bot. This can&apos;t be
            undone. Type <strong>DELETE</strong> to confirm.
          </p>
          <input
            className="field"
            value={confirmText}
            onChange={(e) => setConfirmText(e.target.value)}
            placeholder="DELETE"
            style={{ animation: "none" }}
          />
          <button
            className="btn"
            style={{ animation: "none", background: "var(--danger)", color: "#fff" }}
            onClick={deleteAccount}
            disabled={deleting || confirmText !== "DELETE"}
          >
            {deleting ? "Deleting..." : "Delete my account"}
          </button>
          <NoticeLine notice={deleteNotice} />
        </div>
      </div>
    </div>
  );
}
