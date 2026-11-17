import { FileText, FlaskConical, LayoutDashboard, MessageSquareText, Settings, ShieldCheck, Sparkles, type LucideIcon } from "lucide-react";

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  description: string;
}

export const NAV: NavItem[] = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, description: "Overview and activity" },
  { to: "/documents", label: "Documents", icon: FileText, description: "Upload and browse your library" },
  { to: "/chat", label: "Chat", icon: MessageSquareText, description: "Ask questions with citations" },
  { to: "/insights", label: "Insights", icon: Sparkles, description: "Summaries, key facts and comparisons" },
  { to: "/evaluation", label: "Evaluation", icon: FlaskConical, description: "How accurate DocuMind is" },
  { to: "/settings", label: "Settings", icon: Settings, description: "Account, theme and system" },
];


export const ADMIN_NAV: NavItem = {
  to: "/admin",
  label: "Admin",
  icon: ShieldCheck,
  description: "All users, documents and activity",
};

/** Navigation for the signed-in user; the Admin page is only listed for administrators */
export function navFor(role?: string): NavItem[] {
  return role === "admin" ? [...NAV.slice(0, -1), ADMIN_NAV, NAV[NAV.length - 1]] : NAV;
}
