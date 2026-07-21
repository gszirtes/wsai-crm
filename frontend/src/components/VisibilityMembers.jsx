import React, { useEffect, useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { Users, X } from "lucide-react";
import api from "../api";
import { Button, Select, Badge, Spinner } from "./common";

// Shared by DealDetail and ProjectDetail: a visibility toggle + member list/
// invite panel. entityType is "deal" or "project" (matches the /api/deals
// and /api/projects member/visibility sub-routes, and the EventLog
// entity_type value). The backend enforces set_visibility/invite_members
// capabilities and blocks removing the owner -- this component just hides
// the affordances a non-capable/write user wouldn't be allowed to use
// anyway, it doesn't re-implement those checks.
export default function VisibilityMembers({ entityType, entityId, visibility, ownerId, onVisibilityChange, writable }) {
  const { t } = useTranslation();
  const [members, setMembers] = useState(null);
  const [users, setUsers] = useState([]);
  const [selected, setSelected] = useState("");

  const load = useCallback(() => {
    api.get(`/${entityType}s/${entityId}/members`).then((r) => setMembers(r.data));
  }, [entityType, entityId]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { api.get("/users/directory").then((r) => setUsers(r.data)); }, []);

  const toggleVisibility = async () => {
    const next = visibility === "public" ? "private" : "public";
    const r = await api.patch(`/${entityType}s/${entityId}/visibility`, { visibility: next });
    onVisibilityChange(r.data.visibility);
  };

  const invite = async () => {
    if (!selected) return;
    await api.post(`/${entityType}s/${entityId}/members`, { user_id: selected });
    setSelected("");
    load();
  };

  const removeMember = async (userId) => {
    await api.delete(`/${entityType}s/${entityId}/members/${userId}`);
    load();
  };

  const memberIds = new Set((members || []).map((m) => m.user_id));
  const invitable = users.filter((u) => u.active && !memberIds.has(u.id));

  return (
    <div className="border border-border rounded-sm p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-display font-bold flex items-center gap-2">
          <Users size={18} className="text-primary" />{t("members.title")}
        </h3>
        <div className="flex items-center gap-2">
          <Badge value={visibility === "public" ? "won" : "lost"} label={t(`members.${visibility}`)} />
          {writable && (
            <Button variant="subtle" className="py-1.5 px-3 text-xs" onClick={toggleVisibility}
              data-testid={`toggle-visibility-${entityType}`}>
              {visibility === "public" ? t("members.makePrivate") : t("members.makePublic")}
            </Button>
          )}
        </div>
      </div>

      {!members ? <Spinner /> : (
        <div className="space-y-2">
          {members.map((m) => (
            <div key={m.user_id} data-testid={`member-row-${m.user_id}`} className="flex items-center justify-between text-sm py-1.5">
              <span>{m.name || m.email}{m.user_id === ownerId ? ` · ${t("members.owner")}` : ""}</span>
              {writable && m.user_id !== ownerId && (
                <button onClick={() => removeMember(m.user_id)} data-testid={`remove-member-${m.user_id}`}
                  className="text-muted hover:text-danger transition-colors">
                  <X size={14} />
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {writable && visibility === "private" && (
        <div className="flex items-center gap-2 mt-4">
          <Select value={selected} onChange={(e) => setSelected(e.target.value)} data-testid={`invite-select-${entityType}`}>
            <option value="">{t("members.pick")}</option>
            {invitable.map((u) => <option key={u.id} value={u.id}>{u.name} ({u.email})</option>)}
          </Select>
          <Button onClick={invite} data-testid={`invite-btn-${entityType}`}>{t("members.invite")}</Button>
        </div>
      )}
    </div>
  );
}
