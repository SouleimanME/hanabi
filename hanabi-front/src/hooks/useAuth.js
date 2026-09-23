import { useState, useEffect, useCallback } from "react";
import { Auth, Orders, setToken, getToken } from "../lib/api.js";

/** Session utilisateur et historique de commandes. */
export function useAuth() {
  const [user, setUser] = useState(null);
  const [orders, setOrders] = useState([]);

  const refreshOrders = useCallback(async () => {
    try {
      setOrders(await Orders.history());
    } catch {
      /* historique indisponible : on garde la liste precedente */
    }
  }, []);

  // Restaure la session au chargement. Un jeton expire est purge pour ne pas
  // laisser l'interface en etat "connecte" alors que l'API refuse tout.
  useEffect(() => {
    if (!getToken()) return;
    (async () => {
      try {
        setUser(await Auth.me());
        await refreshOrders();
      } catch {
        setToken(null);
      }
    })();
  }, [refreshOrders]);

  const applySession = useCallback(
    (response) => {
      setToken(response.access_token);
      setUser(response.user);
      refreshOrders();
      return response.user;
    },
    [refreshOrders],
  );

  const login = useCallback(
    async ({ email, password, antibot }) => {
      try {
        return { user: applySession(await Auth.login(email, password, antibot)), error: null };
      } catch (e) {
        return { user: null, error: e.message };
      }
    },
    [applySession],
  );

  const signup = useCallback(
    async (payload) => {
      try {
        return { user: applySession(await Auth.register(payload)), error: null };
      } catch (e) {
        return { user: null, error: e.message };
      }
    },
    [applySession],
  );

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    setOrders([]);
  }, []);

  /** Relit le profil depuis l'API, sans toucher au jeton. */
  const refreshUser = useCallback(async () => {
    if (!getToken()) return;
    try {
      setUser(await Auth.me());
    } catch {
      /* profil indisponible : on garde celui qu'on a */
    }
  }, []);

  /** Adopte la session rendue par une route qui authentifie d'elle-meme. */
  const adopterSession = useCallback((response) => applySession(response), [applySession]);

  /** Remplace le profil en memoire par celui que le serveur vient de rendre. */
  const poserProfil = useCallback((profil) => setUser(profil), []);

  return {
    user,
    orders,
    login,
    signup,
    logout,
    refreshOrders,
    refreshUser,
    adopterSession,
    poserProfil,
  };
}
