import { useEffect, useState } from "react";

import "./tokens.css";
import { api, type Me } from "./api";
import AssignmentList from "./screens/AssignmentList";
import Result from "./screens/Result";
import Round from "./screens/Round";
import Sitting from "./screens/Sitting";
import Tutor from "./screens/Tutor";

/**
 * Read the current route out of the location hash.
 *
 * A hash router rather than a routing library: five screens with no nested
 * layouts do not pay for a dependency, and the back button still works.
 *
 * @returns The hash without its leading `#`, defaulting to `/`.
 */
function useRoute(): string {
  const [route, setRoute] = useState(() => window.location.hash.slice(1) || "/");
  useEffect(() => {
    const onChange = () => setRoute(window.location.hash.slice(1) || "/");
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return route;
}

/** Send the browser to a route without a full reload. */
export function go(route: string): void {
  window.location.hash = route;
}

/**
 * The student surface.
 *
 * Identity is fetched once and passed down, because every screen carries the
 * name, class and student code strip that ADR-13 requires on a machine several
 * students share.
 */
export default function App() {
  const route = useRoute();
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .me()
      .then(setMe)
      .catch((cause: Error) => setError(cause.message));
  }, []);

  if (error !== null) {
    return (
      <div className="page">
        <div className="error" role="alert">
          {error}
        </div>
      </div>
    );
  }
  if (me === null) {
    return <div className="page">Đang tải…</div>;
  }

  const attempt = /^\/attempt\/([^/]+)$/.exec(route);
  if (attempt) return <Sitting me={me} attemptId={attempt[1]} />;

  const result = /^\/attempt\/([^/]+)\/result$/.exec(route);
  if (result) return <Result me={me} attemptId={result[1]} />;

  const tutor = /^\/attempt\/([^/]+)\/tutor$/.exec(route);
  if (tutor) return <Tutor me={me} attemptId={tutor[1]} />;

  const round = /^\/round\/([^/]+)\/([^/]+)$/.exec(route);
  if (round) return <Round me={me} attemptId={round[1]} roundId={round[2]} />;

  return <AssignmentList me={me} />;
}
