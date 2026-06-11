import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { setAuthToken, setUnauthorizedHandler } from "../api/client";

const AuthContext = createContext(null);

const STORAGE_TOKEN = "consorcio_token";
const STORAGE_USER = "consorcio_user";

export function AuthProvider({ children }) {
  const [token, setToken] = useState(null);
  const [user, setUser] = useState(null);
  const [hydrating, setHydrating] = useState(true);

  useEffect(() => {
    const storedToken = localStorage.getItem(STORAGE_TOKEN);
    const storedUser = localStorage.getItem(STORAGE_USER);

    if (storedToken && storedUser) {
      try {
        setToken(storedToken);
        setUser(JSON.parse(storedUser));
      } catch {
        localStorage.removeItem(STORAGE_TOKEN);
        localStorage.removeItem(STORAGE_USER);
      }
    }

    setHydrating(false);
  }, []);

  useEffect(() => {
    setAuthToken(token);
  }, [token]);

  const login = useCallback((newToken, newUser) => {
    localStorage.setItem(STORAGE_TOKEN, newToken);
    localStorage.setItem(STORAGE_USER, JSON.stringify(newUser));
    setToken(newToken);
    setUser(newUser);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(STORAGE_TOKEN);
    localStorage.removeItem(STORAGE_USER);
    setToken(null);
    setUser(null);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(logout);
  }, [logout]);

  return (
    <AuthContext.Provider value={{ token, user, hydrating, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth debe usarse dentro de <AuthProvider>");
  return ctx;
}
