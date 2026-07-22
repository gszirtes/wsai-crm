import React, { useEffect, useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { DragDropContext, Droppable, Draggable } from "@hello-pangea/dnd";
import { Plus, Pencil, Trash2, LayoutGrid, List } from "lucide-react";
import api, { formatApiError } from "../api";
import { useAuth, can } from "../auth";
import { Button, Input, Select, Field, Modal, Badge, Spinner, Textarea } from "../components/common";

const STAGES = ["lead", "qualified", "proposal", "negotiation", "won", "lost"];
const SOURCES = ["inbound", "outreach", "referral", "other"];
const LEAD_TYPES = ["single", "double"];
const empty = {
  title: "", value: 0, currency: "EUR", stage: "lead", company_id: "", contact_id: "", notes: "",
  source: "", unassigned: false, lead_type: "single",
  contract_company_id: "", contract_contact_id: "", referred_by_contact_id: "",
};

export default function Deals() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const navigate = useNavigate();
  const writable = can.write(user);
  const [items, setItems] = useState(null);
  const [companies, setCompanies] = useState([]);
  const [contacts, setContacts] = useState([]);
  const [view, setView] = useState("board");
  const [modal, setModal] = useState(false);
  const [form, setForm] = useState(empty);
  const [editing, setEditing] = useState(null);
  const [error, setError] = useState("");
  const [ourTurnOnly, setOurTurnOnly] = useState(false);
  const [unassignedOnly, setUnassignedOnly] = useState(false);

  const load = useCallback(() => {
    api.get("/deals").then((r) => setItems(r.data))
      .catch((e) => setError(formatApiError(e.response?.data?.detail) || e.message));
  }, []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    api.get("/companies").then((r) => setCompanies(r.data));
    api.get("/contacts").then((r) => setContacts(r.data));
  }, []);

  const openNew = () => { setForm(empty); setEditing(null); setModal(true); };
  const openEdit = (d) => {
    setForm({
      ...empty, ...d, company_id: d.company_id || "", contact_id: d.contact_id || "",
      contract_company_id: d.contract_company_id || "", contract_contact_id: d.contract_contact_id || "",
      referred_by_contact_id: d.referred_by_contact_id || "",
    });
    setEditing(d.id); setModal(true);
  };
  const save = async () => {
    const payload = {
      ...form, value: parseFloat(form.value) || 0,
      company_id: form.company_id || null, contact_id: form.contact_id || null,
      source: form.source || null,
      contract_company_id: form.lead_type === "double" ? (form.contract_company_id || null) : null,
      contract_contact_id: form.lead_type === "double" ? (form.contract_contact_id || null) : null,
      referred_by_contact_id: form.referred_by_contact_id || null,
    };
    try {
      if (editing) await api.put(`/deals/${editing}`, payload);
      else await api.post("/deals", payload);
      setModal(false); load();
    } catch (e) {
      console.error("Deals request failed:", e);
      setError(formatApiError(e.response?.data?.detail) || e.message);
    }
  };
  const del = async (id) => {
    if (!window.confirm(t("common.confirmDelete"))) return;
    await api.delete(`/deals/${id}`); load();
  };
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const toggleUnassigned = (e) => setForm({ ...form, unassigned: e.target.checked });

  const eur = (n) => (n == null ? "—" : "€" + new Intl.NumberFormat().format(n));

  const onDragEnd = async (result) => {
    if (!result.destination || !writable) return;
    const newStage = result.destination.droppableId;
    const id = result.draggableId;
    const deal = items.find((d) => d.id === id);
    if (!deal || deal.stage === newStage) return;
    setItems(items.map((d) => (d.id === id ? { ...d, stage: newStage } : d)));
    try {
      await api.patch(`/deals/${id}/stage`, { stage: newStage });
    } catch (e) {
      console.error("Deals request failed:", e);
      setError(formatApiError(e.response?.data?.detail) || e.message);
    } finally {
      // Resync with the server regardless of outcome -- on failure this
      // reverts the optimistic move instead of leaving the card stuck in
      // the wrong column until a manual refresh.
      load();
    }
  };

  const visibleItems = (items || [])
    .filter((d) => !ourTurnOnly || d.ball_in_court === "us")
    .filter((d) => !unassignedOnly || !d.owner_id);
  const byStage = (s) => visibleItems.filter((d) => d.stage === s);
  const stageTotal = (s) => byStage(s).reduce((a, d) => a + (d.value || 0), 0);

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3">
        <h1 className="font-display text-2xl sm:text-3xl font-bold tracking-tight">{t("deal.title")}</h1>
        <div className="flex items-center gap-2">
          <div className="flex border border-border rounded-sm overflow-hidden">
            <button onClick={() => setView("board")} data-testid="deals-view-board" className={`p-2 transition-colors ${view === "board" ? "bg-primary text-white" : "text-muted hover:bg-surface"}`}><LayoutGrid size={16} /></button>
            <button onClick={() => setView("list")} data-testid="deals-view-list" className={`p-2 transition-colors ${view === "list" ? "bg-primary text-white" : "text-muted hover:bg-surface"}`}><List size={16} /></button>
          </div>
          <Button variant={ourTurnOnly ? "primary" : "subtle"} className="py-1.5 px-3 text-xs"
            onClick={() => setOurTurnOnly(!ourTurnOnly)} data-testid="ball-in-court-filter">
            {t("deal.ballInCourtFilter")}
          </Button>
          <Button variant={unassignedOnly ? "primary" : "subtle"} className="py-1.5 px-3 text-xs"
            onClick={() => setUnassignedOnly(!unassignedOnly)} data-testid="unassigned-filter">
            {t("deal.unassigned")}
          </Button>
          {writable && <Button onClick={openNew} data-testid="add-deal-btn"><Plus size={16} /><span className="hidden sm:inline">{t("deal.newDeal")}</span></Button>}
        </div>
      </div>

      {error && <p className="text-sm text-danger">{error}</p>}

      {!items ? <Spinner /> : view === "board" ? (
        <DragDropContext onDragEnd={onDragEnd}>
          <div className="flex gap-3 overflow-x-auto pb-4 -mx-4 px-4 sm:mx-0 sm:px-0">
            {STAGES.map((s) => (
              <Droppable droppableId={s} key={s}>
                {(provided, snapshot) => (
                  <div ref={provided.innerRef} {...provided.droppableProps}
                    className={`w-64 shrink-0 rounded-sm border border-border ${snapshot.isDraggingOver ? "bg-primary/5" : "bg-surface/40"}`}
                    data-testid={`stage-col-${s}`}>
                    <div className="px-3 py-2.5 border-b border-border flex items-center justify-between sticky top-0">
                      <span className="text-xs uppercase tracking-[0.1em] font-medium">{t(`statuses.${s}`)}</span>
                      <span className="text-xs text-muted">{byStage(s).length}</span>
                    </div>
                    <div className="px-2 py-1 text-[11px] text-muted border-b border-border">{eur(stageTotal(s))}</div>
                    <div className="p-2 space-y-2 min-h-[80px]">
                      {byStage(s).map((d, i) => (
                        <Draggable draggableId={d.id} index={i} key={d.id} isDragDisabled={!writable}>
                          {(prov) => (
                            <div ref={prov.innerRef} {...prov.draggableProps} {...prov.dragHandleProps}
                              data-testid={`deal-card-${d.id}`}
                              onClick={() => navigate(`/deals/${d.id}`)}
                              className="bg-bg border border-border rounded-sm p-3 group hover:border-primary transition-colors cursor-pointer">
                              <div className="flex items-start justify-between gap-2">
                                <span className="text-sm font-medium leading-snug">{d.title}</span>
                                {writable && (
                                  <div className="hidden group-hover:flex gap-1 shrink-0">
                                    <button onClick={(e) => { e.stopPropagation(); openEdit(d); }} className="text-muted hover:text-txt"><Pencil size={13} /></button>
                                    <button onClick={(e) => { e.stopPropagation(); del(d.id); }} className="text-muted hover:text-danger"><Trash2 size={13} /></button>
                                  </div>
                                )}
                              </div>
                              <div className="font-display font-bold text-lg mt-1">{eur(d.value)}</div>
                              <div className="flex items-center gap-2 mt-1">
                                <span className="text-xs text-muted">{d.probability}%</span>
                                {d.ball_in_court && d.ball_in_court !== "none" && (
                                  <Badge value={d.ball_in_court === "us" ? "lost" : "won"}
                                    label={t(`deal.ballInCourt_${d.ball_in_court}`)} />
                                )}
                              </div>
                            </div>
                          )}
                        </Draggable>
                      ))}
                      {provided.placeholder}
                    </div>
                  </div>
                )}
              </Droppable>
            ))}
          </div>
        </DragDropContext>
      ) : (
        <div className="border border-border rounded-sm overflow-hidden stagger">
          {visibleItems.map((d) => (
            <div key={d.id} data-testid={`deal-row-${d.id}`} onClick={() => navigate(`/deals/${d.id}`)} className="flex items-center gap-3 px-4 py-3 border-b border-border last:border-0 hover:bg-surface/60 transition-colors cursor-pointer">
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium truncate">{d.title}</div>
                <div className="text-xs text-muted">{d.probability}%</div>
              </div>
              <span className="font-display font-bold">{eur(d.value)}</span>
              {d.ball_in_court && d.ball_in_court !== "none" && (
                <Badge value={d.ball_in_court === "us" ? "lost" : "won"}
                  label={t(`deal.ballInCourt_${d.ball_in_court}`)} />
              )}
              <Badge value={d.stage} label={t(`statuses.${d.stage}`)} />
              {writable && (
                <div className="flex gap-1 shrink-0">
                  <button onClick={(e) => { e.stopPropagation(); openEdit(d); }} className="p-1.5 rounded-sm hover:bg-border/60 text-muted transition-colors"><Pencil size={14} /></button>
                  <button onClick={(e) => { e.stopPropagation(); del(d.id); }} className="p-1.5 rounded-sm hover:bg-danger/15 text-muted hover:text-danger transition-colors"><Trash2 size={14} /></button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      <Modal open={modal} onClose={() => setModal(false)} title={editing ? t("deal.editDeal") : t("deal.newDeal")}
        footer={<>
          <Button variant="ghost" onClick={() => setModal(false)}>{t("common.cancel")}</Button>
          <Button onClick={save} data-testid="save-deal-btn">{t("common.save")}</Button>
        </>}>
        <Field label={t("deal.name")}><Input data-testid="deal-title" value={form.title} onChange={set("title")} /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label={t("deal.value")}><Input data-testid="deal-value" type="number" value={form.value} onChange={set("value")} /></Field>
          <Field label={t("deal.stage")}>
            <Select value={form.stage} onChange={set("stage")}>
              {STAGES.map((s) => <option key={s} value={s}>{t(`statuses.${s}`)}</option>)}
            </Select>
          </Field>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label={t("deal.company")}>
            <Select value={form.company_id || ""} onChange={set("company_id")}>
              <option value="">—</option>
              {companies.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </Select>
          </Field>
          <Field label={t("deal.contact")}>
            <Select value={form.contact_id || ""} onChange={set("contact_id")}>
              <option value="">—</option>
              {contacts.map((c) => <option key={c.id} value={c.id}>{c.first_name} {c.last_name}</option>)}
            </Select>
          </Field>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label={t("deal.source")}>
            <Select data-testid="deal-source" value={form.source || ""} onChange={set("source")}>
              <option value="">—</option>
              {SOURCES.map((s) => <option key={s} value={s}>{t(`deal.source_${s}`)}</option>)}
            </Select>
          </Field>
          <Field label={t("deal.leadType")}>
            <Select data-testid="deal-lead-type" value={form.lead_type} onChange={set("lead_type")}>
              {LEAD_TYPES.map((lt) => <option key={lt} value={lt}>{t(`deal.leadType_${lt}`)}</option>)}
            </Select>
          </Field>
        </div>
        {form.lead_type === "double" && (
          <div className="grid grid-cols-2 gap-3 border border-border rounded-sm p-3" data-testid="contract-party-block">
            <Field label={t("deal.contractCompany")}>
              <Select data-testid="deal-contract-company" value={form.contract_company_id || ""} onChange={set("contract_company_id")}>
                <option value="">—</option>
                {companies.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </Select>
            </Field>
            <Field label={t("deal.contractContact")}>
              <Select data-testid="deal-contract-contact" value={form.contract_contact_id || ""} onChange={set("contract_contact_id")}>
                <option value="">—</option>
                {contacts.map((c) => <option key={c.id} value={c.id}>{c.first_name} {c.last_name}</option>)}
              </Select>
            </Field>
          </div>
        )}
        <Field label={t("deal.referredBy")}>
          <Select data-testid="deal-referred-by" value={form.referred_by_contact_id || ""} onChange={set("referred_by_contact_id")}>
            <option value="">—</option>
            {contacts.map((c) => <option key={c.id} value={c.id}>{c.first_name} {c.last_name}</option>)}
          </Select>
        </Field>
        {!editing && (
          <label className="flex items-center gap-2 text-sm mt-1">
            <input type="checkbox" data-testid="deal-unassigned" checked={form.unassigned}
              onChange={toggleUnassigned} />
            {t("deal.unassigned")}
          </label>
        )}
        <Field label={t("deal.notes")}><Textarea rows={3} value={form.notes || ""} onChange={set("notes")} /></Field>
      </Modal>
    </div>
  );
}
