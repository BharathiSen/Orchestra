"use client";

import { useMemo, useSyncExternalStore } from "react";

import type { User } from "./api";

const TOKEN_KEY = "orchestra_token";
const USER_KEY = "orchestra_user";

// Components read the session through useSession(), which subscribes here.
// localStorage has no change event within the same tab, so the writers below
// notify subscribers themselves; the `storage` event covers other tabs.
const listeners = new Set<() => void>();

function notify() {
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  const onStorage = (event: StorageEvent) => {
    if (event.key === null || event.key === TOKEN_KEY || event.key === USER_KEY) {
      listener();
    }
  };
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", onStorage);
  };
}

export function saveSession(token: string, user: User) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
  notify();
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  notify();
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

function getRawUser(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(USER_KEY);
}

function parseUser(raw: string | null): User | null {
  if (!raw) return null;
  try {
    return JSON.parse(raw) as User;
  } catch {
    return null;
  }
}

export function getStoredUser(): User | null {
  return parseUser(getRawUser());
}

const noopSubscribe = () => () => {};

export type Session = {
  /**
   * False during server rendering and hydration, when localStorage cannot be
   * read. A missing token only means "signed out" once this is true —
   * redirecting before then would bounce every signed-in user to /login.
   */
  ready: boolean;
  token: string | null;
  user: User | null;
};

/** The current session, kept in sync across components and browser tabs. */
export function useSession(): Session {
  const ready = useSyncExternalStore(noopSubscribe, () => true, () => false);
  const token = useSyncExternalStore(subscribe, getToken, () => null);
  const rawUser = useSyncExternalStore(subscribe, getRawUser, () => null);
  const user = useMemo(() => parseUser(rawUser), [rawUser]);
  return { ready, token, user };
}
