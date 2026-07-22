export type Mission = {
  id: string;
  name: string;
  objective: string;
  status: string;
  progress: number;
  target_meetings: number;
  meetings_booked: number;
  accounts_qualified: number;
  policy?: { continuous?: boolean };
  created_at?: string;
};

export type AgentRun = {
  id: string;
  agent_name: string;
  mission_id?: string;
  status: string;
  current_step?: string;
  started_at?: string;
  duration_ms?: number;
};

export type Decision = {
  id: string;
  action: string;
  agent_name?: string;
  outcome: string;
  reason?: string;
  created_at?: string;
};

export type Escalation = {
  id: string;
  title: string;
  reason: string;
  severity: string;
  status: string;
  agent_name?: string;
  created_at?: string;
};

export type AuditEvent = {
  id: string;
  event_type: string;
  actor?: string;
  summary?: string;
  created_at?: string;
  integrity_verified?: boolean;
};

export type DashboardData = {
  missions: Mission[];
  runs: AgentRun[];
  decisions: Decision[];
  escalations: Escalation[];
  audit: AuditEvent[];
};

export type MissionAccount = {
  id: string; name: string; domain: string; state: string;
  score?: number; tier?: string;
  data: {
    evidence?: Array<{ url: string; claim: string; public: boolean }>;
    contact?: { role?: string; email?: string; source?: string };
    value_hypothesis?: string; strategy?: string; subject?: string; body?: string;
  };
};

export type MissionDetails = { accounts: MissionAccount[]; decisions: Decision[] };

const API = "/api/proxy/api/v1";

function asList<T>(value: unknown): T[] {
  if (Array.isArray(value)) return value as T[];
  if (value && typeof value === "object") {
    const object = value as Record<string, unknown>;
    for (const key of ["items", "results", "data", "missions", "runs", "decisions", "events", "escalations"]) {
      if (Array.isArray(object[key])) return object[key] as T[];
    }
  }
  return [];
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    ...init,
    cache: "no-store",
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${response.status})`);
  }
  return response.json();
}

export async function loadDashboard(): Promise<DashboardData> {
  const calls = [
    request<unknown>("/missions"),
    request<unknown>("/agent-runs?limit=12"),
    request<unknown>("/policy-decisions?limit=12"),
    request<unknown>("/escalations?status=open&limit=8"),
    request<unknown>("/audit?limit=10"),
  ];
  const results = await Promise.allSettled(calls);
  if (results.every((item) => item.status === "rejected")) {
    throw new Error("Unable to reach the ArmorIQ control plane");
  }
  const value = (index: number) => results[index].status === "fulfilled" ? results[index].value : [];
  return {
    missions: asList<Mission>(value(0)),
    runs: asList<AgentRun>(value(1)),
    decisions: asList<Decision>(value(2)),
    escalations: asList<Escalation>(value(3)),
    audit: asList<AuditEvent>(value(4)),
  };
}

export async function loadMissionDetails(id: string): Promise<MissionDetails> {
  const encoded = encodeURIComponent(id);
  const [accounts, decisions] = await Promise.all([
    request<unknown>(`/missions/${encoded}/accounts`),
    request<unknown>(`/missions/${encoded}/policy-decisions`),
  ]);
  return { accounts: asList<MissionAccount>(accounts), decisions: asList<Decision>(decisions) };
}

export async function createMission(input: { name: string; objective: string; target_meetings: number }) {
  const mission = await request<Mission>("/missions", { method: "POST", body: JSON.stringify({ ...input, auto_execute: true, continuous: true }) });
  return request<Mission>(`/missions/${encodeURIComponent(mission.id)}/start`, { method: "POST" });
}

export function missionAction(id: string, action: "start" | "pause" | "resume" | "stop") {
  return request<Mission>(`/missions/${encodeURIComponent(id)}/${action}`, { method: "POST" });
}

export function resolveEscalation(id: string, resolution: "allow" | "deny") {
  return request(`/escalations/${encodeURIComponent(id)}/resolve`, {
    method: "POST",
    body: JSON.stringify({ resolution }),
  });
}
