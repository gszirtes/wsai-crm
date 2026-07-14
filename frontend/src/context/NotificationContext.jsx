import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import api from "../api";

const Ctx = createContext(null);

export function NotificationProvider({ children }) {
  const [data, setData] = useState({ items: [], unread: 0 });

  const refresh = useCallback(
    () => api.get("/notifications").then((r) => setData(r.data)).catch(() => {}),
    []
  );

  useEffect(() => {
    refresh();
    const iv = setInterval(refresh, 60000);
    return () => clearInterval(iv);
  }, [refresh]);

  const markRead = useCallback(async (id) => {
    await api.post(`/notifications/${id}/read`);
    refresh();
  }, [refresh]);

  const markAll = useCallback(async () => {
    await api.post("/notifications/read-all");
    refresh();
  }, [refresh]);

  return (
    <Ctx.Provider value={{ data, refresh, markRead, markAll }}>{children}</Ctx.Provider>
  );
}

export const useNotifications = () => useContext(Ctx);
