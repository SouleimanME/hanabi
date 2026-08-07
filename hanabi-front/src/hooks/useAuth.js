import { useState, useEffect, useCallback } from "react";
import { Auth, Orders, setToken, getToken } from "../lib/api.js";

/**
 * Session utilisateur et historique de commandes.
 *
 * Les fonctions `login` / `signup` suivent la meme convention que le reste du
 * projet : elles renvoient `null` en cas de succes, ou le message d'erreur a
 * afficher. Cela evite d'avoir a envelopper chaque appel dans un try/catch
 * cote composant.
 */
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

  return { user, orders, login, signup, logout, refreshOrders };
}
