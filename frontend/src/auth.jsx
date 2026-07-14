import React, { createContext, useContext, useEffect, useState } from "react";
import api from "./api";
import i18n from "./i18n";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null); // null = checking
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    api
      .get("/auth/me")
      .then((res) => {
        setUser(res.data);
        if (res.data.locale) i18n.changeLanguage(res.data.locale);
      })
      .catch(() => setUser(false))
      .finally(() => setChecked(true));
  }, []);

  const login = async (email, password) => {
    const res = await api.post("/auth/login", { email, password });
    setUser(res.data);
    if (res.data.locale) i18n.changeLanguage(res.data.locale);
    return res.data;
  };

  const register = async (name, email, password) => {
    const res = await api.post("/auth/register", { name, email, password });
    setUser(res.data);
    return res.data;
  };

  const logout = async () => {
    await api.post("/auth/logout");
    setUser(false);
  };

  return (
    <AuthContext.Provider value={{ user, setUser, login, register, logout, checked }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);

export const can = {
  write: (user) => user && user.role !== "guest",
  admin: (user) => user && user.role === "admin",
};
