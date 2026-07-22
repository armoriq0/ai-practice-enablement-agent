import type { SVGProps } from "react";

type Props = SVGProps<SVGSVGElement>;
const Icon = ({ children, ...props }: Props) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>{children}</svg>;

export const Shield = (p: Props) => <Icon {...p}><path d="M12 3 20 6v5c0 5-3.4 8.5-8 10-4.6-1.5-8-5-8-10V6l8-3Z"/><path d="m9 12 2 2 4-4"/></Icon>;
export const Orbit = (p: Props) => <Icon {...p}><circle cx="12" cy="12" r="2.2"/><ellipse cx="12" cy="12" rx="9" ry="4.5"/><ellipse cx="12" cy="12" rx="4.5" ry="9" transform="rotate(45 12 12)"/></Icon>;
export const Target = (p: Props) => <Icon {...p}><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="4"/><path d="M12 2v3M22 12h-3"/></Icon>;
export const Activity = (p: Props) => <Icon {...p}><path d="M3 12h4l2.3-6 4.1 12 2.3-6H21"/></Icon>;
export const Gavel = (p: Props) => <Icon {...p}><path d="m14 5 5 5M12 7l5 5M4 20l8-8M3 17l4 4"/></Icon>;
export const Alert = (p: Props) => <Icon {...p}><path d="M12 3 2.7 19h18.6L12 3Z"/><path d="M12 9v4M12 16.5v.1"/></Icon>;
export const Scroll = (p: Props) => <Icon {...p}><path d="M6 3h12v15a3 3 0 0 1-3 3H6a3 3 0 0 0 3-3V6a3 3 0 0 0-3-3Z"/><path d="M6 3a3 3 0 0 0-3 3v1h6V6a3 3 0 0 0-3-3ZM12 8h3M12 12h3"/></Icon>;
export const Settings = (p: Props) => <Icon {...p}><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-1.6v-.2h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z"/></Icon>;
export const Plus = (p: Props) => <Icon {...p}><path d="M12 5v14M5 12h14"/></Icon>;
export const Refresh = (p: Props) => <Icon {...p}><path d="M20 11a8 8 0 1 0-2.3 5.7"/><path d="M20 5v6h-6"/></Icon>;
export const Chevron = (p: Props) => <Icon {...p}><path d="m9 18 6-6-6-6"/></Icon>;
export const Close = (p: Props) => <Icon {...p}><path d="m6 6 12 12M18 6 6 18"/></Icon>;
