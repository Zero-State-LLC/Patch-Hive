/**
 * Tabs — a tab list that works by keyboard as well as by pointer. Arrow keys move between tabs
 * (skipping disabled ones) and select them, Home and End jump to the ends, and only the selected
 * tab sits in the page's tab order. Panels pair with tabs through tabId and panelId.
 */
import { useEffect } from "react";
import type { KeyboardEvent } from "react";
import { panelId, tabId } from "@/lib/tabs";
import { useScrollEdges } from "@/lib/useScrollEdges";

export interface TabItem<K extends string> {
  key: K;
  label: string;
  disabled?: boolean;
}

export default function Tabs<K extends string>({
  label,
  tabs,
  active,
  onChange,
  idPrefix = "",
  listClassName = "tab-list",
  tabClassName = "tab",
}: {
  label: string;
  tabs: TabItem<K>[];
  active: K;
  onChange: (key: K) => void;
  /** Keeps ids unique when a page has more than one tab list. */
  idPrefix?: string;
  /** A page with its own tab look (sign in) passes its classes. */
  listClassName?: string;
  tabClassName?: string;
}) {
  const listRef = useScrollEdges<HTMLDivElement>();

  // When the row scrolls (a phone), keep the selected tab whole and centred, clear of the fades.
  useEffect(() => {
    const list = listRef.current;
    const selected = list?.querySelector<HTMLElement>('[aria-selected="true"]');
    if (!list || !selected || list.scrollWidth <= list.clientWidth) return;
    const row = list.getBoundingClientRect();
    const tab = selected.getBoundingClientRect();
    list.scrollLeft += tab.left - row.left - (row.width - tab.width) / 2;
  }, [active, listRef]);

  const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    const enabled = tabs.filter((tab) => !tab.disabled);
    const at = enabled.findIndex((tab) => tab.key === active);
    const target = {
      ArrowRight: enabled[(at + 1) % enabled.length],
      ArrowLeft: enabled[(at - 1 + enabled.length) % enabled.length],
      Home: enabled[0],
      End: enabled[enabled.length - 1],
    }[event.key];
    if (!target) return;
    event.preventDefault();
    onChange(target.key);
    document.getElementById(tabId(idPrefix, target.key))?.focus();
  };

  return (
    <div ref={listRef} className={listClassName} role="tablist" aria-label={label}>
      {tabs.map((tab) => {
        const selected = tab.key === active;
        return (
          <button
            key={tab.key}
            id={tabId(idPrefix, tab.key)}
            type="button"
            role="tab"
            className={tabClassName}
            aria-selected={selected}
            aria-controls={selected ? panelId(idPrefix, tab.key) : undefined}
            tabIndex={selected ? 0 : -1}
            disabled={tab.disabled}
            onClick={() => onChange(tab.key)}
            onKeyDown={onKeyDown}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
