import React, { useEffect, useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { DragDropContext, Droppable, Draggable } from "@hello-pangea/dnd";
import { Plus, Pencil, Trash2, LayoutGrid, List } from "lucide-react";
import api from "../api";
import { useAuth, can } from "../auth";
import { Button, Input, Select, Field, Modal, Badge, Spinner, Textarea } from "../components/common";

const STAGES = ["lead", "qualified", "proposal", "negotiation", "won", "lost"];
const empty = { title: "", value: 0, currency: "EUR", stage: "lead", company_id: "", contact_id: "", notes: "" };

export default function Deals() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const writable = can.write(user);
  const [items, setItems] = useState(null);
  const [companies, setCompanies] = useState([]);
  const [contacts, setContacts] = useState([]);
  const [view, setView] = useState("board");
  const [modal, setModal] = useState(false);
  const [form, setForm] = useState(empty);
  const [editing, setEditing] = useState(null);

  const load = useCallback(() => { api.get("/deals").then((r) => setItems(r.data)); }, []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    api.get("/companies").then((r) => setCompanies(r.data));
    api.get("/contacts").then((r) => setContacts(r.data));
  }, []);

  const openNew = () => { setForm(empty); setEditing(null); setModal(true); };
  const openEdit = (d) => { setForm({ ...empty, ...d, company_id: d.company_id || "", contact_id: d.contact_id || "" }); setEditing(d.id); setModal(true); };
  const save = async () => {
    const payload = { ...form, value: parseFloat(form.value) || 0, company_id: form.company_id || null, contact_id: form.contact_id || null };
    if (editing) await api.put(`/deals/${editing}`, payload);
    else await api.post("/deals", payload);
    setModal(false); load();
  };
  const del = async (id) => {
    if (!window.confirm(t("common.confirmDelete"))) return;
    await api.delete(`/deals/${id}`); load();
  };
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const eur = (n) => "€" + new Intl.NumberFormat().format(n || 0);

  const onDragEnd = async (result) => {
    if (!result.destination || !writable) return;
    const newStage = result.destination.droppableId;
    const id = result.draggableId;
    const deal = items.find((d) => d.id === id);
    if (!deal || deal.stage === newStage) return;
    setItems(items.map((d) => (d.id === id ? { ...d, stage: newStage } : d)));
    await api.patch(`/deals/${id}/stage`, { stage: newStage });
    load();
  };

  const byStage = (s) => (items || []).filter((d) => d.stage === s);
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
          {writable && <Button onClick={openNew} data-testid="add-deal-btn"><Plus size={16} /><span className="hidden sm:inline">{t("deal.newDeal")}</span></Button>}
        </div>
      </div>

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
                              className="bg-bg border border-border rounded-sm p-3 group hover:border-primary transition-colors">
                              <div className="flex items-start justify-between gap-2">
                                <span className="text-sm font-medium leading-snug">{d.title}</span>
                                {writable && (
                                  <div className="hidden group-hover:flex gap-1 shrink-0">
                                    <button onClick={() => openEdit(d)} className="text-muted hover:text-txt"><Pencil size={13} /></button>
                                    <button onClick={() => del(d.id)} className="text-muted hover:text-danger"><Trash2 size={13} /></button>
                                  </div>
                                )}
                              </div>
                              <div className="font-display font-bold text-lg mt-1">{eur(d.value)}</div>
                              <div className="text-xs text-muted mt-1">{d.probability}%</div>
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
          {items.map((d) => (
            <div key={d.id} data-testid={`deal-row-${d.id}`} className="flex items-center gap-3 px-4 py-3 border-b border-border last:border-0 hover:bg-surface/60 transition-colors">
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium truncate">{d.title}</div>
                <div className="text-xs text-muted">{d.probability}%</div>
              </div>
              <span className="font-display font-bold">{eur(d.value)}</span>
              <Badge value={d.stage} label={t(`statuses.${d.stage}`)} />
              {writable && (
                <div className="flex gap-1 shrink-0">
                  <button onClick={() => openEdit(d)} className="p-1.5 rounded-sm hover:bg-border/60 text-muted transition-colors"><Pencil size={14} /></button>
                  <button onClick={() => del(d.id)} className="p-1.5 rounded-sm hover:bg-danger/15 text-muted hover:text-danger transition-colors"><Trash2 size={14} /></button>
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
        <Field label={t("deal.notes")}><Textarea rows={3} value={form.notes || ""} onChange={set("notes")} /></Field>
      </Modal>
    </div>
  );
}
