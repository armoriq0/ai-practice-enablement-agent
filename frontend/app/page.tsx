"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { Activity, Alert, Chevron, Close, Gavel, Orbit, Plus, Refresh, Scroll, Settings, Shield, Target } from "./components/icons";
import { createMission, DashboardData, loadDashboard, loadMissionDetails, Mission, MissionDetails, missionAction, resolveEscalation } from "./lib/api";

const EMPTY: DashboardData = { missions: [], runs: [], decisions: [], escalations: [], audit: [] };
const nav = [
  ["Command center", Activity], ["Missions", Target], ["Agent activity", Orbit],
  ["ArmorIQ decisions", Gavel], ["Exceptions", Alert], ["Audit trail", Scroll],
] as const;

function title(value = "") { return value.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase()); }
function ago(value?: string) {
  if (!value) return "—";
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return new Date(value).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function Badge({ value }: { value: string }) {
  const key = value.toLowerCase();
  const tone = ["permit", "completed", "active", "running", "verified"].some((x) => key.includes(x)) ? "success"
    : ["deny", "failed", "critical", "stopped"].some((x) => key.includes(x)) ? "danger"
    : ["escalate", "pending", "paused", "warning", "open"].some((x) => key.includes(x)) ? "warning" : "neutral";
  return <span className={`badge ${tone}`}><i />{title(value)}</span>;
}

export default function Console() {
  const [data, setData] = useState(EMPTY);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [active, setActive] = useState("Command center");
  const [modal, setModal] = useState(false);
  const [busy, setBusy] = useState("");
  const [details, setDetails] = useState<MissionDetails | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try { setData(await loadDashboard()); setError(""); }
    catch (e) { setError(e instanceof Error ? e.message : "Control plane unavailable"); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => {
    const initial = window.setTimeout(refresh, 0);
    const timer = window.setInterval(refresh, 30000);
    return () => { window.clearTimeout(initial); window.clearInterval(timer); };
  }, [refresh]);

  const completed = useMemo(() => data.missions.find((mission) => mission.policy?.continuous) || data.missions.find((mission) => mission.status.toLowerCase() === "completed"), [data.missions]);
  useEffect(() => {
    if (!completed) return;
    let current = true;
    loadMissionDetails(completed.id).then((value) => { if (current) setDetails(value); }).catch((e) => { if (current) setError(e instanceof Error ? e.message : "Mission details unavailable"); });
    return () => { current = false; };
  }, [completed]);

  const stats = useMemo(() => {
    const activeMissions = data.missions.filter((m) => ["active", "running"].includes(m.status.toLowerCase())).length;
    const activeRuns = data.runs.filter((r) => ["active", "running", "executing"].includes(r.status.toLowerCase())).length;
    const permits = data.decisions.filter((d) => d.outcome.toLowerCase() === "permit").length;
    const decided = data.decisions.filter((d) => ["permit", "deny"].includes(d.outcome.toLowerCase())).length;
    return { activeMissions, activeRuns, authorization: decided ? Math.round(permits / decided * 100) : 0, exceptions: data.escalations.filter((e) => e.status.toLowerCase() === "open").length };
  }, [data]);

  async function act(id: string, action: "start" | "pause" | "resume" | "stop") {
    setBusy(id);
    try { await missionAction(id, action); await refresh(); } catch (e) { setError(e instanceof Error ? e.message : "Action failed"); }
    finally { setBusy(""); }
  }

  return <div className="shell">
    <aside>
      <div className="brand"><div className="brand-mark"><Shield /></div><div><strong>ArmorIQ</strong><span>PARTNER OPERATIONS</span></div></div>
      <nav aria-label="Primary navigation">
        <p>OPERATIONS</p>
        {nav.slice(0, 5).map(([label, Icon]) => <button key={label} className={active === label ? "selected" : ""} onClick={() => setActive(label)}><Icon />{label}{label === "Exceptions" && stats.exceptions > 0 ? <em>{stats.exceptions}</em> : null}</button>)}
        <p>GOVERNANCE</p>
        {nav.slice(5).map(([label, Icon]) => <button key={label} className={active === label ? "selected" : ""} onClick={() => setActive(label)}><Icon />{label}</button>)}
      </nav>
      <div className="side-footer"><button><Settings />Configuration</button><div className="identity"><span>AK</span><div><strong>Alex Kim</strong><small>Mission operator</small></div><i /></div></div>
    </aside>

    <main>
      <header><div><div className="eyebrow"><span className="live-dot"/> AUTONOMOUS SYSTEM ONLINE</div><h1>{active === "Command center" && completed ? "Mission results" : active}</h1><p>{active === "Command center" && completed ? "Completed findings stay visible while the next partner search runs in the background." : "Inspect the autonomous workflow and its governed execution history."}</p></div><div className="header-actions"><button className="icon-button" onClick={refresh} aria-label="Refresh"><Refresh className={loading ? "spin" : ""}/></button><button className="primary" onClick={() => setModal(true)}><Plus /> New mission</button></div></header>

      {error && <div className="offline"><Alert/><div><strong>Control plane connection</strong><span>{error}. Retrying automatically; no actions will execute while authorization is unavailable.</span></div><button onClick={refresh}>Retry</button></div>}

      {active !== "Command center" ? <SectionView active={active} data={data}/> : completed ? <MissionResult mission={completed} details={details}/> : <><section className="metrics">
        <Metric label="Active missions" value={stats.activeMissions} detail={`${data.missions.length} total configured`} icon={<Target/>}/>
        <Metric label="Agents working" value={stats.activeRuns} detail={`${data.runs.length} recent runs`} icon={<Orbit/>} pulse/>
        <Metric label="Auto-authorized" value={`${stats.authorization}%`} detail="of resolved decisions" icon={<Shield/>}/>
        <Metric label="Needs attention" value={stats.exceptions} detail="exception escalations" icon={<Alert/>} warning={stats.exceptions > 0}/>
      </section>

      <div className="grid-main">
        <section className="panel missions-panel">
          <PanelHead title="Mission portfolio" sub="Objectives delegated to the agent team" action="View all"/>
          {data.missions.length ? <div className="mission-list">{data.missions.slice(0, 5).map((m) => {
            const progress = Number.isFinite(m.progress) ? m.progress : m.target_meetings ? Math.round((m.meetings_booked || 0) / m.target_meetings * 100) : 0;
            const action = m.status.toLowerCase() === "paused" ? "resume" : ["active", "running"].includes(m.status.toLowerCase()) ? "pause" : "start";
            return <article className="mission" key={m.id}>
              <div className="mission-top"><div><div className="mission-name"><strong>{m.name}</strong><Badge value={m.status}/></div><p>{m.objective}</p></div><button className="ghost" disabled={busy === m.id} onClick={() => act(m.id, action)}>{busy === m.id ? "Working…" : title(action)}</button></div>
              <div className="mission-meta"><span><b>{m.accounts_qualified || 0}</b> qualified</span><span><b>{m.meetings_booked || 0}/{m.target_meetings || 0}</b> meetings</span><span>{progress}% complete</span></div>
              <div className="progress"><i style={{ width: `${Math.min(100, progress)}%` }}/></div>
            </article>;
          })}</div> : <Empty icon={<Target/>} title="No missions yet" text="Set a business objective and the autonomous team will begin planning." button="Create mission" onClick={() => setModal(true)}/>} 
        </section>

        <section className="panel activity-panel">
          <PanelHead title="Live agent activity" sub="Execution across the agent team"/><div className="timeline">
          {data.runs.length ? data.runs.slice(0, 7).map((run) => <div className="run" key={run.id}><div className={`agent-glyph ${run.status.toLowerCase()}`}><Orbit/></div><div><div><strong>{title(run.agent_name)}</strong><Badge value={run.status}/></div><p>{run.current_step || "Processing delegated mission work"}</p><small>{ago(run.started_at)}{run.duration_ms ? ` · ${(run.duration_ms / 1000).toFixed(1)}s` : ""}</small></div></div>) : <Empty icon={<Orbit/>} title="Agents are standing by" text="Activity appears here after a mission starts."/>}
          </div>
        </section>
      </div>

      <div className="grid-bottom">
        <section className="panel"><PanelHead title="ArmorIQ decisions" sub="Recent policy authorizations" action="Open policy console"/>
          <div className="table-wrap"><table><thead><tr><th>Decision</th><th>Requested action</th><th>Agent</th><th>Time</th></tr></thead><tbody>
          {data.decisions.slice(0, 6).map((d) => <tr key={d.id}><td><Badge value={d.outcome}/></td><td><strong>{title(d.action)}</strong><small>{d.reason || "Within delegated authority"}</small></td><td>{title(d.agent_name || "system")}</td><td>{ago(d.created_at)}</td></tr>)}
          {!data.decisions.length && <tr><td colSpan={4}><div className="table-empty">No authorization decisions recorded yet.</div></td></tr>}
          </tbody></table></div>
        </section>
        <section className="panel exception-panel"><PanelHead title="Exception queue" sub="Only novel risk reaches you"/>
          {data.escalations.length ? <div className="exceptions">{data.escalations.slice(0, 4).map((e) => <article key={e.id}><div className={`severity ${e.severity.toLowerCase()}`}><Alert/></div><div><strong>{e.title}</strong><p>{e.reason}</p><small>{title(e.agent_name || "agent")} · {ago(e.created_at)}</small><div className="decision-actions"><button disabled={busy === e.id} onClick={async () => { setBusy(e.id); await resolveEscalation(e.id, "deny"); await refresh(); setBusy(""); }}>Deny</button><button className="allow" disabled={busy === e.id} onClick={async () => { setBusy(e.id); await resolveEscalation(e.id, "allow"); await refresh(); setBusy(""); }}>Allow once</button></div></div></article>)}</div> : <div className="clear-state"><Shield/><strong>All within policy</strong><p>No agent actions currently require operator judgment.</p></div>}
        </section>
      </div>

      <section className="trust-strip"><div><Shield/><span><strong>Fail-closed authorization</strong><small>External actions require a valid, action-bound ArmorIQ permit</small></span></div><div><span className="chain">◈—◈—◈</span><span><strong>Audit chain healthy</strong><small>{data.audit.length} recent events available for verification</small></span></div><button onClick={() => setActive("Audit trail")}>Inspect audit trail <Chevron/></button></section></>}
    </main>
    {modal && <MissionModal close={() => setModal(false)} done={async () => { setModal(false); await refresh(); }}/>} 
  </div>;
}

function SectionView({ active, data }: { active: string; data: DashboardData }) {
  if (active === "Missions") return <section className="panel section-view"><PanelHead title="All missions" sub="Continuous and one-time objectives"/><div className="mission-list">{data.missions.map((mission) => <article className="mission" key={mission.id}><div className="mission-top"><div><div className="mission-name"><strong>{mission.name}</strong><Badge value={mission.status}/></div><p>{mission.objective}</p></div></div><div className="mission-meta"><span><b>{mission.accounts_qualified || 0}</b> qualified</span><span><b>{mission.meetings_booked || 0}/{mission.target_meetings || 0}</b> meetings</span><span>{mission.policy?.continuous ? "Runs daily" : "One time"}</span></div></article>)}</div></section>;
  if (active === "Agent activity") return <section className="panel section-view"><PanelHead title="Agent activity" sub="Specialist execution history"/><div className="timeline">{data.runs.map((run) => <div className="run" key={run.id}><div className={`agent-glyph ${run.status.toLowerCase()}`}><Orbit/></div><div><div><strong>{title(run.agent_name)}</strong><Badge value={run.status}/></div><p>{run.current_step || "Processing delegated mission work"}</p><small>{ago(run.started_at)}</small></div></div>)}</div></section>;
  if (active === "ArmorIQ decisions") return <section className="panel section-view"><PanelHead title="ArmorIQ decisions" sub="Permit and deny outcomes across missions"/><DecisionTable decisions={data.decisions}/></section>;
  if (active === "Exceptions") return <section className="panel section-view"><PanelHead title="Exception queue" sub="Actions requiring operator attention"/>{data.escalations.length ? <div className="exceptions">{data.escalations.map((item) => <article key={item.id}><div className={`severity ${item.severity.toLowerCase()}`}><Alert/></div><div><strong>{title(item.title)}</strong><p>{item.reason}</p><small>{ago(item.created_at)}</small></div></article>)}</div> : <div className="clear-state"><Shield/><strong>All within policy</strong><p>No open exceptions require attention.</p></div>}</section>;
  return <section className="panel section-view"><PanelHead title="Audit trail" sub="Tamper-evident workflow events"/><div className="audit-list">{data.audit.map((event) => <article key={event.id}><Scroll/><div><strong>{title(event.event_type)}</strong><p>{event.summary || "Recorded workflow event"}</p><small>{title(event.actor || "system")} · {ago(event.created_at)}</small></div>{event.integrity_verified && <Badge value="Verified"/>}</article>)}</div></section>;
}

function DecisionTable({ decisions }: { decisions: DashboardData["decisions"] }) {
  return <div className="table-wrap"><table><thead><tr><th>Decision</th><th>Requested action</th><th>Agent</th><th>Time</th></tr></thead><tbody>{decisions.map((decision) => <tr key={decision.id}><td><Badge value={decision.outcome}/></td><td><strong>{title(decision.action)}</strong><small>{decision.reason || "Within delegated authority"}</small></td><td>{title(decision.agent_name || "system")}</td><td>{ago(decision.created_at)}</td></tr>)}{!decisions.length && <tr><td colSpan={4}><div className="table-empty">No authorization decisions recorded.</div></td></tr>}</tbody></table></div>;
}

function MissionResult({ mission, details }: { mission: Mission; details: MissionDetails | null }) {
  if (!details) return <section className="panel"><Empty icon={<Orbit/>} title="Loading mission result" text="Retrieving partners, evidence, and policy decisions."/></section>;
  const denied = details.decisions.find((decision) => decision.outcome.toLowerCase() === "deny");
  return <div className="result-view">
    <section className="result-hero"><div><div className="mission-name"><h2>{mission.name}</h2><Badge value={mission.status}/></div><p>{mission.objective}</p></div><div className="result-summary"><span><strong>{details.accounts.length}</strong>discovered</span><span><strong>{mission.accounts_qualified}</strong>qualified</span><span><strong>{details.decisions.filter((d) => d.outcome.toLowerCase() === "permit").length}</strong>authorized</span></div></section>
    {details.accounts.map((account) => <article className="account-result" key={account.id}>
      <div className="account-head"><div><span className="kicker">SELECTED PARTNER</span><h2>{account.name}</h2><a href={`https://${account.domain}`} target="_blank" rel="noreferrer">{account.domain}</a></div><div className="score"><small>FIT SCORE</small><strong>{account.score ?? "—"}</strong><span>Tier {account.tier ?? "—"}</span></div></div>
      <div className="result-grid"><section className="result-card"><h3>Partnership case</h3><p>{account.data.value_hypothesis || account.data.strategy || "No partnership hypothesis recorded."}</p></section><section className="result-card"><h3>Verified contact</h3>{account.data.contact?.email ? <><strong>{account.data.contact.name || account.data.contact.role || "Business contact"}</strong>{account.data.contact.name && account.data.contact.role && <span>{account.data.contact.role}</span>}<a href={`mailto:${account.data.contact.email}`}>{account.data.contact.email}</a>{account.data.contact.source && <a className="source-link" href={account.data.contact.source} target="_blank" rel="noreferrer">Public source <Chevron/></a>}</> : account.data.contact?.name ? <><strong>{account.data.contact.name}</strong><span>{account.data.contact.role || "Relevant decision-maker"}</span><p>No exact publicly sourced professional email found.</p></> : <p>No relevant public professional contact found.</p>}</section></div>
      <section className="result-card evidence-card"><h3>Evidence used</h3><div className="evidence-list">{account.data.evidence?.map((item, index) => <a href={item.url} target="_blank" rel="noreferrer" key={`${item.url}-${index}`}><span>{index + 1}</span><p>{item.claim}</p><Chevron/></a>)}</div></section>
      <section className="result-card draft-card"><div><h3>Generated outreach</h3><Badge value={denied ? "Not sent — policy denied" : account.state}/></div><strong>{account.data.subject || "No subject generated"}</strong><pre>{account.data.body || "No outreach draft generated."}</pre>{denied && <p className="policy-outcome"><Shield/>ArmorIQ stopped delivery: {title(denied.reason || "policy denied")}</p>}</section>
    </article>)}
    <section className="panel decision-path"><PanelHead title="ArmorIQ decision path" sub="Authorization at each mission stage"/><div>{details.decisions.map((decision) => <div className="decision-step" key={decision.id}><Badge value={decision.outcome}/><span><strong>{title(decision.action)}</strong><small>{decision.reason || "Within delegated authority"}</small></span></div>)}</div></section>
  </div>;
}

function Metric({ label, value, detail, icon, pulse, warning }: { label: string; value: string | number; detail: string; icon: React.ReactNode; pulse?: boolean; warning?: boolean }) {
  return <article className={`metric ${warning ? "warn" : ""}`}><div className="metric-icon">{icon}{pulse && <i/>}</div><div><span>{label}</span><strong>{value}</strong><small>{detail}</small></div></article>;
}
function PanelHead({ title: heading, sub, action }: { title: string; sub: string; action?: string }) { return <div className="panel-head"><div><h2>{heading}</h2><p>{sub}</p></div>{action && <button>{action}<Chevron/></button>}</div>; }
function Empty({ icon, title: heading, text, button, onClick }: { icon: React.ReactNode; title: string; text: string; button?: string; onClick?: () => void }) { return <div className="empty">{icon}<strong>{heading}</strong><p>{text}</p>{button && <button onClick={onClick}>{button}</button>}</div>; }

function MissionModal({ close, done }: { close: () => void; done: () => void }) {
  const [saving, setSaving] = useState(false); const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setSaving(true); setError(""); const form = new FormData(event.currentTarget);
    try { await createMission({ name: String(form.get("name")), objective: String(form.get("objective")), target_meetings: Number(form.get("target")) }); await done(); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not create mission"); setSaving(false); }
  }
  return <div className="modal-backdrop" role="presentation" onMouseDown={(e) => { if (e.target === e.currentTarget) close(); }}><div className="modal" role="dialog" aria-modal="true" aria-labelledby="mission-title"><button className="modal-close" onClick={close}><Close/></button><div className="modal-icon"><Target/></div><span className="kicker">DELEGATE AN OBJECTIVE</span><h2 id="mission-title">Create an autonomous mission</h2><p>Define the outcome. The supervisor will plan work, delegate specialist agents, and request ArmorIQ authorization before external actions.</p><form onSubmit={submit}><label>Mission name<input name="name" required maxLength={80} placeholder="Q3 AI security partnerships" autoFocus/></label><label>Business objective<textarea name="objective" required minLength={20} rows={4} placeholder="Identify and engage qualified AI security consulting partners…"/></label><label>Target first meetings<input name="target" required type="number" min="1" max="100" defaultValue="3"/></label><div className="policy-note"><Shield/><span><strong>Governed autonomy enabled</strong><small>All agent tools remain bounded by your organization policy.</small></span></div>{error && <div className="form-error">{error}</div>}<div className="modal-actions"><button type="button" onClick={close}>Cancel</button><button className="primary" disabled={saving}>{saving ? "Delegating…" : "Create & delegate"}</button></div></form></div></div>;
}
