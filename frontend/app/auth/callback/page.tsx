"use client";

/**
 * Shell handoff callback (value-lab RS256 JWT in ?token=).
 *
 * Soft-Cases backend does not yet implement POST /api/v1/auth/handoff.
 * We strip the token from the URL and land on the app home. When handoff
 * is added, mirror ai-library/frontend/app/auth/callback/page.tsx.
 */

import { useSearchParams, useRouter } from "next/navigation";
import { useEffect, Suspense } from "react";

function CallbackContent() {
  const searchParams = useSearchParams();
  const router = useRouter();

  useEffect(() => {
    const token = searchParams.get("token");
    if (!token) {
      router.replace("/");
      return;
    }
    router.replace("/");
  }, [searchParams, router]);

  return (
    <div className="min-h-[40vh] flex items-center justify-center">
      <p className="text-sm text-muted">Opening Soft Cases…</p>
    </div>
  );
}

export default function SoftCasesAuthCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-[40vh] flex items-center justify-center text-muted text-sm">
          Loading…
        </div>
      }
    >
      <CallbackContent />
    </Suspense>
  );
}
