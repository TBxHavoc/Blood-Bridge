import { createContext, useContext } from "react";

import type { BloodGroup } from "../lib/types";

export type ViewName =
  | "Overview"
  | "Inventory"
  | "Find supplies"
  | "Request inbox"
  | "Request blood"
  | "Reports"
  | "Live eRaktKosh"
  | "FAQ";

export interface NavParams {
  type?: BloodGroup;
  bank?: string;
}

export interface NavValue {
  view: ViewName;
  params: NavParams;
  go: (view: ViewName, params?: NavParams) => void;
}

export const NavContext = createContext<NavValue | null>(null);

export function useNav(): NavValue {
  const ctx = useContext(NavContext);
  if (!ctx) throw new Error("useNav must be used within a NavContext provider");
  return ctx;
}

export function getWorkspaceItems(role?: string): { view: ViewName; label: string }[] {
  if (role === "bloodbank_user") {
    return [
      { view: "Overview", label: "Overview" },
      { view: "Inventory", label: "Inventory" },
      { view: "Request inbox", label: "Request inbox" },
      { view: "Live eRaktKosh", label: "Live Bangalore Stock" },
      { view: "Request blood", label: "Request blood" },
      { view: "Reports", label: "Reports" },
    ];
  }
  return [
    { view: "Overview", label: "Overview" },
    { view: "Inventory", label: "Inventory" },
    { view: "Find supplies", label: "Find supplies" },
    { view: "Live eRaktKosh", label: "Live Bangalore Stock" },
    { view: "Request blood", label: "Request blood" },
    { view: "Reports", label: "Reports" },
  ];
}

export const WORKSPACE_ITEMS: { view: ViewName; label: string }[] = [
  { view: "Overview", label: "Overview" },
  { view: "Inventory", label: "Inventory" },
  { view: "Find supplies", label: "Find supplies" },
  { view: "Live eRaktKosh", label: "Live Bangalore Stock" },
  { view: "Request blood", label: "Request blood" },
  { view: "Reports", label: "Reports" },
];

export const HELP_ITEM: { view: ViewName; label: string } = {
  view: "FAQ",
  label: "FAQ",
};

