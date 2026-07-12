import { createContext, useCallback, useContext, useEffect, useState } from "react";
import {
  setAuthToken,
  setCambioPasswordRequeridoHandler,
  setConsorcioActivoId as setClientConsorcioId,
  setUnauthorizedHandler,
} from "../api/client";
import { listarConsorciosAccesibles } from "../api/me";

const AuthContext = createContext(null);

const STORAGE_TOKEN = "consorcio_token";
const STORAGE_USER = "consorcio_user";
const STORAGE_CONSORCIO_ID = "consorcio_activo_id";
const STORAGE_MUST_CHANGE_PASSWORD = "consorcio_must_change_password";

function _decodeJwt(token) {
  try {
    const payload = token.split(".")[1];
    const decoded = atob(payload.replace(/-/g, "+").replace(/_/g, "/"));
    return JSON.parse(decoded);
  } catch {
    return null;
  }
}

export function AuthProvider({ children }) {
  const [token, setToken] = useState(null);
  const [user, setUser] = useState(null);
  const [consorcioActivoId, setConsorcioActivoIdState] = useState(null);
  const [consorciosAccesibles, setConsorciosAccesibles] = useState([]);
  const [mustChangePassword, setMustChangePassword] = useState(false);
  const [hydrating, setHydrating] = useState(true);

  // Hidrata desde localStorage al montar.
  useEffect(() => {
    const storedToken = localStorage.getItem(STORAGE_TOKEN);
    const storedUser = localStorage.getItem(STORAGE_USER);
    const storedConsorcio = localStorage.getItem(STORAGE_CONSORCIO_ID);
    const storedMustChange = localStorage.getItem(STORAGE_MUST_CHANGE_PASSWORD);

    if (!storedToken || !storedUser) {
      setHydrating(false);
      return;
    }

    let parsedUser;
    try {
      parsedUser = JSON.parse(storedUser);
    } catch {
      localStorage.removeItem(STORAGE_TOKEN);
      localStorage.removeItem(STORAGE_USER);
      localStorage.removeItem(STORAGE_CONSORCIO_ID);
      localStorage.removeItem(STORAGE_MUST_CHANGE_PASSWORD);
      setHydrating(false);
      return;
    }

    setToken(storedToken);
    setUser(parsedUser);
    setMustChangePassword(storedMustChange === "1");
    setAuthToken(storedToken);

    if (parsedUser.rol === "super_admin") {
      setHydrating(false);
      return;
    }

    // Rol no super_admin: cargar consorcios accesibles y elegir uno activo.
    // Cubre el caso post-impersonate (donde el token fue reemplazado sin
    // pasar por login()) y el F5 con un consorcio guardado pero potencialmente
    // stale.
    (async () => {
      const r = await listarConsorciosAccesibles();
      if (r.status === 200 && Array.isArray(r.data)) {
        setConsorciosAccesibles(r.data);
        const storedId = storedConsorcio ? Number(storedConsorcio) : null;
        const idElegido =
          storedId && r.data.some((c) => c.id === storedId)
            ? storedId
            : r.data[0]?.id ?? null;
        if (idElegido) {
          localStorage.setItem(STORAGE_CONSORCIO_ID, String(idElegido));
          setClientConsorcioId(idElegido);
          setConsorcioActivoIdState(idElegido);
        }
      }
      setHydrating(false);
    })();
  }, []);

  // Propaga el token al cliente HTTP.
  useEffect(() => {
    setAuthToken(token);
  }, [token]);

  // Propaga el consorcio activo al cliente HTTP.
  useEffect(() => {
    setClientConsorcioId(consorcioActivoId);
  }, [consorcioActivoId]);

  const seleccionarConsorcio = useCallback((id) => {
    const numericId = Number(id);
    localStorage.setItem(STORAGE_CONSORCIO_ID, String(numericId));
    setClientConsorcioId(numericId);
    setConsorcioActivoIdState(numericId);
  }, []);

  const cargarConsorciosAccesibles = useCallback(async (rol) => {
    if (rol === "super_admin") {
      setConsorciosAccesibles([]);
      return [];
    }
    const r = await listarConsorciosAccesibles();
    if (r.status === 200 && Array.isArray(r.data)) {
      setConsorciosAccesibles(r.data);
      return r.data;
    }
    setConsorciosAccesibles([]);
    return [];
  }, []);

  const login = useCallback(
    async (newToken, newUser) => {
      localStorage.setItem(STORAGE_TOKEN, newToken);
      localStorage.setItem(STORAGE_USER, JSON.stringify(newUser));
      setToken(newToken);
      setUser(newUser);

      const claims = _decodeJwt(newToken) || {};
      const mustChange = !!claims.must_change_password || !!newUser?.must_change_password;
      setMustChangePassword(mustChange);
      localStorage.setItem(STORAGE_MUST_CHANGE_PASSWORD, mustChange ? "1" : "0");

      // Cargar consorcios accesibles y elegir uno activo (excepto super_admin).
      if (newUser.rol !== "super_admin") {
        // Setear token globalmente antes de la primera llamada.
        setAuthToken(newToken);
        const accesibles = await cargarConsorciosAccesibles(newUser.rol);
        if (accesibles.length > 0) {
          const stored = localStorage.getItem(STORAGE_CONSORCIO_ID);
          const storedId = stored ? Number(stored) : null;
          const idElegido =
            storedId && accesibles.some((c) => c.id === storedId)
              ? storedId
              : accesibles[0].id;
          localStorage.setItem(STORAGE_CONSORCIO_ID, String(idElegido));
          setClientConsorcioId(idElegido);
          setConsorcioActivoIdState(idElegido);
        }
      }
    },
    [cargarConsorciosAccesibles]
  );

  const logout = useCallback(() => {
    localStorage.removeItem(STORAGE_TOKEN);
    localStorage.removeItem(STORAGE_USER);
    localStorage.removeItem(STORAGE_CONSORCIO_ID);
    localStorage.removeItem(STORAGE_MUST_CHANGE_PASSWORD);
    setToken(null);
    setUser(null);
    setConsorcioActivoIdState(null);
    setConsorciosAccesibles([]);
    setMustChangePassword(false);
  }, []);

  const marcarPasswordCambiada = useCallback(() => {
    setMustChangePassword(false);
    localStorage.setItem(STORAGE_MUST_CHANGE_PASSWORD, "0");
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(logout);
  }, [logout]);

  useEffect(() => {
    setCambioPasswordRequeridoHandler(() => setMustChangePassword(true));
  }, []);

  // El JWT actual es de impersonate?
  const impersonatedBy = token ? _decodeJwt(token)?.impersonated_by ?? null : null;

  return (
    <AuthContext.Provider
      value={{
        token,
        user,
        hydrating,
        consorcioActivoId,
        consorciosAccesibles,
        mustChangePassword,
        impersonatedBy,
        login,
        logout,
        seleccionarConsorcio,
        cargarConsorciosAccesibles,
        marcarPasswordCambiada,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth debe usarse dentro de <AuthProvider>");
  return ctx;
}
