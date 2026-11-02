"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useSession } from "../SessionProvider";
import { readEmergencyDraft, writeEmergencyDraft, emergencyDraftIsPersistent } from "@/lib/emergencyDrafts.mjs";

// Access the browser property lazily: security settings can block the getter itself.
const recoveryStorage = {
  getItem: key => sessionStorage.getItem(key),
  setItem: (key, value) => sessionStorage.setItem(key, value),
  removeItem: key => sessionStorage.removeItem(key),
};

// Session storage survives reauthentication without sharing drafts between admins.
export default function useEmergencyDraft(kind, initial = null, recordId = "") {
  const { user } = useSession();
  const owner = user.id;
  const [value, setValue] = useState(initial);
  const current = useRef(initial);
  const [warning, setWarning] = useState("");
  useEffect(() => {
    try {
      const restored = readEmergencyDraft(recoveryStorage, owner, kind, recordId);
      if (restored) {
        current.current = restored;
        setValue(restored);
      }
      if (!emergencyDraftIsPersistent(owner, kind, recordId)) setWarning("Recovery is kept only in this open tab because browser storage is unavailable. Do not reload or close the tab.");
    } catch {
      setWarning("A recovery copy could not be read. Keep this page open while editing.");
    }
  }, [owner, kind, recordId]);
  const update = useCallback(change => {
    const next = typeof change === "function" ? change(current.current) : change;
    current.current = next;
    try {
      writeEmergencyDraft(recoveryStorage, owner, kind, recordId, next);
      setWarning("");
    } catch {
      setWarning("Your changes are in this page, but a recovery copy could not be saved. Keep the page open.");
    }
    setValue(next);
  }, [owner, kind, recordId]);
  return [value, update, warning];
}
