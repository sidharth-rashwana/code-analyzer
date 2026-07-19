import { useRef, useState, useEffect } from "react";

/**
 * Tracks the pixel size of a container element via ResizeObserver.
 * Returns [ref, {width, height}] — attach ref to the element you want measured.
 */
export function useContainerSize() {
  const ref = useRef(null);
  const [size, setSize] = useState({ width: 800, height: 600 });

  useEffect(() => {
    if (!ref.current) return undefined;
    const el = ref.current;
    const obs = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry) {
        setSize({
          width: entry.contentRect.width,
          height: entry.contentRect.height,
        });
      }
    });
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  return [ref, size];
}
