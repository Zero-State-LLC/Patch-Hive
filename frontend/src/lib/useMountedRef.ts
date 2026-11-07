import { useEffect, useRef } from "react";

/**
 * Whether the component is still on screen. Setting state on one that has left does nothing, but
 * navigating still happens, so an answer that moves the screen checks this first.
 */
export function useMountedRef() {
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  return mounted;
}
