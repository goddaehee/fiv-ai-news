"use client";

import { useEffect, useState } from "react";
import { isRepoSaved, toggleSavedRepo } from "@/lib/saved";

export function SaveRepoButton({ slug }: { slug: string }) {
  const [saved, setSaved] = useState(false);
  useEffect(() => {
    setSaved(isRepoSaved(slug));
  }, [slug]);
  return (
    <button
      type="button"
      className={saved ? "save-btn on" : "save-btn"}
      onClick={() => setSaved(toggleSavedRepo(slug))}
    >
      {saved ? "저장됨" : "저장"}
    </button>
  );
}
