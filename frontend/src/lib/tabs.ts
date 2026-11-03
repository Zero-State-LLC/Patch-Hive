/** Ids that pair a tab with its panel (components/Tabs.tsx and the page's tabpanel). */
export const tabId = (prefix: string, key: string) => `${prefix}tab-${key}`;
export const panelId = (prefix: string, key: string) => `${prefix}panel-${key}`;
